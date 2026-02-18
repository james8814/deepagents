# DeepAgents SkillsMiddleware V2 实施方案

**版本**: 2.1
**日期**: 2026-02-18
**状态**: 生产就绪
**基于**: [DeepAgents SkillsMiddleware V2 升级设计方案（最终修订版）](./DeepAgents_SkillsMiddleware_V2_升级设计方案_final_修订.md)

---

**修订历史**：
| 版本 | 日期 | 变更说明 |
| :--- | :--- | :--- |
| 2.0 | 2026-02-18 | 初始版本 |
| 2.1 | 2026-02-18 | 根据评审意见补充 5 条注释和错误处理矩阵（P3 非阻塞性改进） |

> **注**：本实施方案聚焦于"如何实现"。设计决策的背景分析、行业对比、扩展路线图等"Why"层面的内容，请参考 [DeepAgents SkillsMiddleware V2 升级设计方案（最终修订版）](./DeepAgents_SkillsMiddleware_V2_升级设计方案_final_修订.md) 对应章节。

---

## 一、实施方案概述

### 1.1 方案目标

本实施方案旨在将 `SkillsMiddleware` 从 V1 版本升级到 V2 版本，实现：
1. **技能加载状态追踪**：追踪哪些技能已被 Agent 实际加载
2. **延迟资源发现**：按需扫描技能资源目录，降低 I/O 开销
3. **专用工具**：`load_skill` 和 `unload_skill` 工具，完整的技能生命周期管理
4. **上下文预算管理**：控制同时加载的技能数量，防止上下文膨胀
5. **简化设计**：废除 `RESTRICT` 模式和描述层预算，降低复杂度

### 1.2 设计原则回顾

| 优先级 | 原则 | 实施含义 |
| :---: | :--- | :--- |
| P0 | **向后兼容性** | 所有现有 `SKILL.md` 文件无需修改，V1 API 保持不变 |
| P0 | **最小侵入性** | 所有变更限制在 `skills.py` 文件内部 |
| P1 | **遵循既有模式** | 复用 DeepAgents 框架的 BackendProtocol、PrivateStateAttr、Command 等模式 |
| P2 | **模块化与可扩展性** | 为 hooks、context: fork 等高级功能预留扩展点 |

### 1.3 LangGraph 框架机制对齐

本方案严格遵循 LangGraph/LangChain 框架的核心机制：

#### 1.3.1 AgentMiddleware Hook 机制

```python
# LangGraph 定义的 AgentMiddleware 基类
class AgentMiddleware:
    def before_agent(self, state, runtime, config): ...
    def wrap_model_call(self, request, handler): ...
    def wrap_tool_call(self, request, handler): ...  # V2 不使用
```

**V2 Hook 使用策略**：
- ✅ `before_agent`：技能发现、状态初始化
- ✅ `wrap_model_call`：系统提示注入（加载状态标记）
- ❌ `wrap_tool_call`：因废除 RESTRICT 模式，不使用

#### 1.3.2 PrivateStateAttr 状态隔离机制

```python
# LangGraph 状态字段标记机制
from langchain.agents.middleware.types import PrivateStateAttr

class SkillsState(AgentState):
    skills_loaded: Annotated[list[str], PrivateStateAttr]  # 不传播到父/子 Agent
    skill_resources: Annotated[dict[str, list[ResourceMetadata]], PrivateStateAttr]
```

**设计含义**：
- `PrivateStateAttr` 标记的字段不会在 SubAgent 调用时传播
- 确保主 Agent 和 SubAgent 的技能加载状态完全隔离

#### 1.3.3 Command 状态更新机制

```python
# LangGraph Command 对象用于工具内状态更新
from langgraph.types import Command

return Command(
    update={
        "skills_loaded": loaded_skills,
        "skill_resources": skill_resources,
    },
    messages=[ToolMessage(content=..., tool_call_id=...)]
)
```

**设计含义**：
- `Command.update` 中的字段会合并到 Agent State
- `Command.messages` 携带 ToolMessage 作为工具响应
- 与 `FilesystemMiddleware.write_file` 模式完全一致

### 1.4 DeepAgents 设计原理对齐

#### 1.4.1 BackendProtocol 抽象

```python
# DeepAgents 统一的 Backend 接口
from deepagents.backends.protocol import BackendProtocol

# V2 使用模式
backend = self._get_backend(state, runtime, config)
backend.download_files([path])  # 读取 SKILL.md
backend.ls_info(skill_dir)       # 延迟资源发现
```

**设计含义**：
- 支持 StateBackend、FilesystemBackend、StoreBackend、CompositeBackend
- 支持 factory 模式：`lambda rt: StateBackend(rt)`

#### 1.4.2 渐进式披露模式

```
┌─────────────────────────────────────────┐
│  Level 1: 元数据（启动时加载）           │
│  • name + description                   │
│  • 所有技能都展示在系统提示中            │
├─────────────────────────────────────────┤
│  Level 2: 完整指令（load_skill 后加载）  │
│  • SKILL.md 全文                         │
│  • 资源摘要                              │
│  • 标记为 [Loaded]                       │
├─────────────────────────────────────────┤
│  Level 3: 资源文件（按需 read_file）     │
│  • scripts/*.py                         │
│  • references/*.md                      │
│  • assets/*                             │
└─────────────────────────────────────────┘
```

---

## 二、代码实现

### 2.1 新增类型定义

在 `skills.py` 文件顶部添加以下类型定义：

```python
from typing import Literal

# =============================================================================
# V2 新增类型定义
# =============================================================================

class ResourceMetadata(TypedDict):
    """技能资源文件的元数据。

    用于延迟发现策略，缓存技能目录下的资源文件信息。
    """
    path: str
    """资源文件在 backend 中的完整路径。"""
    type: Literal["script", "reference", "asset", "other"]
    """资源类型，基于所在目录名推断。"""
    skill_name: str
    """所属技能的名称。"""


class SkillsState(AgentState):
    """Skills 中间件的状态 schema。"""

    skills_metadata: NotRequired[Annotated[list[SkillMetadata], PrivateStateAttr]]
    """已发现的技能元数据列表。"""

    # V2 新增
    skills_loaded: NotRequired[Annotated[list[str], PrivateStateAttr]]
    """已加载（激活）的技能名称列表。

    当 Agent 通过 load_skill 工具读取了某个技能的完整 SKILL.md 内容后，
    该技能的名称会被添加到此列表中。此列表用于：
    1. 在系统提示中标记已加载的技能
    2. 避免重复加载同一技能
    3. 作为内容层预算（max_loaded_skills）的计数依据
    4. 作为 unload_skill 的操作目标
    """

    # V2 新增
    skill_resources: NotRequired[Annotated[dict[str, list[ResourceMetadata]], PrivateStateAttr]]
    """已发现的技能资源映射，键为技能名称。

    采用延迟发现策略：在 load_skill 被调用时按需扫描该技能的资源目录，
    结果缓存在此字段中。采用 dict 结构（而非 flat list）以支持按技能名称的 O(1) 查找。
    """


class SkillsStateUpdate(TypedDict):
    """Skills 中间件的状态更新。"""
    skills_metadata: list[SkillMetadata]
    skills_loaded: list[str]
    skill_resources: dict[str, list[ResourceMetadata]]
```

### 2.2 模块级常量

在 `MAX_SKILL_FILE_SIZE` 常量后添加：

```python
# V1 保留
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# V2 新增
RESOURCE_TYPE_MAP: dict[str, Literal["script", "reference", "asset"]] = {
    "scripts": "script",
    "references": "reference",
    "assets": "asset",
}
```

### 2.3 延迟资源发现函数

在 `_list_skills` 和 `_alist_skills` 函数后添加以下辅助函数：

```python
# =============================================================================
# V2 新增：延迟资源发现
# =============================================================================


def _discover_resources(
    backend: BackendProtocol,
    skill_dir: str,
    skill_name: str,
) -> list[ResourceMetadata]:
    """发现技能目录下的资源文件（同步版本）。

    扫描技能目录下的 scripts/, references/, assets/ 子目录（仅第一层），
    以及目录根级别的非 SKILL.md 文件。

    Args:
        backend: Backend 实例
        skill_dir: 技能目录路径
        skill_name: 技能名称

    Returns:
        发现的资源元数据列表
    """
    resources: list[ResourceMetadata] = []

    try:
        items = backend.ls_info(skill_dir)
    except Exception:
        logger.warning(
            "Failed to list resources for skill '%s' at %s",
            skill_name, skill_dir,
        )
        return resources

    for item in items:
        item_path = item["path"]
        item_name = PurePosixPath(item_path).name

        if item.get("is_dir"):
            # 仅扫描标准资源目录
            resource_type = RESOURCE_TYPE_MAP.get(item_name)
            if resource_type is None:
                continue  # 跳过非标准目录

            # 扫描资源目录内容（仅第一层，不递归）
            try:
                sub_items = backend.ls_info(item_path)
            except Exception:
                logger.warning("Failed to list resources in %s", item_path)
                continue

            for sub_item in sub_items:
                if not sub_item.get("is_dir"):
                    resources.append(ResourceMetadata(
                        path=sub_item["path"],
                        type=resource_type,
                        skill_name=skill_name,
                    ))
        else:
            # 根级别非 SKILL.md 文件（如 template.md）
            if item_name != "SKILL.md":
                resources.append(ResourceMetadata(
                    path=item_path,
                    type="other",
                    skill_name=skill_name,
                ))

    return resources


async def _adiscover_resources(
    backend: BackendProtocol,
    skill_dir: str,
    skill_name: str,
) -> list[ResourceMetadata]:
    """发现技能目录下的资源文件（异步版本）。

    与 _discover_resources 逻辑相同，但使用异步 backend API。
    """
    resources: list[ResourceMetadata] = []

    try:
        items = await backend.als_info(skill_dir)
    except Exception:
        logger.warning(
            "Failed to list resources for skill '%s' at %s",
            skill_name, skill_dir,
        )
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
                    resources.append(ResourceMetadata(
                        path=sub_item["path"],
                        type=resource_type,
                        skill_name=skill_name,
                    ))
        else:
            if item_name != "SKILL.md":
                resources.append(ResourceMetadata(
                    path=item_path,
                    type="other",
                    skill_name=skill_name,
                ))

    return resources
```

### 2.4 SkillsMiddleware.__init__ 扩展

修改 `__init__` 方法：

```python
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
        max_loaded_skills: Maximum number of skills that can be loaded simultaneously.
            Defaults to 10. Agent can use unload_skill to free up slots.
    """

    state_schema = SkillsState

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        sources: list[str],
        # V2 新增参数
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

        # V2 新增
        self._max_loaded_skills = max_loaded_skills

        # V2: 创建专用工具（与 FilesystemMiddleware 模式一致）
        self.tools = [
            self._create_load_skill_tool(),
            self._create_unload_skill_tool(),
        ]
```

### 2.5 before_agent / abefore_agent 扩展

修改 `before_agent` 和 `abefore_agent` 方法：

```python
# =============================================================================
# V2 修改：before_agent / abefore_agent
# =============================================================================

    def before_agent(
        self, state: SkillsState, runtime: Runtime, config: RunnableConfig,
    ) -> SkillsStateUpdate | None:
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
            State update with `skills_metadata` populated, or `None` if already present.
        """
        # 幂等检查：如果 skills_metadata 已存在，跳过
        if "skills_metadata" in state:
            return None

        backend = self._get_backend(state, runtime, config)
        all_skills: dict[str, SkillMetadata] = {}

        # Load skills from each source in order
        # Later sources override earlier ones (last one wins)
        for source_path in self.sources:
            source_skills = _list_skills(backend, source_path)
            for skill in source_skills:
                all_skills[skill["name"]] = skill

        return SkillsStateUpdate(
            skills_metadata=list(all_skills.values()),
            skills_loaded=[],               # V2: 初始化为空
            skill_resources={},             # V2: 初始化为空（延迟发现）
        )

    async def abefore_agent(
        self, state: SkillsState, runtime: Runtime, config: RunnableConfig,
    ) -> SkillsStateUpdate | None:
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
            State update with `skills_metadata` populated, or `None` if already present.
        """
        # 幂等检查：如果 skills_metadata 已存在，跳过
        if "skills_metadata" in state:
            return None

        backend = self._get_backend(state, runtime, config)
        all_skills: dict[str, SkillMetadata] = {}

        # Load skills from each source in order
        # Later sources override earlier ones (last one wins)
        for source_path in self.sources:
            source_skills = await _alist_skills(backend, source_path)
            for skill in source_skills:
                all_skills[skill["name"]] = skill

        return SkillsStateUpdate(
            skills_metadata=list(all_skills.values()),
            skills_loaded=[],
            skill_resources={},
        )
```

### 2.6 load_skill 工具实现

在 `modify_request` 方法后添加：

```python
# =============================================================================
# V2 新增：load_skill 工具
# =============================================================================

    def _get_backend_from_runtime(
        self, runtime: ToolRuntime[None, SkillsState],
    ) -> BackendProtocol:
        """从 ToolRuntime 中解析 backend 实例。

        用于工具函数中获取 backend，支持 factory 模式。

        Args:
            runtime: ToolRuntime 实例

        Returns:
            BackendProtocol 实例
        """
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def _create_load_skill_tool(self) -> BaseTool:
        """创建 load_skill 工具。"""

        def sync_load_skill(
            skill_name: Annotated[str, "Name of the skill to load from the available skills list."],
            runtime: ToolRuntime[None, SkillsState],
        ) -> Command | str:
            """Load a skill's full instructions and discover its resources.

            Use this instead of read_file when you need to activate a skill
            from the available skills list. Returns the complete SKILL.md
            content along with a summary of available resources.
            """
            backend = self._get_backend_from_runtime(runtime)
            return self._execute_load_skill(backend, skill_name, runtime)

        async def async_load_skill(
            skill_name: Annotated[str, "Name of the skill to load from the available skills list."],
            runtime: ToolRuntime[None, SkillsState],
        ) -> Command | str:
            """Load a skill's full instructions and discover its resources (async)."""
            backend = self._get_backend_from_runtime(runtime)
            return await self._aexecute_load_skill(backend, skill_name, runtime)

        return StructuredTool.from_function(
            name="load_skill",
            description=(
                "Load a skill's full instructions and discover its resources. "
                "Use this instead of read_file when you need to activate a skill "
                "from the available skills list."
            ),
            func=sync_load_skill,
            coroutine=async_load_skill,
        )

    def _execute_load_skill(
        self,
        backend: BackendProtocol,
        skill_name: str,
        runtime: ToolRuntime[None, SkillsState],
    ) -> Command | str:
        """load_skill 核心逻辑（同步版本）。

        Args:
            backend: Backend 实例
            skill_name: 技能名称
            runtime: ToolRuntime 实例

        Returns:
            Command 更新状态并携带 ToolMessage，或错误消息字符串
        """
        state = runtime.state
        skills_metadata = state.get("skills_metadata", [])
        # 建议 2 注释：浅拷贝 dict 即可——后续代码仅添加/替换 key (skill_resources[skill_name] = ...)，
        # 不会原地修改已有 value (list) 的内容，因此浅拷贝是安全的。
        skill_resources = dict(state.get("skill_resources", {}))
        loaded_skills = list(state.get("skills_loaded", []))

        # 查找目标技能
        target_skill: SkillMetadata | None = None
        for skill in skills_metadata:
            if skill["name"] == skill_name:
                target_skill = skill
                break

        if target_skill is None:
            available = [s["name"] for s in skills_metadata]
            return (
                f"Error: Skill '{skill_name}' not found. "
                f"Available skills: {', '.join(available)}"
            )

        # 检查是否已加载（幂等性）
        if skill_name in loaded_skills:
            return f"Skill '{skill_name}' is already loaded. Its instructions are already active."

        # 内容层预算检查（引导使用 unload_skill 释放空间）
        if len(loaded_skills) >= self._max_loaded_skills:
            return (
                f"Error: Cannot load skill '{skill_name}'. "
                f"Maximum number of simultaneously loaded skills reached "
                f"({self._max_loaded_skills}). "
                f"Currently loaded: {', '.join(loaded_skills)}. "
                f"Use `unload_skill(\"skill-name\")` to unload a skill you no "
                f"longer need, then retry loading."
            )

        # 读取 SKILL.md 内容
        responses = backend.download_files([target_skill["path"]])
        response = responses[0]

        if response.error or response.content is None:
            return f"Error: Failed to read skill file at {target_skill['path']}: {response.error}"

        # 安全检查：文件大小限制（与 V1 的 _parse_skill_metadata 一致）
        if len(response.content) > MAX_SKILL_FILE_SIZE:
            return (
                f"Error: Skill file at {target_skill['path']} exceeds "
                f"maximum size ({MAX_SKILL_FILE_SIZE} bytes)"
            )

        try:
            content = response.content.decode("utf-8")
        except UnicodeDecodeError as e:
            return f"Error: Failed to decode skill file: {e}"

        # 延迟资源发现：如果缓存中没有该技能的资源，按需扫描
        if skill_name not in skill_resources:
            skill_dir = str(PurePosixPath(target_skill["path"]).parent)
            skill_resources[skill_name] = _discover_resources(
                backend, skill_dir, skill_name,
            )

        # 构建返回内容
        result_parts = [content]

        # 附加资源摘要
        resources = skill_resources.get(skill_name, [])
        if resources:
            result_parts.append("\n\n---\n**Skill Resources:**\n")
            for resource in resources:
                result_parts.append(f"- [{resource['type']}] `{resource['path']}`")

        result_content = "\n".join(result_parts)

        # 通过 Command 更新状态
        loaded_skills.append(skill_name)
        # 建议 1 注释：messages 放在 update 字典内部而非 Command 顶层参数。
        # 这是 LangGraph Command 的标准模式，messages 作为状态更新的一部分被处理。
        # 与 FilesystemMiddleware.write_file 模式保持一致。
        return Command(
            update={
                "skills_loaded": loaded_skills,
                "skill_resources": skill_resources,
                "messages": [
                    ToolMessage(
                        content=result_content,
                        tool_call_id=runtime.tool_call_id,
                    ),
                ],
            },
        )

    async def _aexecute_load_skill(
        self,
        backend: BackendProtocol,
        skill_name: str,
        runtime: ToolRuntime[None, SkillsState],
    ) -> Command | str:
        """load_skill 核心逻辑（异步版本）。

        与 _execute_load_skill 逻辑完全相同，但使用异步 backend API。
        """
        state = runtime.state
        skills_metadata = state.get("skills_metadata", [])
        skill_resources = dict(state.get("skill_resources", {}))
        loaded_skills = list(state.get("skills_loaded", []))

        # 查找目标技能
        target_skill: SkillMetadata | None = None
        for skill in skills_metadata:
            if skill["name"] == skill_name:
                target_skill = skill
                break

        if target_skill is None:
            available = [s["name"] for s in skills_metadata]
            return (
                f"Error: Skill '{skill_name}' not found. "
                f"Available skills: {', '.join(available)}"
            )

        # 检查是否已加载（幂等性）
        if skill_name in loaded_skills:
            return f"Skill '{skill_name}' is already loaded. Its instructions are already active."

        # 内容层预算检查（引导使用 unload_skill 释放空间）
        if len(loaded_skills) >= self._max_loaded_skills:
            return (
                f"Error: Cannot load skill '{skill_name}'. "
                f"Maximum number of simultaneously loaded skills reached "
                f"({self._max_loaded_skills}). "
                f"Currently loaded: {', '.join(loaded_skills)}. "
                f"Use `unload_skill(\"skill-name\")` to unload a skill you no "
                f"longer need, then retry loading."
            )

        # 读取 SKILL.md 内容
        responses = await backend.adownload_files([target_skill["path"]])
        response = responses[0]

        if response.error or response.content is None:
            return f"Error: Failed to read skill file at {target_skill['path']}: {response.error}"

        # 安全检查：文件大小限制
        if len(response.content) > MAX_SKILL_FILE_SIZE:
            return (
                f"Error: Skill file at {target_skill['path']} exceeds "
                f"maximum size ({MAX_SKILL_FILE_SIZE} bytes)"
            )

        try:
            content = response.content.decode("utf-8")
        except UnicodeDecodeError as e:
            return f"Error: Failed to decode skill file: {e}"

        # 延迟资源发现
        if skill_name not in skill_resources:
            skill_dir = str(PurePosixPath(target_skill["path"]).parent)
            skill_resources[skill_name] = await _adiscover_resources(
                backend, skill_dir, skill_name,
            )

        # 构建返回内容
        result_parts = [content]
        resources = skill_resources.get(skill_name, [])
        if resources:
            result_parts.append("\n\n---\n**Skill Resources:**\n")
            for resource in resources:
                result_parts.append(f"- [{resource['type']}] `{resource['path']}`")

        result_content = "\n".join(result_parts)

        # 通过 Command 更新状态
        loaded_skills.append(skill_name)
        return Command(
            update={
                "skills_loaded": loaded_skills,
                "skill_resources": skill_resources,
                "messages": [
                    ToolMessage(
                        content=result_content,
                        tool_call_id=runtime.tool_call_id,
                    ),
                ],
            },
        )
```

### 2.7 unload_skill 工具实现

在 `load_skill` 工具后添加：

```python
# =============================================================================
# V2 新增：unload_skill 工具
# =============================================================================

    def _create_unload_skill_tool(self) -> BaseTool:
        """创建 unload_skill 工具。"""

        def sync_unload_skill(
            skill_name: Annotated[str, "Name of the loaded skill to unload."],
            runtime: ToolRuntime[None, SkillsState],
        ) -> Command | str:
            """Unload a previously loaded skill to free up a loading slot.

            Use this when you have reached the maximum number of loaded skills
            and need to load a different one, or when a skill is no longer
            needed for the current task.
            """
            return self._execute_unload_skill(skill_name, runtime)

        async def async_unload_skill(
            skill_name: Annotated[str, "Name of the loaded skill to unload."],
            runtime: ToolRuntime[None, SkillsState],
        ) -> Command | str:
            """Unload a previously loaded skill to free up a loading slot (async)."""
            return self._execute_unload_skill(skill_name, runtime)

        return StructuredTool.from_function(
            name="unload_skill",
            description=(
                "Unload a previously loaded skill to free up a loading slot. "
                "Use this when you have reached the maximum number of loaded "
                "skills and need to load a different one."
            ),
            func=sync_unload_skill,
            coroutine=async_unload_skill,
        )

    def _execute_unload_skill(
        self,
        skill_name: str,
        runtime: ToolRuntime[None, SkillsState],
    ) -> Command | str:
        """unload_skill 核心逻辑。

        注意：unload_skill 不需要 backend 访问（不涉及文件操作），
        因此同步和异步版本可以共用同一个实现。

        Args:
            skill_name: 技能名称
            runtime: ToolRuntime 实例

        Returns:
            Command 更新状态并携带 ToolMessage，或错误消息字符串
        """
        state = runtime.state
        loaded_skills = list(state.get("skills_loaded", []))
        skill_resources = dict(state.get("skill_resources", {}))

        # 验证技能是否已加载
        if skill_name not in loaded_skills:
            return (
                f"Error: Skill '{skill_name}' is not currently loaded. "
                f"Currently loaded skills: "
                f"{', '.join(loaded_skills) if loaded_skills else '(none)'}."
            )

        # 从 skills_loaded 中移除
        loaded_skills.remove(skill_name)

        # 从 skill_resources 缓存中移除（释放内存）
        skill_resources.pop(skill_name, None)

        remaining = len(loaded_skills)
        available_slots = self._max_loaded_skills - remaining

        return Command(
            update={
                "skills_loaded": loaded_skills,
                "skill_resources": skill_resources,
                "messages": [
                    ToolMessage(
                        content=(
                            f"Skill '{skill_name}' has been unloaded. "
                            f"Currently loaded: {remaining}/{self._max_loaded_skills} "
                            f"({available_slots} slot(s) available). "
                            f"Note: The skill's instructions from the previous "
                            f"load_skill call are still in the conversation history "
                            f"but will no longer be marked as [Loaded] in the "
                            f"skills list."
                        ),
                        tool_call_id=runtime.tool_call_id,
                    ),
                ],
            },
        )
```

### 2.8 _format_skills_list 扩展

修改 `_format_skills_list` 方法：

```python
# =============================================================================
# V2 修改：_format_skills_list
# =============================================================================

    def _format_skills_list(
        self,
        skills: list[SkillMetadata],
        loaded: list[str],
        resources: dict[str, list[ResourceMetadata]],
    ) -> str:
        """格式化技能列表用于系统提示显示。

        V2 增强：显示加载状态标记、资源摘要、load_skill/unload_skill 引导语。
        所有在 sources 中发现的技能都会完整展示，不进行截断。

        Args:
            skills: 技能元数据列表
            loaded: 已加载技能名称列表
            resources: 技能资源缓存

        Returns:
            格式化的技能列表字符串
        """
        if not skills:
            paths = [f"{source_path}" for source_path in self.sources]
            return (
                f"(No skills available yet. You can create skills in "
                f"{' or '.join(paths)})"
            )

        lines = []
        loaded_set = set(loaded)

        for skill in skills:
            name = skill["name"]
            annotations = _format_skill_annotations(skill)

            # V2: 标记已加载状态
            status = " [Loaded]" if name in loaded_set else ""
            desc_line = f"- **{name}**{status}: {skill['description']}"
            if annotations:
                desc_line += f" ({annotations})"

            skill_lines = [desc_line]

            # 显示 allowed-tools 推荐（RECOMMEND 模式，仅提示不拦截）
            if skill["allowed_tools"]:
                skill_lines.append(
                    f"  -> Recommended tools: {', '.join(skill['allowed_tools'])}"
                )

            # V2: 显示已加载技能的资源摘要
            if name in loaded_set:
                skill_resources = resources.get(name, [])
                if skill_resources:
                    resource_summary = _format_resource_summary(skill_resources)
                    skill_lines.append(f"  -> Resources: {resource_summary}")

            # V2: 引导使用 load_skill 工具
            if name not in loaded_set:
                skill_lines.append(
                    f'  -> Use `load_skill("{name}")` to read full instructions'
                )

            lines.append("\n".join(skill_lines))

        return "\n".join(lines)


def _format_resource_summary(resources: list[ResourceMetadata]) -> str:
    """格式化资源摘要，按类型分组。

    Args:
        resources: 资源元数据列表

    Returns:
        格式化的资源摘要字符串
    """
    by_type: dict[str, int] = {}
    for r in resources:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    parts = []
    for rtype, count in sorted(by_type.items()):
        parts.append(f"{count} {rtype}{'s' if count > 1 else ''}")
    return ", ".join(parts)
```

### 2.9 modify_request 扩展

修改 `modify_request` 方法：

```python
# =============================================================================
# V2 修改：modify_request
# =============================================================================

    def modify_request(self, request: ModelRequest) -> ModelRequest:
        """Inject skills documentation into a model request's system message.

        Args:
            request: Model request to modify

        Returns:
            New model request with skills documentation injected into system message
        """
        skills_metadata = request.state.get("skills_metadata", [])
        skills_loaded = request.state.get("skills_loaded", [])       # V2
        skill_resources = request.state.get("skill_resources", {})    # V2

        skills_locations = self._format_skills_locations()
        skills_list = self._format_skills_list(
            skills_metadata, skills_loaded, skill_resources,  # V2: 传入新状态
        )

        skills_section = self.system_prompt_template.format(
            skills_locations=skills_locations,
            skills_list=skills_list,
        )

        new_system_message = append_to_system_message(request.system_message, skills_section)

        return request.override(system_message=new_system_message)
```

### 2.10 SKILLS_SYSTEM_PROMPT 模板更新

更新 `SKILLS_SYSTEM_PROMPT` 模板：

```python
# =============================================================================
# V2 修改：SKILLS_SYSTEM_PROMPT 模板
# =============================================================================

SKILLS_SYSTEM_PROMPT = """

## Skills System

You have access to a skills library that provides specialized capabilities \
and domain knowledge.

{skills_locations}

**Available Skills:**

{skills_list}

**How to Use Skills (Progressive Disclosure):**

Skills follow a **progressive disclosure** pattern - you see their name and \
description above, but only read full instructions when needed:

1. **Recognize when a skill applies**: Check if the user's task matches a \
skill's description
2. **Load the skill**: Use `load_skill("skill-name")` to read full \
instructions and discover resources
3. **Follow the skill's instructions**: The loaded content contains \
step-by-step workflows, best practices, and examples
4. **Access supporting files**: Use the resource paths shown in the loaded \
skill output with `read_file`
5. **Unload when done**: Use `unload_skill("skill-name")` to free up a \
loading slot when a skill is no longer needed

**When to Use Skills:**
- User's request matches a skill's domain (e.g., "research X" -> \
web-research skill)
- You need specialized knowledge or structured workflows
- A skill provides proven patterns for complex tasks

Remember: Skills make you more capable and consistent. When in doubt, check \
if a skill exists for the task!
"""
```

### 2.11 __all__ 导出更新

更新 `__all__` 导出：

```python
# V1: __all__ = ["SkillMetadata", "SkillsMiddleware"]
# V2: 新增 ResourceMetadata
__all__ = ["SkillMetadata", "SkillsMiddleware", "ResourceMetadata"]
```

---

## 三、测试策略

### 3.1 单元测试（24 个用例）

在 `tests/unit_tests/middleware/test_skills_middleware.py` 中添加以下测试：

#### 3.1.1 资源发现测试（5 个）

```python
def test_discover_resources_standard_dirs(tmp_path: Path) -> None:
    """Test correct discovery of resources in standard directories."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)

    # Create skill with resources
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)

    # Create SKILL.md
    (skill_dir / "SKILL.md").write_text(make_skill_content("test-skill", "Test"))

    # Create resources
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "helper.py").write_text("def helper(): pass")

    references_dir = skill_dir / "references"
    references_dir.mkdir()
    (references_dir / "api.md").write_text("# API Reference")

    assets_dir = skill_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "template.txt").write_text("Template content")

    # Discover resources
    resources = _discover_resources(backend, str(skill_dir), "test-skill")

    assert len(resources) == 3
    resource_types = {r["type"] for r in resources}
    assert resource_types == {"script", "reference", "asset"}


def test_discover_resources_empty_skill(tmp_path: Path) -> None:
    """Test discovery returns empty list for skill without resources."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skill_dir = tmp_path / "skills" / "empty-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(make_skill_content("empty-skill", "Empty"))

    resources = _discover_resources(backend, str(skill_dir), "empty-skill")
    assert resources == []


def test_discover_resources_backend_error(tmp_path: Path) -> None:
    """Test graceful degradation when backend.ls_info fails."""
    # Create a mock backend that raises exception
    class FailingBackend:
        def ls_info(self, path: str):
            raise RuntimeError("Backend error")
        async def als_info(self, path: str):
            raise RuntimeError("Backend error")

    backend = FailingBackend()
    resources = _discover_resources(backend, "/skills/test", "test-skill")

    assert resources == []  # Should return empty list, not raise


def test_discover_resources_non_standard_dirs_ignored(tmp_path: Path) -> None:
    """Test that non-standard directories are ignored."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(make_skill_content("test-skill", "Test"))

    # Create non-standard directory
    temp_dir = skill_dir / "temp"
    temp_dir.mkdir()
    (temp_dir / "temp.txt").write_text("Temporary file")

    resources = _discover_resources(backend, str(skill_dir), "test-skill")

    # Should only find SKILL.md as "other", not temp directory content
    assert len(resources) == 0  # SKILL.md is explicitly excluded


def test_discover_resources_root_level_files(tmp_path: Path) -> None:
    """Test that root-level non-SKILL.md files are marked as 'other'."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(make_skill_content("test-skill", "Test"))
    (skill_dir / "readme.txt").write_text("Readme content")

    resources = _discover_resources(backend, str(skill_dir), "test-skill")

    assert len(resources) == 1
    assert resources[0]["type"] == "other"
    assert resources[0]["path"].endswith("readme.txt")
```

#### 3.1.2 状态初始化测试（2 个）

```python
def test_before_agent_initializes_new_state(tmp_path: Path) -> None:
    """Test that before_agent initializes skills_loaded and skill_resources."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])

    result = middleware.before_agent({}, None, {})  # type: ignore

    assert result is not None
    assert "skills_loaded" in result
    assert result["skills_loaded"] == []
    assert "skill_resources" in result
    assert result["skill_resources"] == {}


def test_before_agent_idempotent(tmp_path: Path) -> None:
    """Test that before_agent is idempotent (skips if metadata exists)."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])

    # First call should load skills
    result1 = middleware.before_agent({}, None, {})  # type: ignore
    assert result1 is not None

    # Second call with existing metadata should return None
    state_with_metadata = {"skills_metadata": result1["skills_metadata"]}
    result2 = middleware.before_agent(state_with_metadata, None, {})  # type: ignore
    assert result2 is None
```

#### 3.1.3 load_skill 测试（8 个）

```python
def test_load_skill_returns_command_with_content(tmp_path: Path) -> None:
    """Test successful load_skill returns Command with skill content."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    skill_content = make_skill_content("test-skill", "Test skill")
    (skills_dir / "test-skill" / "SKILL.md").write_text(skill_content)

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])

    # Initialize state first
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_load_skill(backend, "test-skill", runtime)

    assert isinstance(result, Command)
    assert "skills_loaded" in result.update
    assert "test-skill" in result.update["skills_loaded"]


def test_load_skill_updates_skills_loaded(tmp_path: Path) -> None:
    """Test that load_skill adds skill to skills_loaded."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_load_skill(backend, "test-skill", runtime)

    assert isinstance(result, Command)
    assert result.update["skills_loaded"] == ["test-skill"]


def test_load_skill_updates_skill_resources(tmp_path: Path) -> None:
    """Test that load_skill discovers and caches skill resources."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(make_skill_content("test-skill", "Test"))

    # Add resources
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "helper.py").write_text("def helper(): pass")

    middleware = SkillsMiddleware(backend=backend, sources=[str(skill_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_load_skill(backend, "test-skill", runtime)

    assert isinstance(result, Command)
    assert "test-skill" in result.update["skill_resources"]
    assert len(result.update["skill_resources"]["test-skill"]) == 1


def test_load_skill_not_found_returns_error(tmp_path: Path) -> None:
    """Test load_skill returns error for non-existent skill."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_load_skill(backend, "non-existent-skill", runtime)

    assert isinstance(result, str)
    assert "not found" in result


def test_load_skill_already_loaded_returns_message(tmp_path: Path) -> None:
    """Test load_skill returns message for already loaded skill."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None
    state["skills_loaded"] = ["test-skill"]

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_load_skill(backend, "test-skill", runtime)

    assert isinstance(result, str)
    assert "already loaded" in result


def test_load_skill_file_read_error(tmp_path: Path) -> None:
    """Test load_skill handles file read errors gracefully."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    # Mock backend to simulate read error
    class FailingBackend:
        def download_files(self, paths):
            from deepagents.backends.protocol import FileDownloadResponse
            return [FileDownloadResponse(path=paths[0], content=None, error="file_not_found")]
        async def adownload_files(self, paths):
            return self.download_files(paths)

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_load_skill(FailingBackend(), "test-skill", runtime)

    assert isinstance(result, str)
    assert "Failed to read" in result


def test_load_skill_file_size_exceeded(tmp_path: Path) -> None:
    """Test load_skill rejects oversized skill files."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)

    # Create oversized file
    large_content = "---\nname: big-skill\ndescription: Big\n---\n\n" + ("X" * (MAX_SKILL_FILE_SIZE + 1))
    (skills_dir / "big-skill" / "SKILL.md").write_text(large_content)

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_load_skill(backend, "big-skill", runtime)

    assert isinstance(result, str)
    assert "exceeds maximum size" in result


def test_load_skill_max_loaded_reached(tmp_path: Path) -> None:
    """Test load_skill blocks when max_loaded_skills limit is reached."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)

    # Create two skills
    (skills_dir / "skill-1" / "SKILL.md").write_text(
        make_skill_content("skill-1", "Skill 1")
    )
    (skills_dir / "skill-2" / "SKILL.md").write_text(
        make_skill_content("skill-2", "Skill 2")
    )

    # Middleware with max_loaded_skills=1
    middleware = SkillsMiddleware(
        backend=backend, sources=[str(skills_dir)], max_loaded_skills=1
    )
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None
    state["skills_loaded"] = ["skill-1"]  # Pre-load one skill

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_load_skill(backend, "skill-2", runtime)

    assert isinstance(result, str)
    assert "Maximum number of simultaneously loaded skills reached" in result
    assert "unload_skill" in result  # Should guide user to unload
```

#### 3.1.4 unload_skill 测试（4 个）

```python
def test_unload_skill_success(tmp_path: Path) -> None:
    """Test successful unload_skill removes skill from skills_loaded."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None
    state["skills_loaded"] = ["test-skill"]

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_unload_skill("test-skill", runtime)

    assert isinstance(result, Command)
    assert result.update["skills_loaded"] == []


def test_unload_skill_clears_resources(tmp_path: Path) -> None:
    """Test unload_skill removes skill from skill_resources cache."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(make_skill_content("test-skill", "Test"))

    middleware = SkillsMiddleware(backend=backend, sources=[str(skill_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None
    state["skills_loaded"] = ["test-skill"]
    state["skill_resources"] = {"test-skill": [{"path": "...", "type": "script", "skill_name": "test-skill"}]}

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_unload_skill("test-skill", runtime)

    assert isinstance(result, Command)
    assert "test-skill" not in result.update["skill_resources"]


def test_unload_skill_not_loaded_returns_error(tmp_path: Path) -> None:
    """Test unload_skill returns error for skill not currently loaded."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None
    state["skills_loaded"] = []  # No skills loaded

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    result = middleware._execute_unload_skill("test-skill", runtime)

    assert isinstance(result, str)
    assert "not currently loaded" in result


def test_unload_skill_then_reload(tmp_path: Path) -> None:
    """Test that a skill can be unloaded and reloaded."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None
    state["skills_loaded"] = ["test-skill"]
    state["skill_resources"] = {"test-skill": [{"path": "...", "type": "script", "skill_name": "test-skill"}]}

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    # Unload
    unload_result = middleware._execute_unload_skill("test-skill", runtime)
    assert isinstance(unload_result, Command)
    assert unload_result.update["skills_loaded"] == []

    # Reload (need to update runtime state)
    runtime.state["skills_loaded"] = []
    runtime.state["skill_resources"] = {}

    load_result = middleware._execute_load_skill(backend, "test-skill", runtime)
    assert isinstance(load_result, Command)
    assert "test-skill" in load_result.update["skills_loaded"]
```

#### 3.1.5 系统提示测试（3 个）

```python
def test_format_skills_list_with_loaded_status() -> None:
    """Test that _format_skills_list shows [Loaded] marker."""
    middleware = SkillsMiddleware(backend=None, sources=["/skills"])  # type: ignore

    skills: list[SkillMetadata] = [
        {
            "name": "loaded-skill",
            "description": "Loaded skill",
            "path": "/skills/loaded-skill/SKILL.md",
            "metadata": {},
            "license": None,
            "compatibility": None,
            "allowed_tools": [],
        },
        {
            "name": "unloaded-skill",
            "description": "Unloaded skill",
            "path": "/skills/unloaded-skill/SKILL.md",
            "metadata": {},
            "license": None,
            "compatibility": None,
            "allowed_tools": [],
        },
    ]

    result = middleware._format_skills_list(skills, ["loaded-skill"], {})

    assert "[Loaded]" in result
    assert "loaded-skill" in result
    assert "unloaded-skill" in result
    # Check that loaded skill has [Loaded] marker
    assert "**loaded-skill** [Loaded]" in result
    assert "**unloaded-skill** [Loaded]" not in result


def test_format_skills_list_with_resources() -> None:
    """Test that _format_skills_list shows resource summary for loaded skills."""
    middleware = SkillsMiddleware(backend=None, sources=["/skills"])  # type: ignore

    skills: list[SkillMetadata] = [
        {
            "name": "test-skill",
            "description": "Test skill",
            "path": "/skills/test-skill/SKILL.md",
            "metadata": {},
            "license": None,
            "compatibility": None,
            "allowed_tools": [],
        },
    ]

    resources = {
        "test-skill": [
            {"path": "/skills/test-skill/scripts/helper.py", "type": "script", "skill_name": "test-skill"},
            {"path": "/skills/test-skill/scripts/util.py", "type": "script", "skill_name": "test-skill"},
            {"path": "/skills/test-skill/references/api.md", "type": "reference", "skill_name": "test-skill"},
        ]
    }

    result = middleware._format_skills_list(skills, ["test-skill"], resources)

    assert "Resources:" in result
    assert "2 scripts" in result
    assert "1 reference" in result


def test_format_skills_list_load_skill_guidance() -> None:
    """Test that _format_skills_list shows load_skill guidance for unloaded skills."""
    middleware = SkillsMiddleware(backend=None, sources=["/skills"])  # type: ignore

    skills: list[SkillMetadata] = [
        {
            "name": "test-skill",
            "description": "Test skill",
            "path": "/skills/test-skill/SKILL.md",
            "metadata": {},
            "license": None,
            "compatibility": None,
            "allowed_tools": [],
        },
    ]

    result = middleware._format_skills_list(skills, [], {})

    assert 'load_skill("test-skill")' in result
```

#### 3.1.6 向后兼容测试（2 个）

```python
def test_v1_skills_work_without_modification(tmp_path: Path) -> None:
    """Test that V1 skills (without resource directories) work without modification."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)

    # Create a V1-style skill (only SKILL.md, no resources)
    skill_content = """---
name: v1-skill
description: A V1 skill without resources
---

# V1 Skill

This skill has no resource directories.
"""
    (skills_dir / "v1-skill" / "SKILL.md").write_text(skill_content)

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])

    result = middleware.before_agent({}, None, {})  # type: ignore

    assert result is not None
    assert len(result["skills_metadata"]) == 1
    assert result["skills_metadata"][0]["name"] == "v1-skill"


def test_read_file_still_works_for_skills(tmp_path: Path) -> None:
    """Test that reading skills via read_file still works (elegant degradation)."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    # Simulate read_file access (no state update)
    skill_path = str(skills_dir / "test-skill" / "SKILL.md")
    content = backend.read(skill_path)

    assert "test-skill" in content
    assert "Test" in content
```

### 3.2 集成测试（6 个）

在 `tests/integration_tests/test_skills_integration.py` 中添加：

```python
def test_load_skill_then_read_resource(tmp_path: Path) -> None:
    """Test load_skill followed by read_file to access resource."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(make_skill_content("test-skill", "Test"))
    (skill_dir / "scripts" / "helper.py").write_text("def helper(): return 'hello'")

    middleware = SkillsMiddleware(backend=backend, sources=[str(skill_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    # Load skill
    load_result = middleware._execute_load_skill(backend, "test-skill", runtime)
    assert isinstance(load_result, Command)

    # Read resource file
    resource_path = str(skill_dir / "scripts" / "helper.py")
    resource_content = backend.read(resource_path)

    assert "def helper" in resource_content


def test_new_agent_initializes_empty_skills_loaded(tmp_path: Path) -> None:
    """Test that a new agent instance initializes with empty skills_loaded.

    Note: This tests initialization behavior. PrivateStateAttr isolation
    is guaranteed by LangGraph framework and does not need middleware-level testing.
    """
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])

    # Main agent loads skill
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None
    state["skills_loaded"] = ["test-skill"]

    # New agent instance should initialize with empty skills_loaded
    new_agent_state = middleware.before_agent({}, None, {})  # type: ignore
    assert new_agent_state is not None
    assert new_agent_state["skills_loaded"] == []  # Empty, fresh initialization


def test_unload_skill_updates_system_prompt(tmp_path: Path) -> None:
    """Test that unloading a skill updates the system prompt."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None
    state["skills_loaded"] = ["test-skill"]
    state["skill_resources"] = {}

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    # Verify [Loaded] marker before unload
    skills_list_before = middleware._format_skills_list(
        state["skills_metadata"], state["skills_loaded"], state["skill_resources"]
    )
    assert "[Loaded]" in skills_list_before

    # Unload
    unload_result = middleware._execute_unload_skill("test-skill", runtime)
    assert isinstance(unload_result, Command)

    # Verify [Loaded] marker removed after unload
    skills_list_after = middleware._format_skills_list(
        state["skills_metadata"], unload_result.update["skills_loaded"], unload_result.update["skill_resources"]
    )
    # The skill should still be in the list, but without [Loaded] marker
    assert "**test-skill** [Loaded]" not in skills_list_after


def test_load_unload_reload_lifecycle(tmp_path: Path) -> None:
    """Test complete load -> unload -> reload lifecycle."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill" / "SKILL.md").write_text(
        make_skill_content("test-skill", "Test")
    )

    middleware = SkillsMiddleware(backend=backend, sources=[str(skills_dir)])
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    # Load
    load_result = middleware._execute_load_skill(backend, "test-skill", runtime)
    assert isinstance(load_result, Command)
    assert load_result.update["skills_loaded"] == ["test-skill"]

    # Update runtime state
    runtime.state["skills_loaded"] = load_result.update["skills_loaded"]
    runtime.state["skill_resources"] = load_result.update["skill_resources"]

    # Unload
    unload_result = middleware._execute_unload_skill("test-skill", runtime)
    assert isinstance(unload_result, Command)
    assert unload_result.update["skills_loaded"] == []

    # Update runtime state
    runtime.state["skills_loaded"] = unload_result.update["skills_loaded"]
    runtime.state["skill_resources"] = unload_result.update["skill_resources"]

    # Reload
    reload_result = middleware._execute_load_skill(backend, "test-skill", runtime)
    assert isinstance(reload_result, Command)
    assert reload_result.update["skills_loaded"] == ["test-skill"]


def test_max_loaded_skills_with_unload(tmp_path: Path) -> None:
    """Test that unloading frees up slots for new skills."""
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=False)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)

    # Create 3 skills
    for i in range(3):
        (skills_dir / f"skill-{i}" / "SKILL.md").write_text(
            make_skill_content(f"skill-{i}", f"Skill {i}")
        )

    # Middleware with max_loaded_skills=2
    middleware = SkillsMiddleware(
        backend=backend, sources=[str(skills_dir)], max_loaded_skills=2
    )
    state = middleware.before_agent({}, None, {})  # type: ignore
    assert state is not None

    # Load 2 skills
    state["skills_loaded"] = ["skill-0", "skill-1"]
    state["skill_resources"] = {}

    runtime = ToolRuntime(
        state={"skills_metadata": state["skills_metadata"], **state},
        context=None,
        tool_call_id="test-call",
        store=None,
        stream_writer=lambda _: None,
        config={},
    )

    # Try to load 3rd skill (should fail)
    result = middleware._execute_load_skill(backend, "skill-2", runtime)
    assert isinstance(result, str)
    assert "Maximum number" in result

    # Unload one skill
    unload_result = middleware._execute_unload_skill("skill-0", runtime)
    assert isinstance(unload_result, Command)

    # Update runtime state
    runtime.state["skills_loaded"] = unload_result.update["skills_loaded"]
    runtime.state["skill_resources"] = unload_result.update["skill_resources"]

    # Now should be able to load skill-2
    result = middleware._execute_load_skill(backend, "skill-2", runtime)
    assert isinstance(result, Command)
    assert "skill-2" in result.update["skills_loaded"]
```

---

## 四、质量保证

### 4.1 代码审查清单

| 检查项 | 状态 |
| :--- | :---: |
| 类型注解完整 | □ |
| 错误处理完善 | □ |
| 日志记录适当 | □ |
| 向后兼容保证 | □ |
| 性能无回归 | □ |
| 测试覆盖完整 | □ |

### 4.2 性能基准

| 操作 | V1 开销 | V2 开销 | 影响评估 |
| :--- | :---: | :---: | :---: |
| `before_agent` | 基准 | 相同 | ✅ 无影响 |
| `load_skill` | N/A | 1-3 次 `ls_info` | ✅ 可忽略 |
| `unload_skill` | N/A | 无 I/O | ✅ 可忽略 |
| `_format_skills_list` | 基准 | +O(N) 遍历 | ✅ 可忽略 |

### 4.3 已知限制

| 限制 | 说明 | 缓解策略 |
| :--- | :--- | :--- |
| 并行工具调用 | 当前框架不支持，状态更新使用覆盖语义 | 未来可添加 reducer |
| `sources` 运行时不可变 | `__init__` 时固定，运行时不可变 | 重启 agent 以识别新 `sources` |
| SubAgent 技能隔离 | 主 Agent 和 SubAgent 技能状态完全隔离 | SubAgent 自行 `load_skill` |
| 卸载不删除对话历史 | `unload_skill` 仅移除状态标记，不删除历史内容 | 这是预期行为，与操作系统"关闭文件"语义一致 |


### 4.4 错误处理矩阵

#### 4.4.1 `load_skill` 错误处理

| 错误场景 | 返回类型 | 关键消息片段 | 代码位置 |
| :--- | :---: | :--- | :--- |
| 技能不存在 | `str` | `"not found"` + 可用技能列表 | 2.6 节 `_execute_load_skill` |
| 技能已加载 | `str` | `"already loaded"` | 2.6 节 `_execute_load_skill` |
| 达到加载上限 | `str` | `"Maximum number..."` + `unload_skill` 引导 | 2.6 节 `_execute_load_skill` |
| 文件读取失败 | `str` | `"Failed to read"` + 后端错误消息 | 2.6 节 `_execute_load_skill` |
| 文件超过大小限制 | `str` | `"exceeds maximum size"` | 2.6 节 `_execute_load_skill` |
| 编码错误 | `str` | `"Failed to decode"` | 2.6 节 `_execute_load_skill` |
| 成功加载 | `Command` | 技能内容 + 资源摘要 | 2.6 节 `_execute_load_skill` |

#### 4.4.2 `unload_skill` 错误处理

| 错误场景 | 返回类型 | 关键消息片段 | 代码位置 |
| :--- | :---: | :--- | :--- |
| 技能未加载 | `str` | `"not currently loaded"` + 已加载技能列表 | 2.7 节 `_execute_unload_skill` |
| 成功卸载 | `Command` | 卸载确认 + 当前加载数量 + 可用名额 | 2.7 节 `_execute_unload_skill` |

---

## 五、实施步骤

### 5.1 Phase 1：核心功能实现（2-3 天）

| 任务 | 预计时间 | 验收标准 |
| :--- | :---: | :---: |
| 新增类型定义 | 1 小时 | `ResourceMetadata`、`SkillsState`、`SkillsStateUpdate` |
| 实现延迟资源发现 | 2 小时 | `_discover_resources` / `_adiscover_resources` |
| 扩展 `before_agent` | 1 小时 | 新增 `skills_loaded` 和 `skill_resources` 初始化 |
| 实现 `load_skill` 工具 | 3 小时 | 完整功能 + 错误处理 + 预算检查 |
| 实现 `unload_skill` 工具 | 2 小时 | 完整功能 + 错误处理 |
| 扩展 `_format_skills_list` | 1 小时 | 加载状态标记 + 资源摘要 |
| 更新 `SKILLS_SYSTEM_PROMPT` | 30 分钟 | 新增 `unload_skill` 引导 |
| 更新 `__init__` 和 `__all__` | 30 分钟 | 新增参数 + 导出 |

### 5.2 Phase 2：测试与文档（1-2 天）

| 任务 | 预计时间 | 验收标准 |
| :--- | :---: | :---: |
| 单元测试（24 个） | 1 天 | 所有测试通过 |
| 集成测试（6 个） | 4 小时 | 所有测试通过 |
| 文档更新 | 2 小时 | API 文档 + 迁移指南 |

### 5.3 Phase 3：代码审查与发布（1 天）

| 任务 | 预计时间 | 验收标准 |
| :--- | :---: | :---: |
| 代码审查 | 2 小时 | 无严重问题 |
| 性能测试 | 2 小时 | 无性能回归 |
| 发布 PR | 1 小时 | CI 通过 |

---

## 六、变更总结

### 6.1 新增内容

| 类型 | 名称 | 说明 |
| :--- | :--- | :--- |
| 类型 | `ResourceMetadata` | 资源元数据 |
| 类型 | `SkillsState` (扩展) | 新增 `skills_loaded`、`skill_resources` |
| 类型 | `SkillsStateUpdate` (扩展) | 新增 `skills_loaded`、`skill_resources` |
| 函数 | `_discover_resources` | 同步延迟资源发现 |
| 函数 | `_adiscover_resources` | 异步延迟资源发现 |
| 函数 | `_format_resource_summary` | 资源摘要格式化 |
| 方法 | `_get_backend_from_runtime` | 从 runtime 解析 backend |
| 方法 | `_create_load_skill_tool` | 创建 `load_skill` 工具 |
| 方法 | `_create_unload_skill_tool` | 创建 `unload_skill` 工具 |
| 方法 | `_execute_load_skill` | `load_skill` 同步核心逻辑 |
| 方法 | `_aexecute_load_skill` | `load_skill` 异步核心逻辑 |
| 方法 | `_execute_unload_skill` | `unload_skill` 核心逻辑 |

### 6.2 修改内容

| 类型 | 名称 | 说明 |
| :--- | :--- | :--- |
| 方法 | `__init__` | 新增 `max_loaded_skills` 参数 + `self.tools` |
| 方法 | `before_agent` | 新增 `skills_loaded` 和 `skill_resources` 初始化 |
| 方法 | `abefore_agent` | 新增 `skills_loaded` 和 `skill_resources` 初始化 |
| 方法 | `_format_skills_list` | 新增 `loaded` 和 `resources` 参数 |
| 方法 | `modify_request` | 传入新状态字段 |
| 常量 | `SKILLS_SYSTEM_PROMPT` | 新增 `unload_skill` 引导 |
| 导出 | `__all__` | 新增 `ResourceMetadata` |

### 6.3 废除内容

| 类型 | 名称 | 说明 |
| :--- | :--- | :--- |
| 模式 | `RESTRICT` 模式 | 因与 HITL 功能重叠而废除 |
| 参数 | `allowed_tools_policy` | 因废除 RESTRICT 模式而移除 |
| 参数 | `max_description_budget` | 因废除描述层预算而移除 |
| 参数 | `always_allowed_tools` | 因废除 RESTRICT 模式而移除 |
| Hook | `wrap_tool_call` | 因废除 RESTRICT 模式而不再使用 |
| 类型 | `AllowedToolsPolicy` | 因废除 RESTRICT 模式而移除 |
| 常量 | `_DEFAULT_ALWAYS_ALLOWED_TOOLS` | 因废除 RESTRICT 模式而移除 |

---

## 七、参考资源

| 资源 | 链接 |
| :--- | :--- |
| Agent Skills 规范 | https://agentskills.io/specification |
| Claude Code 技能文档 | https://code.claude.com/docs/en/skills |
| DeepAgents V2 设计文档 | ./DeepAgents_SkillsMiddleware_V2_升级设计方案_final_修订.md |
| LangGraph Middleware | https://docs.langchain.com/oss/python/langchain/middleware |

---

*本实施方案严格遵循 LangChain/LangGraph 框架机制和 DeepAgents 设计原理，确保与项目架构完美匹配，不会对系统造成侵害性影响。*
