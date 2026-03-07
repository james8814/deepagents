# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Deep Agents is a batteries-included AI agent harness built on LangGraph. It provides planning, filesystem access, shell execution, and sub-agent spawning capabilities out of the box.

**Documentation**: https://docs.langchain.com/oss/python/deepagents/overview

## Monorepo Structure

```
deepagents/
├── libs/
│   ├── deepagents/      # Core SDK (published as `deepagents`)
│   ├── cli/             # Terminal UI (published as `deepagents-cli`)
│   ├── acp/             # Agent Context Protocol (published as `deepagents-acp`)
│   ├── harbor/          # Evaluation/benchmark framework
│   └── partners/daytona/ # Daytona sandbox integration
├── examples/            # Working agent examples
└── docs/                # Technical documentation
```

**Package Dependencies**:
```
deepagents-cli ──> deepagents
deepagents-acp ──> deepagents
deepagents-harbor ──> deepagents, deepagents-cli
langchain-daytona ──> deepagents
```

When modifying `libs/deepagents`, you must also run CLI tests since the CLI depends on the SDK.

## Build & Test Commands

Navigate to the package directory (`cd libs/deepagents` or `cd libs/cli`) then:

```bash
# Unit tests (no network)
make test
uv run --group test pytest -vvv --disable-socket --allow-unix-socket tests/unit_tests/

# Integration tests (network allowed, 30s timeout, parallel)
make integration_test
uv run --group test pytest -n auto -vvv --timeout 30 tests/integration_tests/

# Run specific test file
make test TEST_FILE=tests/unit_tests/middleware/test_skills.py

# Run tests in watch mode
make test_watch

# Run benchmark tests
make benchmark

# Lint and format
make lint
make format

# Type checking (CLI only - SDK does not use type checking)
make type

# Coverage
make coverage
```

**Pre-commit hooks**: Run `pre-commit install` to install. Hooks run format/lint on commit.

## Architecture

### Core SDK (`libs/deepagents/deepagents/`)

**Main entry point**: `create_deep_agent()` in `graph.py`

**Default model**: `claude-sonnet-4-5-20250929` (20k tokens)

**Middleware Stack** (execution order in `create_deep_agent`):
1. `TodoListMiddleware` - `write_todos` / `read_todos`
2. `MemoryMiddleware` (optional) - Loads `AGENTS.md` into system prompt
3. `SkillsMiddleware` (optional) - Loads `SKILL.md` metadata (progressive disclosure)
4. `FilesystemMiddleware` - File ops: `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep`, `execute`
5. `SubAgentMiddleware` - `task` tool for spawning sub-agents
6. `SummarizationMiddleware` - Auto-summarization at 85% context or 100k tokens
7. `AnthropicPromptCachingMiddleware` - Prompt caching
8. `PatchToolCallsMiddleware` - Fixes dangling tool calls
9. `HumanInTheLoopMiddleware` (optional) - Tool approval before execution
10. User-provided middleware (appended)

**File Uploads**: Files uploaded via CLI `/upload <path>` command are stored in `/uploads/`. The upload system includes:
- **Security validation**: File type detection using magic bytes (via `puremagic`), 100MB size limit, unauthorized type blocking
- **Type-specific guidance**: After upload, CLI shows guidance based on file type:
  - Text files: Use `ls /uploads` and `read_file` to access
  - Binary files (images/audio/video): Use `execute` with external tools
  - PDFs: Use `execute` with `pdftotext` or similar
  - Archives: Use `execute` with `unzip`, `tar`, etc.
  - Office documents: Use `execute` with `pandoc`
- **Large file handling**: Tool results >20k tokens are written to `/large_tool_results/{tool_call_id}`

**Backends** (pluggable storage/execution):
- `BackendProtocol` - Base protocol: `ls_info`, `read`, `write`, `edit`, `grep_raw`, `glob_info`
- `SandboxBackendProtocol` - Extends with `execute()` and `id` property
- `StateBackend` - In-memory via LangGraph state (default, ephemeral)
- `FilesystemBackend` - Local disk storage
- `StoreBackend` - LangGraph store persistence (cross-session)
- `LocalShellBackend` - Local shell execution
- `CompositeBackend` - Routes by path prefix (longest-match wins)

**Backend Factory Pattern**:
```python
# StateBackend needs runtime context - use factory
backend = lambda rt: StateBackend(rt)
# Or direct instance for stateless backends
backend = FilesystemBackend(root_dir="/workspace")
```

**CompositeBackend Routing**:
```python
composite = CompositeBackend(
    default=StateBackend(runtime),
    routes={
        "/memories/": StoreBackend(runtime),
        "/conversation_history/": fs_backend,
    }
)
```

### Sub-Agent Mechanism (`subagents.py`)

**State Isolation**: When invoking sub-agents, these keys are excluded from parent state:
```python
_EXCLUDED_STATE_KEYS = {"messages", "todos", "structured_response", "skills_metadata", "memory_contents"}
```

**General-Purpose Subagent**: Always created by default with its own middleware stack (TodoList, Filesystem, Summarization, AnthropicCache, PatchToolCalls).

**Task Tool Flow**:
1. Main agent calls `task(description, subagent_type)`
2. `SubAgentMiddleware` filters state, injects `HumanMessage(description)`
3. Sub-agent runs independently with its own middleware
4. Final message extracted as `ToolMessage` returned to parent

### Skills System (`skills.py`)

**Structure**:
```
/skills/user/web-research/
├── SKILL.md          # YAML frontmatter + instructions
└── helper.py         # Optional supporting files
```

**SKILL.md Format**:
```yaml
---
name: web-research
description: Structured approach to web research
license: MIT
---
```

**V2 Features** (SkillsMiddleware V2 - 2026-02-18):
- **`load_skill` tool**: Load full skill instructions and discover resources
- **`unload_skill` tool**: Unload skill to free up context space
- **`[Loaded]` marker**: System prompt shows which skills are loaded
- **Context budget**: `max_loaded_skills=10` limits simultaneously loaded skills
- **Resource discovery**: Auto-scans `scripts/`, `references/`, `assets/` directories
- **`expose_dynamic_tools`**: `bool = False` — controls whether `load_skill`/`unload_skill` tools are exposed
- **`allowed_skills`**: `list[str] | None = None` — optional allowlist to filter visible skills by name

**Per-SubAgent Skill Filtering** (2026-03-07):
- `SubAgent` TypedDict has `skills_allowlist: NotRequired[list[str]]` field
- `create_deep_agent` wires `skills_allowlist` into `SkillsMiddleware(allowed_skills=...)`
- Enables per-SubAgent skill visibility: e.g., research_agent sees 4 skills, analysis_agent sees 6
- Default `None` preserves directory-level scan behavior (backward compatible)

**Progressive Disclosure**: Only metadata (name + description) injected at startup. Agent reads full `SKILL.md` via `load_skill()` when needed.

**Source Priority**: Later sources override earlier for same skill name (last one wins).

**V2 State Fields**:
- `skills_loaded`: List of loaded skill names
- `skill_resources`: Cached resource metadata per skill

### CLI (`libs/cli/deepagents_cli/`)

**Entry Point**: `create_cli_agent()` in `agent.py`

Textual-based terminal UI with:
- `app.py` - Main Textual application
- `widgets/` - UI components (messages, chat_input, approval, tool_widgets)
- `integrations/` - Third-party (daytona, modal, runloop, langsmith)
- `skills/` - Skills system
- `backends.py` - `CLIShellBackend` with per-command timeout support

**HITL Tool Approval** (when `auto_approve=False`):
- `execute`, `write_file`, `edit_file`, `web_search`, `fetch_url`, `task`
- Custom description formatters for each tool

**HITL Approval Flow**: When `interrupt_on` includes a tool, the UI shows an approval dialog before execution. User can approve, deny, or edit the tool call.

**Local vs Remote Mode**:
- **Local**: `CLIShellBackend` + `FilesystemBackend` + `LocalContextMiddleware`
- **Remote**: Sandbox backend (Modal/Daytona/Runloop) handles file ops + execute

**Qwen/DashScope Support** (content-builder-agent):
```bash
export DASHSCOPE_API_KEY="your-key"
export MODEL_PROVIDER="dashscope"
export DASHSCOPE_MODEL="qwen-plus"
./run_test_env.sh "Your task"
```

### Summarization (`summarization.py`)

**Storage**: `/conversation_history/{thread_id}.md` (appended on each summarization event)

**Environment Variables**:
- `DEEPAGENTS_FALLBACK_TRIGGER_TOKENS` (default: 100,000)
- `DEEPAGENTS_FALLBACK_KEEP_MESSAGES` (default: 6)

**Argument Truncation**: Configurable via `truncate_args_settings` - truncates `write_file`/`edit_file` args in old messages before summarization.

## Code Style

- **Type hints required** on all functions (avoid `Any`)
- **Google-style docstrings** with Args section
- **Line length**: 150 (deepagents), 100 (cli/acp/harbor)
- **American English** spelling
- **Single backticks** for inline code in docstrings

```python
def send_email(to: str, msg: str, *, priority: str = "normal") -> bool:
    """Send an email to a recipient with specified priority.

    Args:
        to: The email address of the recipient.
        msg: The message body to send.
        priority: Email priority level.

    Returns:
        `True` if email was sent successfully, `False` otherwise.
    """
```

## Testing Guidelines

**Test structure**:
- `tests/unit_tests/` - No network calls (enforced by `pytest-socket`)
- `tests/integration_tests/` - Network allowed, 30s timeout, parallel execution

**Test patterns**:
- Use fixtures/mocks for external dependencies
- Tests must be deterministic (no flaky tests)
- Avoid mocks when possible; test actual implementation
- Mark with appropriate pytest markers if needed

## CI/CD

**PR title format** (Conventional Commits):
```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
Scopes: `deepagents`, `sdk`, `deepagents-cli`, `cli`, `harbor`, `acp`, `examples`, `deps`, `daytona`

## Public API Stability

**CRITICAL**: Preserve function signatures, argument positions, and names for exported APIs.

- Check `__init__.py` exports before making changes
- Use keyword-only arguments for new parameters: `*, new_param: str = "default"`
- Mark experimental features with `!!! warning` in docstrings

## Security

**"Trust the LLM" Model**: Deep Agents follows a trust-the-LLM model. Enforce boundaries at the tool/sandbox level, not by expecting the model to self-police.

**Path Traversal Protection** (`FilesystemBackend.virtual_mode`):
- Prohibits `..` and `~` traversal
- All paths must resolve within `root_dir`
- Uses `os.O_NOFOLLOW` to prevent symlink attacks

**Sandbox Isolation**:
- **Remote** (Daytona/Modal/Runloop): Strong isolation in containers
- **Local** (`CLIShellBackend`): No isolation - use with HITL approval

**HITL Approval**: Configure `interrupt_on` in `create_deep_agent()` for destructive tools (`execute`, `write_file`, `edit_file`).

**Standardized Error Codes**: `file_not_found`, `permission_denied`, `is_directory`, `invalid_path` - LLM-actionable error reporting.

## Key Implementation Details

**File Result Eviction** (`FilesystemMiddleware`): Tool results >20k tokens are written to `/large_tool_results/{tool_call_id}` with preview + file reference.

**Message ID Requirement**: All messages must have IDs for proper state management (see `_ensure_message_ids` in summarization).

**Backend Download vs Read**: Use `download_files()` for raw content (editing), `read()` returns line-numbered format (for LLM consumption).

**StateBackend Uploads**: Use `upload_files()` from `deepagents.upload_adapter` for universal file upload support.

**Thread ID Extraction**: Summarization extracts `thread_id` from LangGraph config, falls back to generated session ID.

**SkillsMiddleware V2** (2026-02-18, enhanced 2026-03-07):
- Full implementation: `docs/skillsmiddleware_docs/SkillsMiddleware_V2_核查报告.md`
- Design document: `docs/skillsmiddleware_docs/DeepAgents_SkillsMiddleware_V2_升级设计方案_final.md`
- Key changes: `libs/deepagents/deepagents/middleware/skills.py` (+442 lines)
- CLI compatibility: Fully backward compatible, no changes required
- External team guide: `docs/api/EXTERNAL_TEAM_API_GUIDE.md`
- Review report: `docs/integrations/skills/v2_review_report.md`
- Dynamic loading guide: `docs/integrations/skills/dynamic_loading_guide.md`

**Upload Adapter V5.0** (2026-02-27):
- Location: `libs/deepagents/deepagents/upload_adapter.py`
- Purpose: Universal file upload for any backend
- Features: Auto strategy selection, overwrite detection, WeakKeyDictionary locks
- Export: `from deepagents import upload_files, UploadResult`
- Guide: `docs/UPLOAD_ADAPTER_GUIDE.md`

## Key Links

- **LangGraph docs**: https://docs.langchain.com/oss/python/langgraph/overview
- **API Reference**: https://reference.langchain.com/python/deepagents/
- **Textual docs** (for CLI): https://textual.textualize.io/
- **UV docs**: https://docs.astral.sh/uv/

**V2 Documentation**:
- **SkillsMiddleware V2 Design**: `docs/skillsmiddleware_docs/DeepAgents_SkillsMiddleware_V2_升级设计方案_final.md`
- **V2 Verification Report**: `docs/skillsmiddleware_docs/SkillsMiddleware_V2_核查报告.md`
- **Phase 3 Code Review**: `docs/skillsmiddleware_docs/Phase3_CodeReview_Report.md`
- **SDK Upgrade Guide**: `docs/SDK_UPGRADE_GUIDE.md`

**V5.0 Upload Adapter Documentation**:
- **User Guide**: `docs/UPLOAD_ADAPTER_GUIDE.md`
- **Implementation**: `docs/attachment_function_docs/UNIVERSAL_UPLOAD_ADAPTER_V5.md`
- **Final Report**: `docs/attachment_function_docs/FINAL_DELIVERY_REPORT.md`
