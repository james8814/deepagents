"""Skills middleware for loading and exposing agent skills to the system prompt.

This module implements Anthropic's agent skills pattern with progressive disclosure,
loading skills from backend storage via configurable sources.

## Architecture

Skills are loaded from one or more **sources** - paths in a backend where skills are
organized. Sources are loaded in order, with later sources overriding earlier ones
when skills have the same name (last one wins). This enables layering: base -> user
-> project -> team skills.

The middleware uses backend APIs exclusively (no direct filesystem access), making it
portable across different storage backends (filesystem, state, remote storage, etc.).

For StateBackend (ephemeral/in-memory), use a factory function:
```python
SkillsMiddleware(backend=lambda rt: StateBackend(rt), ...)
```

## Skill Structure

Each skill is a directory containing a SKILL.md file with YAML frontmatter:

```
/skills/user/web-research/
├── SKILL.md          # Required: YAML frontmatter + markdown instructions
└── helper.py         # Optional: supporting files
```

SKILL.md format:
```markdown
---
name: web-research
description: Structured approach to conducting thorough web research
license: MIT
---

# Web Research Skill

## When to Use
- User asks you to research a topic
...
```

## Skill Metadata (SkillMetadata)

Parsed from YAML frontmatter per Agent Skills specification:
- `name`: Skill identifier (max 64 chars, lowercase alphanumeric and hyphens)
- `description`: What the skill does (max 1024 chars)
- `path`: Backend path to the SKILL.md file
- Optional: `license`, `compatibility`, `metadata`, `allowed_tools`

## Sources

Sources are simply paths to skill directories in the backend. The source name is
derived from the last component of the path (e.g., "/skills/user/" -> "user").

Example sources:
```python
[
    "/skills/user/",
    "/skills/project/"
]
```

## Path Conventions

All paths use POSIX conventions (forward slashes) via `PurePosixPath`:
- Backend paths: "/skills/user/web-research/SKILL.md"
- Virtual, platform-independent
- Backends handle platform-specific conversions as needed

## Usage

```python
from deepagents.backends.state import StateBackend
from deepagents.middleware.skills import SkillsMiddleware

middleware = SkillsMiddleware(
    backend=my_backend,
    sources=[
        "/skills/base/",
        "/skills/user/",
        "/skills/project/",
    ],
)
```
"""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Annotated

import yaml
from langchain.agents.middleware.types import PrivateStateAttr

if TYPE_CHECKING:
    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

from collections.abc import Awaitable, Callable
from typing import Literal, NotRequired
from typing_extensions import TypedDict

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolRuntime
from langgraph.runtime import Runtime

from deepagents.middleware._utils import append_to_system_message

logger = logging.getLogger(__name__)

# Security: Maximum size for SKILL.md files to prevent DoS attacks (10MB)
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024

# Agent Skills specification constraints (https://agentskills.io/specification)
MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024

# V2: Resource type mapping for standard skill resource directories
RESOURCE_TYPE_MAP: dict[str, Literal["script", "reference", "asset"]] = {
    "scripts": "script",
    "references": "reference",
    "assets": "asset",
}


class ResourceMetadata(TypedDict):
    """技能资源文件的元数据。用于延迟发现策略，缓存技能目录下的资源文件信息。"""
    path: str
    """资源文件在 backend 中的完整路径。"""
    type: Literal["script", "reference", "asset", "other"]
    """资源类型，基于所在目录名推断。"""
    skill_name: str
    """所属技能的名称。"""


# =============================================================================
# V2: Lazy resource discovery functions
# =============================================================================


def _discover_resources(
    backend: "BackendProtocol",
    skill_dir: str,
    skill_name: str,
) -> list["ResourceMetadata"]:
    """发现技能目录下的资源文件（同步版本）。扫描标准资源目录（仅第一层）。"""
    resources: list["ResourceMetadata"] = []

    try:
        items = backend.ls_info(skill_dir)
    except Exception:
        logger.warning("Failed to list resources for skill '%s' at %s", skill_name, skill_dir)
        return resources

    for item in items:
        item_path = item["path"]
        item_name = PurePosixPath(item_path).name

        if item.get("is_dir"):
            resource_type = RESOURCE_TYPE_MAP.get(item_name)
            if resource_type is None:
                continue
            try:
                sub_items = backend.ls_info(item_path)
            except Exception:
                logger.warning("Failed to list resources in %s", item_path)
                continue
            for sub_item in sub_items:
                if not sub_item.get("is_dir"):
                    resources.append({"path": sub_item["path"], "type": resource_type, "skill_name": skill_name})
        else:
            if item_name != "SKILL.md":
                resources.append({"path": item_path, "type": "other", "skill_name": skill_name})

    return resources


async def _adiscover_resources(
    backend: "BackendProtocol",
    skill_dir: str,
    skill_name: str,
) -> list["ResourceMetadata"]:
    """发现技能目录下的资源文件（异步版本）。"""
    resources: list["ResourceMetadata"] = []

    try:
        items = await backend.als_info(skill_dir)
    except Exception:
        logger.warning("Failed to list resources for skill '%s' at %s", skill_name, skill_dir)
        return resources

    for item in items:
        item_path = item["path"]
        item_name = PurePosixPath(item_path).name

        if item.get("is_dir"):
            resource_type = RESOURCE_TYPE_MAP.get(item_name)
            if resource_type is None:
                continue
            try:
                sub_items = await backend.als_info(item_path)
            except Exception:
                logger.warning("Failed to list resources in %s", item_path)
                continue
            for sub_item in sub_items:
                if not sub_item.get("is_dir"):
                    resources.append({"path": sub_item["path"], "type": resource_type, "skill_name": skill_name})
        else:
            if item_name != "SKILL.md":
                resources.append({"path": item_path, "type": "other", "skill_name": skill_name})

    return resources


def _format_resource_summary(resources: list["ResourceMetadata"]) -> str:
    """格式化资源摘要，按类型分组。"""
    by_type: dict[str, int] = {}
    for r in resources:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    parts = [f"{count} {rtype}{'s' if count > 1 else ''}" for rtype, count in sorted(by_type.items())]
    return ", ".join(parts)


def _format_skill_annotations(skill: "SkillMetadata") -> str:
    """Format optional skill annotations (license, compatibility)."""
    annotations = []
    if skill.get("license"):
        annotations.append(f"License: {skill['license']}")
    if skill.get("compatibility"):
        annotations.append(f"Compatibility: {skill['compatibility']}")
    return "; ".join(annotations) if annotations else ""



class SkillMetadata(TypedDict):
    """Metadata for a skill per Agent Skills specification (https://agentskills.io/specification)."""

    name: str
    """Skill identifier (max 64 chars, lowercase alphanumeric and hyphens)."""

    description: str
    """What the skill does (max 1024 chars)."""

    path: str
    """Path to the SKILL.md file."""

    license: str | None
    """License name or reference to bundled license file."""

    compatibility: str | None
    """Environment requirements (max 500 chars)."""

    metadata: dict[str, str]
    """Arbitrary key-value mapping for additional metadata."""

    allowed_tools: list[str]
    """Space-delimited list of pre-approved tools. (Experimental)"""


class SkillsState(AgentState):
    """State for the skills middleware."""

    skills_metadata: NotRequired[Annotated[list[SkillMetadata], PrivateStateAttr]]
    """List of loaded skill metadata from configured sources. Not propagated to parent agents."""

    # V2: Track which skills have been loaded (activated) by the agent
    skills_loaded: NotRequired[Annotated[list[str], PrivateStateAttr]]
    """已加载（激活）的技能名称列表。"""

    # V2: Cache discovered skill resources for loaded skills
    skill_resources: NotRequired[Annotated[dict[str, list[ResourceMetadata]], PrivateStateAttr]]
    """已发现的技能资源映射，键为技能名称。"""


class SkillsStateUpdate(TypedDict):
    """State update for the skills middleware."""

    skills_metadata: list[SkillMetadata]
    """List of loaded skill metadata to merge into state."""
    # V2 fields
    skills_loaded: list[str]
    """List of loaded skill names."""
    skill_resources: dict[str, list[ResourceMetadata]]
    """Discovered skill resources cache."""


def _validate_skill_name(name: str, directory_name: str) -> tuple[bool, str]:
    """Validate skill name per Agent Skills specification.

    Requirements per spec:
    - Max 64 characters
    - Lowercase alphanumeric and hyphens only (a-z, 0-9, -)
    - Cannot start or end with hyphen
    - No consecutive hyphens
    - Must match parent directory name

    Args:
        name: Skill name from YAML frontmatter
        directory_name: Parent directory name

    Returns:
        (is_valid, error_message) tuple. Error message is empty if valid.
    """
    if not name:
        return False, "name is required"
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, "name exceeds 64 characters"
    # Pattern: lowercase alphanumeric, single hyphens between segments, no start/end hyphen
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        return False, "name must be lowercase alphanumeric with single hyphens only"
    if name != directory_name:
        return False, f"name '{name}' must match directory name '{directory_name}'"
    return True, ""


def _parse_skill_metadata(
    content: str,
    skill_path: str,
    directory_name: str,
) -> SkillMetadata | None:
    """Parse YAML frontmatter from SKILL.md content.

    Extracts metadata per Agent Skills specification from YAML frontmatter delimited
    by --- markers at the start of the content.

    Args:
        content: Content of the SKILL.md file
        skill_path: Path to the SKILL.md file (for error messages and metadata)
        directory_name: Name of the parent directory containing the skill

    Returns:
        SkillMetadata if parsing succeeds, None if parsing fails or validation errors occur
    """
    if len(content) > MAX_SKILL_FILE_SIZE:
        logger.warning("Skipping %s: content too large (%d bytes)", skill_path, len(content))
        return None

    # Match YAML frontmatter between --- delimiters
    frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n"
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if not match:
        logger.warning("Skipping %s: no valid YAML frontmatter found", skill_path)
        return None

    frontmatter_str = match.group(1)

    # Parse YAML using safe_load for proper nested structure support
    try:
        frontmatter_data = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        logger.warning("Invalid YAML in %s: %s", skill_path, e)
        return None

    if not isinstance(frontmatter_data, dict):
        logger.warning("Skipping %s: frontmatter is not a mapping", skill_path)
        return None

    # Validate required fields
    name = frontmatter_data.get("name")
    description = frontmatter_data.get("description")

    if not name or not description:
        logger.warning("Skipping %s: missing required 'name' or 'description'", skill_path)
        return None

    # Validate name format per spec (warn but continue loading for backwards compatibility)
    is_valid, error = _validate_skill_name(str(name), directory_name)
    if not is_valid:
        logger.warning(
            "Skill '%s' in %s does not follow Agent Skills specification: %s. Consider renaming for spec compliance.",
            name,
            skill_path,
            error,
        )

    # Validate description length per spec (max 1024 chars)
    description_str = str(description).strip()
    if len(description_str) > MAX_SKILL_DESCRIPTION_LENGTH:
        logger.warning(
            "Description exceeds %d characters in %s, truncating",
            MAX_SKILL_DESCRIPTION_LENGTH,
            skill_path,
        )
        description_str = description_str[:MAX_SKILL_DESCRIPTION_LENGTH]

    if frontmatter_data.get("allowed-tools"):
        allowed_tools = frontmatter_data.get("allowed-tools").split(" ")
    else:
        allowed_tools = []

    return SkillMetadata(
        name=str(name),
        description=description_str,
        path=skill_path,
        metadata=frontmatter_data.get("metadata", {}),
        license=frontmatter_data.get("license", "").strip() or None,
        compatibility=frontmatter_data.get("compatibility", "").strip() or None,
        allowed_tools=allowed_tools,
    )


def _list_skills(backend: BackendProtocol, source_path: str) -> list[SkillMetadata]:
    """List all skills from a backend source.

    Scans backend for subdirectories containing SKILL.md files, downloads their content,
    parses YAML frontmatter, and returns skill metadata.

    Expected structure:
        source_path/
        ├── skill-name/
        │   ├── SKILL.md        # Required
        │   └── helper.py       # Optional

    Args:
        backend: Backend instance to use for file operations
        source_path: Path to the skills directory in the backend

    Returns:
        List of skill metadata from successfully parsed SKILL.md files
    """
    base_path = source_path

    skills: list[SkillMetadata] = []
    items = backend.ls_info(base_path)
    # Find all skill directories (directories containing SKILL.md)
    skill_dirs = []
    for item in items:
        if not item.get("is_dir"):
            continue
        skill_dirs.append(item["path"])

    if not skill_dirs:
        return []

    # For each skill directory, check if SKILL.md exists and download it
    skill_md_paths = []
    for skill_dir_path in skill_dirs:
        # Construct SKILL.md path using PurePosixPath for safe, standardized path operations
        skill_dir = PurePosixPath(skill_dir_path)
        skill_md_path = str(skill_dir / "SKILL.md")
        skill_md_paths.append((skill_dir_path, skill_md_path))

    paths_to_download = [skill_md_path for _, skill_md_path in skill_md_paths]
    responses = backend.download_files(paths_to_download)

    # Parse each downloaded SKILL.md
    for (skill_dir_path, skill_md_path), response in zip(skill_md_paths, responses, strict=True):
        if response.error:
            # Skill doesn't have a SKILL.md, skip it
            continue

        if response.content is None:
            logger.warning("Downloaded skill file %s has no content", skill_md_path)
            continue

        try:
            content = response.content.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.warning("Error decoding %s: %s", skill_md_path, e)
            continue

        # Extract directory name from path using PurePosixPath
        directory_name = PurePosixPath(skill_dir_path).name

        # Parse metadata
        skill_metadata = _parse_skill_metadata(
            content=content,
            skill_path=skill_md_path,
            directory_name=directory_name,
        )
        if skill_metadata:
            skills.append(skill_metadata)

    return skills


async def _alist_skills(backend: BackendProtocol, source_path: str) -> list[SkillMetadata]:
    """List all skills from a backend source (async version).

    Scans backend for subdirectories containing SKILL.md files, downloads their content,
    parses YAML frontmatter, and returns skill metadata.

    Expected structure:
        source_path/
        ├── skill-name/
        │   ├── SKILL.md        # Required
        │   └── helper.py       # Optional

    Args:
        backend: Backend instance to use for file operations
        source_path: Path to the skills directory in the backend

    Returns:
        List of skill metadata from successfully parsed SKILL.md files
    """
    base_path = source_path

    skills: list[SkillMetadata] = []
    items = await backend.als_info(base_path)
    # Find all skill directories (directories containing SKILL.md)
    skill_dirs = []
    for item in items:
        if not item.get("is_dir"):
            continue
        skill_dirs.append(item["path"])

    if not skill_dirs:
        return []

    # For each skill directory, check if SKILL.md exists and download it
    skill_md_paths = []
    for skill_dir_path in skill_dirs:
        # Construct SKILL.md path using PurePosixPath for safe, standardized path operations
        skill_dir = PurePosixPath(skill_dir_path)
        skill_md_path = str(skill_dir / "SKILL.md")
        skill_md_paths.append((skill_dir_path, skill_md_path))

    paths_to_download = [skill_md_path for _, skill_md_path in skill_md_paths]
    responses = await backend.adownload_files(paths_to_download)

    # Parse each downloaded SKILL.md
    for (skill_dir_path, skill_md_path), response in zip(skill_md_paths, responses, strict=True):
        if response.error:
            # Skill doesn't have a SKILL.md, skip it
            continue

        if response.content is None:
            logger.warning("Downloaded skill file %s has no content", skill_md_path)
            continue

        try:
            content = response.content.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.warning("Error decoding %s: %s", skill_md_path, e)
            continue

        # Extract directory name from path using PurePosixPath
        directory_name = PurePosixPath(skill_dir_path).name

        # Parse metadata
        skill_metadata = _parse_skill_metadata(
            content=content,
            skill_path=skill_md_path,
            directory_name=directory_name,
        )
        if skill_metadata:
            skills.append(skill_metadata)

    return skills


SKILLS_SYSTEM_PROMPT = """

## Skills System

You have access to a skills library that provides specialized capabilities and domain knowledge.

{skills_locations}

**Available Skills:**

{skills_list}

**How to Use Skills (Progressive Disclosure):**

Skills follow a **progressive disclosure** pattern - you see their name and description above, but only read full instructions when needed:

1. **Recognize when a skill applies**: Check if the user's task matches a skill's description
2. **Read the skill's full instructions**: Use the path shown in the skill list above
3. **Follow the skill's instructions**: SKILL.md contains step-by-step workflows, best practices, and examples
4. **Access supporting files**: Skills may include helper scripts, configs, or reference docs - use absolute paths

**When to Use Skills:**
- User's request matches a skill's domain (e.g., "research X" -> web-research skill)
- You need specialized knowledge or structured workflows
- A skill provides proven patterns for complex tasks

**Executing Skill Scripts:**
Skills may contain Python scripts or other executable files. Always use absolute paths from the skill list.

**Example Workflow:**

User: "Can you research the latest developments in quantum computing?"

1. Check available skills -> See "web-research" skill with its path
2. Read the skill using the path shown
3. Follow the skill's research workflow (search -> organize -> synthesize)
4. Use any helper scripts with absolute paths

Remember: Skills make you more capable and consistent. When in doubt, check if a skill exists for the task!
"""


class SkillsMiddleware(AgentMiddleware):
    """Middleware for loading and exposing agent skills to the system prompt.

    Loads skills from backend sources and injects them into the system prompt
    using progressive disclosure (metadata first, full content on demand).

    Skills are loaded in source order with later sources overriding earlier ones.

    Example:
        ```python
        from deepagents.backends.filesystem import FilesystemBackend

        backend = FilesystemBackend(root_dir="/path/to/skills")
        middleware = SkillsMiddleware(
            backend=backend,
            sources=[
                "/path/to/skills/user/",
                "/path/to/skills/project/",
            ],
        )
        ```

    Args:
        backend: Backend instance for file operations
        sources: List of skill source paths. Source names are derived from the last path component.
    """

    state_schema = SkillsState

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        sources: list[str],
        max_loaded_skills: int = 10,
    ) -> None:
        """Initialize the skills middleware.

        Args:
            backend: Backend instance or factory function that takes runtime and returns a backend.
                     Use a factory for StateBackend: `lambda rt: StateBackend(rt)`
            sources: List of skill source paths (e.g., ["/skills/user/", "/skills/project/"]).
            max_loaded_skills: Maximum number of simultaneously loaded skills. Defaults to 10.
        """
        self._backend = backend
        self.sources = sources
        self.system_prompt_template = SKILLS_SYSTEM_PROMPT
        self._max_loaded_skills = max_loaded_skills
        # V2: Create tools for skill lifecycle management
        self.tools = [
            self._create_load_skill_tool(),
            self._create_unload_skill_tool(),
        ]

    def _get_backend(self, state: SkillsState, runtime: Runtime, config: RunnableConfig) -> BackendProtocol:
        """Resolve backend from instance or factory.

        Args:
            state: Current agent state.
            runtime: Runtime context for factory functions.
            config: Runnable config to pass to backend factory.

        Returns:
            Resolved backend instance
        """
        if callable(self._backend):
            # Construct an artificial tool runtime to resolve backend factory
            tool_runtime = ToolRuntime(
                state=state,
                context=runtime.context,
                stream_writer=runtime.stream_writer,
                store=runtime.store,
                config=config,
                tool_call_id=None,
            )
            backend = self._backend(tool_runtime)
            if backend is None:
                raise AssertionError("SkillsMiddleware requires a valid backend instance")
            return backend

        return self._backend

    def _get_backend_from_runtime(self, runtime: "ToolRuntime[None, SkillsState]") -> "BackendProtocol":
        """从 ToolRuntime 中解析 backend 实例，用于工具函数中。"""
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def _format_skills_locations(self) -> str:
        """Format skills locations for display in system prompt."""
        locations = []
        for i, source_path in enumerate(self.sources):
            name = PurePosixPath(source_path.rstrip("/")).name.capitalize()
            suffix = " (higher priority)" if i == len(self.sources) - 1 else ""
            locations.append(f"**{name} Skills**: `{source_path}`{suffix}")
        return "\n".join(locations)

    def _format_skills_list(
        self,
        skills: list[SkillMetadata],
        loaded: list[str],
        resources: dict[str, list["ResourceMetadata"]],
    ) -> str:
        """Format skills metadata for display in system prompt (V2 enhanced)."""
        if not skills:
            paths = [f"{source_path}" for source_path in self.sources]
            return f"(No skills available yet. You can create skills in {' or '.join(paths)})"

        lines = []
        loaded_set = set(loaded)

        for skill in skills:
            name = skill["name"]
            annotations = _format_skill_annotations(skill)
            status = " [Loaded]" if name in loaded_set else ""
            desc_line = f"- **{name}**{status}: {skill['description']}"
            if annotations:
                desc_line += f" ({annotations})"

            skill_lines = [desc_line]

            if skill["allowed_tools"]:
                skill_lines.append(f"  -> Recommended tools: {', '.join(skill['allowed_tools'])}")

            if name in loaded_set:
                skill_resources = resources.get(name, [])
                if skill_resources:
                    resource_summary = _format_resource_summary(skill_resources)
                    skill_lines.append(f"  -> Resources: {resource_summary}")

            if name not in loaded_set:
                skill_lines.append(f'  -> Use `load_skill("{name}")` to read full instructions')

            lines.append("\n".join(skill_lines))

        return "\n".join(lines)

    def modify_request(self, request: ModelRequest) -> ModelRequest:
        """Inject skills documentation into a model request's system message.

        Args:
            request: Model request to modify

        Returns:
            New model request with skills documentation injected into system message
        """
        skills_metadata = request.state.get("skills_metadata", [])
        skills_loaded = request.state.get("skills_loaded", [])
        skill_resources = request.state.get("skill_resources", {})
        skills_locations = self._format_skills_locations()
        skills_list = self._format_skills_list(skills_metadata, skills_loaded, skill_resources)

        skills_section = self.system_prompt_template.format(
            skills_locations=skills_locations,
            skills_list=skills_list,
        )

        new_system_message = append_to_system_message(request.system_message, skills_section)

        return request.override(system_message=new_system_message)

    def before_agent(self, state: SkillsState, runtime: Runtime, config: RunnableConfig) -> SkillsStateUpdate | None:
        """Load skills metadata before agent execution (synchronous).

        Runs before each agent interaction to discover available skills from all
        configured sources. Re-loads on every call to capture any changes.

        Skills are loaded in source order with later sources overriding
        earlier ones if they contain skills with the same name (last one wins).

        Args:
            state: Current agent state.
            runtime: Runtime context.
            config: Runnable config.

        Returns:
            State update with `skills_metadata` populated, or `None` if already present
        """
        # Skip if skills_metadata is already present in state (even if empty)
        if "skills_metadata" in state:
            return None

        # Resolve backend (supports both direct instances and factory functions)
        backend = self._get_backend(state, runtime, config)
        all_skills: dict[str, SkillMetadata] = {}

        # Load skills from each source in order
        # Later sources override earlier ones (last one wins)
        for source_path in self.sources:
            source_skills = _list_skills(backend, source_path)
            for skill in source_skills:
                all_skills[skill["name"]] = skill

        skills = list(all_skills.values())
        return SkillsStateUpdate(
            skills_metadata=skills,
            skills_loaded=[],
            skill_resources={},
        )

    async def abefore_agent(self, state: SkillsState, runtime: Runtime, config: RunnableConfig) -> SkillsStateUpdate | None:
        """Load skills metadata before agent execution (async).

        Runs before each agent interaction to discover available skills from all
        configured sources. Re-loads on every call to capture any changes.

        Skills are loaded in source order with later sources overriding
        earlier ones if they contain skills with the same name (last one wins).

        Args:
            state: Current agent state.
            runtime: Runtime context.
            config: Runnable config.

        Returns:
            State update with `skills_metadata` populated, or `None` if already present
        """
        # Skip if skills_metadata is already present in state (even if empty)
        if "skills_metadata" in state:
            return None

        # Resolve backend (supports both direct instances and factory functions)
        backend = self._get_backend(state, runtime, config)
        all_skills: dict[str, SkillMetadata] = {}

        # Load skills from each source in order
        # Later sources override earlier ones (last one wins)
        for source_path in self.sources:
            source_skills = await _alist_skills(backend, source_path)
            for skill in source_skills:
                all_skills[skill["name"]] = skill

        skills = list(all_skills.values())
        return SkillsStateUpdate(
            skills_metadata=skills,
            skills_loaded=[],
            skill_resources={},
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Inject skills documentation into the system prompt.

        Args:
            request: Model request being processed
            handler: Handler function to call with modified request

        Returns:
            Model response from handler
        """
        modified_request = self.modify_request(request)
        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Inject skills documentation into the system prompt (async version).

        Args:
            request: Model request being processed
            handler: Async handler function to call with modified request

        Returns:
            Model response from handler
        """
        modified_request = self.modify_request(request)
        return await handler(modified_request)

    # ==========================================================================
    # V2: Tool methods for skill lifecycle management
    # ==========================================================================

    def _create_load_skill_tool(self) -> "StructuredTool":
        """创建 load_skill 工具。"""
        def sync_load_skill(
            skill_name: str,
            runtime: "ToolRuntime[None, SkillsState]",
        ) -> "Command | str":
            """Load a skill's full instructions and discover its resources."""
            backend = self._get_backend_from_runtime(runtime)
            return self._execute_load_skill(backend, skill_name, runtime)

        async def async_load_skill(
            skill_name: str,
            runtime: "ToolRuntime[None, SkillsState]",
        ) -> "Command | str":
            """Load a skill's full instructions and discover its resources (async)."""
            backend = self._get_backend_from_runtime(runtime)
            return await self._aexecute_load_skill(backend, skill_name, runtime)

        return StructuredTool.from_function(
            name="load_skill",
            description="Load a skill's full instructions and discover its resources. Use this instead of read_file when you need to activate a skill.",
            func=sync_load_skill,
            coroutine=async_load_skill,
        )

    def _execute_load_skill(
        self,
        backend: "BackendProtocol",
        skill_name: str,
        runtime: "ToolRuntime[None, SkillsState]",
    ) -> "Command | str":
        """load_skill 核心逻辑（同步版本）。"""
        state = runtime.state
        skills_metadata = state.get("skills_metadata", [])
        # 浅拷贝 dict 即可——后续代码仅添加/替换 key，不会原地修改已有 value 的内容
        skill_resources = dict(state.get("skill_resources", {}))
        loaded_skills = list(state.get("skills_loaded", []))

        target_skill = None
        for skill in skills_metadata:
            if skill["name"] == skill_name:
                target_skill = skill
                break

        if target_skill is None:
            available = [s["name"] for s in skills_metadata]
            return f"Error: Skill '{skill_name}' not found. Available skills: {', '.join(available)}"

        if skill_name in loaded_skills:
            return f"Skill '{skill_name}' is already loaded. Its instructions are already active."

        if len(loaded_skills) >= self._max_loaded_skills:
            return (
                f"Error: Cannot load skill '{skill_name}'. "
                f"Maximum number of simultaneously loaded skills reached ({self._max_loaded_skills}). "
                f"Currently loaded: {', '.join(loaded_skills)}. "
                f'Use `unload_skill("skill-name")` to unload a skill you no longer need, then retry loading.'
            )

        responses = backend.download_files([target_skill["path"]])
        response = responses[0]

        if response.error or response.content is None:
            return f"Error: Failed to read skill file at {target_skill['path']}: {response.error}"

        if len(response.content) > MAX_SKILL_FILE_SIZE:
            return f"Error: Skill file at {target_skill['path']} exceeds maximum size ({MAX_SKILL_FILE_SIZE} bytes)"

        try:
            file_content = response.content.decode("utf-8")
        except UnicodeDecodeError as e:
            return f"Error: Failed to decode skill file: {e}"

        if skill_name not in skill_resources:
            from pathlib import PurePosixPath
            skill_dir = str(PurePosixPath(target_skill["path"]).parent)
            skill_resources[skill_name] = _discover_resources(backend, skill_dir, skill_name)

        result_parts = [file_content]
        resources = skill_resources.get(skill_name, [])
        if resources:
            result_parts.append("\n\n---\n**Skill Resources:**\n")
            for resource in resources:
                result_parts.append(f"- [{resource['type']}] `{resource['path']}`")

        result_content = "\n".join(result_parts)
        loaded_skills.append(skill_name)

        # messages 放在 update 字典内部，这是 LangGraph Command 的标准模式
        return Command(
            update={
                "skills_loaded": loaded_skills,
                "skill_resources": skill_resources,
                "messages": [ToolMessage(content=result_content, tool_call_id=runtime.tool_call_id)],
            },
        )

    async def _aexecute_load_skill(
        self,
        backend: "BackendProtocol",
        skill_name: str,
        runtime: "ToolRuntime[None, SkillsState]",
    ) -> "Command | str":
        """load_skill 核心逻辑（异步版本）。"""
        state = runtime.state
        skills_metadata = state.get("skills_metadata", [])
        skill_resources = dict(state.get("skill_resources", {}))
        loaded_skills = list(state.get("skills_loaded", []))

        target_skill = None
        for skill in skills_metadata:
            if skill["name"] == skill_name:
                target_skill = skill
                break

        if target_skill is None:
            available = [s["name"] for s in skills_metadata]
            return f"Error: Skill '{skill_name}' not found. Available skills: {', '.join(available)}"

        if skill_name in loaded_skills:
            return f"Skill '{skill_name}' is already loaded. Its instructions are already active."

        if len(loaded_skills) >= self._max_loaded_skills:
            return (
                f"Error: Cannot load skill '{skill_name}'. "
                f"Maximum number of simultaneously loaded skills reached ({self._max_loaded_skills}). "
                f"Currently loaded: {', '.join(loaded_skills)}. "
                f'Use `unload_skill("skill-name")` to unload a skill you no longer need, then retry loading.'
            )

        responses = await backend.adownload_files([target_skill["path"]])
        response = responses[0]

        if response.error or response.content is None:
            return f"Error: Failed to read skill file at {target_skill['path']}: {response.error}"

        if len(response.content) > MAX_SKILL_FILE_SIZE:
            return f"Error: Skill file at {target_skill['path']} exceeds maximum size ({MAX_SKILL_FILE_SIZE} bytes)"

        try:
            file_content = response.content.decode("utf-8")
        except UnicodeDecodeError as e:
            return f"Error: Failed to decode skill file: {e}"

        if skill_name not in skill_resources:
            from pathlib import PurePosixPath
            skill_dir = str(PurePosixPath(target_skill["path"]).parent)
            skill_resources[skill_name] = await _adiscover_resources(backend, skill_dir, skill_name)

        result_parts = [file_content]
        resources = skill_resources.get(skill_name, [])
        if resources:
            result_parts.append("\n\n---\n**Skill Resources:**\n")
            for resource in resources:
                result_parts.append(f"- [{resource['type']}] `{resource['path']}`")

        result_content = "\n".join(result_parts)
        loaded_skills.append(skill_name)

        return Command(
            update={
                "skills_loaded": loaded_skills,
                "skill_resources": skill_resources,
                "messages": [ToolMessage(content=result_content, tool_call_id=runtime.tool_call_id)],
            },
        )

    def _create_unload_skill_tool(self) -> "StructuredTool":
        """创建 unload_skill 工具。"""
        def sync_unload_skill(
            skill_name: str,
            runtime: "ToolRuntime[None, SkillsState]",
        ) -> "Command | str":
            """Unload a previously loaded skill to free up a loading slot."""
            return self._execute_unload_skill(skill_name, runtime)

        async def async_unload_skill(
            skill_name: str,
            runtime: "ToolRuntime[None, SkillsState]",
        ) -> "Command | str":
            """Unload a previously loaded skill to free up a loading slot (async)."""
            return self._execute_unload_skill(skill_name, runtime)

        return StructuredTool.from_function(
            name="unload_skill",
            description="Unload a previously loaded skill to free up a loading slot.",
            func=sync_unload_skill,
            coroutine=async_unload_skill,
        )

    def _execute_unload_skill(
        self,
        skill_name: str,
        runtime: "ToolRuntime[None, SkillsState]",
    ) -> "Command | str":
        """unload_skill 核心逻辑（同步/异步共用，不涉及 I/O）。"""
        state = runtime.state
        loaded_skills = list(state.get("skills_loaded", []))
        skill_resources = dict(state.get("skill_resources", {}))

        if skill_name not in loaded_skills:
            loaded_list = ', '.join(loaded_skills) if loaded_skills else '(none)'
            return f"Error: Skill '{skill_name}' is not currently loaded. Currently loaded skills: {loaded_list}."

        loaded_skills.remove(skill_name)
        skill_resources.pop(skill_name, None)

        remaining = len(loaded_skills)
        available = self._max_loaded_skills - remaining

        return Command(
            update={
                "skills_loaded": loaded_skills,
                "skill_resources": skill_resources,
                "messages": [
                    ToolMessage(
                        content=(
                            f"Skill '{skill_name}' has been unloaded. "
                            f"Currently loaded: {remaining}/{self._max_loaded_skills} ({available} slot(s) available). "
                            f"Note: The skill's instructions from the previous load_skill call are still in the conversation history "
                            f"but will no longer be marked as [Loaded] in the skills list."
                        ),
                        tool_call_id=runtime.tool_call_id,
                    ),
                ],
            },
        )



__all__ = ["SkillMetadata", "SkillsMiddleware", "ResourceMetadata"]
