# DeepAgents SkillsMiddleware V2 升级设计方案

**版本**: 2.0（三轮自审定稿）
**日期**: 2026-02-16
**状态**: 最终版

---

## 目录

1. [概述](#1-概述)
2. [架构设计](#2-架构设计)
3. [实现方案](#3-实现方案)
4. [向后兼容性保证](#4-向后兼容性保证)
5. [错误处理与降级策略](#5-错误处理与降级策略)
6. [测试策略](#6-测试策略)
7. [扩展路线图](#7-扩展路线图)
8. [实施计划](#8-实施计划)

---

## 1. 概述

### 1.1 文档目的

本文档为 `deepagents.middleware.skills.SkillsMiddleware` 的 V2 版本升级提供完整的设计与实现方案。方案基于对 [Agent Skills 开放规范][1]、[Claude Code 原生 Skill 系统][2]、以及 DeepAgents 现有框架架构的深入分析，旨在将现有中间件从基础的技能发现与提示注入器，升级为一个功能完备、安全可控、高度可扩展的技能运行时系统。

### 1.2 当前状态分析

当前 `SkillsMiddleware` V1（`skills.py`，约 832 行）已经实现了以下核心能力：

| 已实现能力 | 实现方式 | 使用的 Hook |
| :--- | :--- | :--- |
| 技能发现与元数据解析 | `_list_skills` / `_alist_skills` 遍历 backend 目录 | `before_agent` |
| YAML frontmatter 解析 | `_parse_skill_metadata` 解析 `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` | `before_agent` |
| 系统提示注入 | `SKILLS_SYSTEM_PROMPT` 模板 + `modify_request` | `wrap_model_call` |
| 多源优先级覆盖 | 后面的 source 覆盖前面的（last one wins） | `before_agent` |
| 规范验证 | `_validate_skill_name` 验证名称格式 | `before_agent` |
| 安全防护 | `MAX_SKILL_FILE_SIZE` (10MB) 限制 | `before_agent` |

然而，V1 存在以下核心局限，这些局限直接限制了技能系统的实用性和安全性：

**缺乏状态追踪**。系统无法追踪哪些技能已被 Agent 实际"加载"（即读取了完整的 `SKILL.md` 内容）。当前的渐进式披露是单向的——Agent 在系统提示中看到技能列表后，通过通用的 `read_file` 工具读取 `SKILL.md`，但中间件对此过程完全无感知。这意味着无法基于"已加载技能"实施任何策略（如权限控制、上下文优化）。

**无资源发现机制**。Agent Skills 规范定义了 `scripts/`, `references/`, `assets/` 三个标准资源目录，但 V1 仅发现 `SKILL.md` 文件本身，不会扫描或报告这些资源目录的内容。Agent 必须依赖 `SKILL.md` 中的文本引用来猜测资源路径。

**`allowed-tools` 无强制执行**。V1 正确解析了 `allowed-tools` 字段并在系统提示中显示，但缺乏任何运行时强制执行机制。这意味着即使技能声明了工具限制，Agent 仍然可以调用任意工具。

**缺少专用加载工具**。Agent 必须使用通用的 `read_file` 工具来加载技能内容，这不仅增加了操作复杂性，也使得中间件无法区分"读取技能"和"读取普通文件"的行为。

**可扩展性有限**。当前架构仅使用了 `AgentMiddleware` 接口的 2 个 hook（`before_agent` 和 `wrap_model_call`），未利用 `wrap_tool_call`、`before_model`、`after_agent` 等 hook，难以支持 `hooks` 或 `context: fork` 等高级流程控制特性。

### 1.3 设计原则

本次升级严格遵循以下四项核心设计原则，它们按优先级排列：

| 优先级 | 原则 | 约束 |
| :---: | :--- | :--- |
| P0 | **向后兼容性** | 所有现存的 `SKILL.md` 文件无需任何修改即可继续工作。V1 的公开 API（`SkillsMiddleware.__init__` 签名、`SkillMetadata` TypedDict、`SkillsState` schema）保持不变。新功能作为增量引入。 |
| P0 | **最小侵入性** | 所有变更严格限制在 `skills.py` 文件内部。不修改 `create_deep_agent` 函数签名、`AgentMiddleware` 基类、`BackendProtocol` 接口、或任何其他中间件。新工具通过 `self.tools` 属性提供（与 `FilesystemMiddleware` 模式一致），由框架自动收集。 |
| P1 | **遵循既有模式** | 复用 DeepAgents 框架中已建立的设计模式：通过 `BackendProtocol` 进行文件操作、通过 `PrivateStateAttr` 隔离中间件状态、通过 `self.tools` 提供中间件工具、通过 `Command` 进行工具内状态更新、通过 `ToolRuntime` 在工具函数中访问 state 和 backend。 |
| P2 | **模块化与可扩展性** | 为未来的高级功能（事件钩子 `hooks`、子代理执行 `context: fork`、模型覆盖 `model`）预留清晰的扩展点，但不在本次升级中实现。 |

### 1.4 升级范围

本次升级的范围严格限定如下：

| 范围 | 内容 |
| :--- | :--- |
| **纳入范围** | 技能加载状态追踪、资源发现与报告、专用 `load_skill` 工具、`allowed-tools` 运行时建议/限制、系统提示优化、扩展点预留 |
| **排除范围** | `hooks` 事件系统实现、`context: fork` 子代理执行、`model` 字段覆盖、`argument-hint` / `$ARGUMENTS` 替换、`disable-model-invocation` / `user-invocable` 控制、CLI 命令扩展 |

排除范围中的功能将在后续版本中按优先级逐步引入，本文档第 7 节提供了详细的扩展路线图。

---

## 2. 架构设计

### 2.1 Hook 使用规划

V2 将在 V1 的基础上，新增对 `wrap_tool_call` hook 的使用。以下是完整的 hook 使用规划：

| Hook | V1 使用 | V2 使用 | 职责 |
| :--- | :---: | :---: | :--- |
| `before_agent` / `abefore_agent` | ✅ | ✅ | 技能发现、元数据解析、资源发现、状态初始化 |
| `wrap_model_call` / `awrap_model_call` | ✅ | ✅ | 系统提示注入（含加载状态标记）|
| `wrap_tool_call` / `awrap_tool_call` | ❌ | ✅ | `allowed-tools` 运行时建议/限制 |
| `before_model` | ❌ | ❌ | 预留：未来可用于技能上下文预检 |
| `after_model` | ❌ | ❌ | 预留：未来可用于技能使用统计 |
| `after_agent` | ❌ | ❌ | 预留：未来可用于状态清理 |

> **重要说明**：所有新增的 hook 方法都需要同时提供同步和异步版本（如 `wrap_tool_call` 和 `awrap_tool_call`），这与 V1 中 `before_agent`/`abefore_agent` 和 `wrap_model_call`/`awrap_model_call` 的模式一致。

### 2.2 状态模型扩展

`SkillsState` 将被扩展以包含新的状态字段。所有新增字段均使用 `PrivateStateAttr` 标记，确保不会传播到父级 Agent，维持状态隔离。

```python
class ResourceMetadata(TypedDict):
    """技能资源文件的元数据。"""
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
    2. 作为 allowed-tools 权限检查的依据
    3. 避免重复加载同一技能
    """

    # V2 新增
    skill_resources: NotRequired[Annotated[dict[str, list[ResourceMetadata]], PrivateStateAttr]]
    """已发现的技能资源映射，键为技能名称。
    
    在 before_agent 阶段通过扫描技能目录下的 scripts/, references/, assets/ 
    子目录填充。采用 dict 结构（而非 flat list）以支持按技能名称的 O(1) 查找。
    """
```

`SkillsStateUpdate` 也需要相应扩展：

```python
class SkillsStateUpdate(TypedDict):
    """Skills 中间件的状态更新。"""
    skills_metadata: list[SkillMetadata]
    skills_loaded: list[str]
    skill_resources: dict[str, list[ResourceMetadata]]
```

**设计决策说明**。`skill_resources` 采用 `dict[str, list[ResourceMetadata]]` 而非 `list[ResourceMetadata]`，原因是 `load_skill` 工具在返回技能内容时需要附带该技能的资源列表，按技能名称索引可以避免每次都遍历整个列表。

### 2.3 工具设计

V2 将引入一个新的专用工具 `load_skill`，通过 `self.tools` 属性提供给框架。这与 `FilesystemMiddleware` 在 `__init__` 中创建 `self.tools = [self._create_ls_tool(), self._create_read_file_tool(), ...]` 的模式完全一致。

#### 2.3.1 `load_skill` 工具

```
load_skill(skill_name: str) -> str | Command
```

**工具行为**：

1. 从 `runtime.state["skills_metadata"]` 中查找匹配的技能，获取其 `path`。
2. 通过 `backend.download_files([path])` 读取 `SKILL.md` 的完整内容。
3. 从 `runtime.state["skill_resources"]` 中获取该技能的资源列表。
4. 构建返回内容：`SKILL.md` 内容 + 资源摘要（如果有资源）。
5. **状态更新**：通过返回 `Command` 将 `skill_name` 添加到 `skills_loaded` 列表中，同时携带 `ToolMessage` 作为工具响应。

**为何不引入 `load_skill_resource` 工具**。经过评审，我们决定不引入单独的 `load_skill_resource` 工具，原因如下：现有的 `read_file` 工具（由 `FilesystemMiddleware` 提供）已经完全能够读取资源文件，且 `load_skill` 返回的资源摘要中会包含完整的路径。引入冗余工具会增加 Agent 的认知负担，违反"最小侵入性"原则。

#### 2.3.2 工具提供机制

工具将在 `__init__` 中创建并赋值给 `self.tools`，由 `create_agent` 框架自动收集：

```python
class SkillsMiddleware(AgentMiddleware):
    state_schema = SkillsState

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        sources: list[str],
        allowed_tools_policy: AllowedToolsPolicy = AllowedToolsPolicy.RECOMMEND,
    ) -> None:
        self._backend = backend
        self.sources = sources
        self.system_prompt_template = SKILLS_SYSTEM_PROMPT
        self._allowed_tools_policy = allowed_tools_policy  # V2

        # V2: 创建专用工具
        self.tools = [
            self._create_load_skill_tool(),
        ]
```

**关键设计决策：状态更新在工具函数内部完成**。与 `FilesystemMiddleware` 的 `write_file` 工具模式一致，`load_skill` 工具函数在需要更新状态时直接返回 `Command` 对象。`Command` 的 `update` 字段包含要合并到 agent state 中的字段（如 `skills_loaded`），同时通过 `messages` 字段携带 `ToolMessage` 作为工具响应。这种模式避免了在 `wrap_tool_call` 中进行复杂的状态更新逻辑，保持了关注点分离。

---

## 3. 实现方案

### 3.1 资源发现（`before_agent` 增强）

`before_agent` hook 将被增强，在现有的技能元数据加载之后，增加资源发现步骤。

#### 3.1.1 `_discover_resources` 辅助函数

```python
# 资源目录映射（Agent Skills 规范定义的标准目录）
RESOURCE_TYPE_MAP: dict[str, Literal["script", "reference", "asset"]] = {
    "scripts": "script",
    "references": "reference",
    "assets": "asset",
}


def _discover_resources(
    backend: BackendProtocol,
    skill_dir: str,
    skill_name: str,
) -> list[ResourceMetadata]:
    """发现技能目录下的资源文件（同步版本）。
    
    扫描技能目录下的 scripts/, references/, assets/ 子目录，
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
            
            # 扫描资源目录内容
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

**性能考量**。资源发现在 `before_agent` 阶段执行（每次 agent invocation 仅一次），且仅扫描已发现技能目录下的标准子目录。对于典型的技能库（10-50 个技能，每个技能 0-10 个资源文件），额外的 I/O 开销可以忽略。对于远程 backend，`ls_info` 调用次数为 `O(技能数 × 标准目录数)`，即最多 `50 × 3 = 150` 次，在可接受范围内。

如果未来出现性能瓶颈（例如超过 100 个技能），可以通过以下策略优化：将资源发现改为延迟模式（lazy discovery），仅在 `load_skill` 被调用时才扫描该技能的资源目录。这一优化可以在不改变公开 API 的情况下透明实施。

**扫描深度说明**。资源发现仅扫描标准资源目录（`scripts/`, `references/`, `assets/`）的第一层子目录，不会递归扫描嵌套目录。例如，`scripts/utils/helper.py` 不会被发现，但 `scripts/helper.py` 会被发现。这是有意的设计选择，与 Agent Skills 规范的扁平资源目录结构一致。如果未来需要支持深层扫描，可以在 `_discover_resources` 中添加递归选项，而不影响公开 API。

#### 3.1.2 增强后的 `before_agent` / `abefore_agent`

```python
def before_agent(
    self, state: SkillsState, runtime: Runtime, config: RunnableConfig,
) -> SkillsStateUpdate | None:
    # 幂等检查：如果 skills_metadata 已存在，跳过
    if "skills_metadata" in state:
        return None

    backend = self._get_backend(state, runtime, config)
    all_skills: dict[str, SkillMetadata] = {}
    all_resources: dict[str, list[ResourceMetadata]] = {}

    for source_path in self.sources:
        source_skills = _list_skills(backend, source_path)
        for skill in source_skills:
            skill_name = skill["name"]
            all_skills[skill_name] = skill
            
            # V2: 资源发现
            skill_dir = str(PurePosixPath(skill["path"]).parent)
            all_resources[skill_name] = _discover_resources(
                backend, skill_dir, skill_name,
            )

    return SkillsStateUpdate(
        skills_metadata=list(all_skills.values()),
        skills_loaded=[],               # V2: 初始化为空
        skill_resources=all_resources,   # V2: 资源映射
    )


async def abefore_agent(
    self, state: SkillsState, runtime: Runtime, config: RunnableConfig,
) -> SkillsStateUpdate | None:
    if "skills_metadata" in state:
        return None

    backend = self._get_backend(state, runtime, config)
    all_skills: dict[str, SkillMetadata] = {}
    all_resources: dict[str, list[ResourceMetadata]] = {}

    for source_path in self.sources:
        source_skills = await _alist_skills(backend, source_path)
        for skill in source_skills:
            skill_name = skill["name"]
            all_skills[skill_name] = skill
            
            skill_dir = str(PurePosixPath(skill["path"]).parent)
            all_resources[skill_name] = await _adiscover_resources(
                backend, skill_dir, skill_name,
            )

    return SkillsStateUpdate(
        skills_metadata=list(all_skills.values()),
        skills_loaded=[],
        skill_resources=all_resources,
    )
```

**幂等性保证**。V1 通过 `if "skills_metadata" in state` 实现幂等。由于 V2 的 `SkillsStateUpdate` 同时写入所有三个字段，只需检查 `skills_metadata` 即可保证所有字段的幂等性——如果 `skills_metadata` 已存在，则 `skills_loaded` 和 `skill_resources` 也必然已存在（它们在同一个 `StateUpdate` 中写入）。

### 3.2 `load_skill` 工具实现

工具创建遵循 `FilesystemMiddleware` 的 `_create_*_tool` 模式，通过闭包捕获 `self` 引用以访问 backend 配置。

```python
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


def _get_backend_from_runtime(
    self, runtime: ToolRuntime[None, SkillsState],
) -> BackendProtocol:
    """从 ToolRuntime 中解析 backend 实例。"""
    if callable(self._backend):
        return self._backend(runtime)
    return self._backend


def _execute_load_skill(
    self,
    backend: BackendProtocol,
    skill_name: str,
    runtime: ToolRuntime[None, SkillsState],
) -> Command | str:
    """load_skill 核心逻辑（同步版本）。"""
    state = runtime.state
    skills_metadata = state.get("skills_metadata", [])
    skill_resources = state.get("skill_resources", {})
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

    # 检查是否已加载
    if skill_name in loaded_skills:
        return f"Skill '{skill_name}' is already loaded. Its instructions are already active."

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

    # 构建返回内容
    result_parts = [content]

    # 附加资源摘要
    resources = skill_resources.get(skill_name, [])
    if resources:
        result_parts.append("\n\n---\n**Skill Resources:**\n")
        for resource in resources:
            result_parts.append(f"- [{resource['type']}] `{resource['path']}`")

    result_content = "\n".join(result_parts)

    # 通过 Command 更新 skills_loaded 状态
    loaded_skills.append(skill_name)
    return Command(
        update={
            "skills_loaded": loaded_skills,
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
    """load_skill 核心逻辑（异步版本）。"""
    state = runtime.state
    skills_metadata = state.get("skills_metadata", [])
    skill_resources = state.get("skill_resources", {})
    loaded_skills = list(state.get("skills_loaded", []))

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

    if skill_name in loaded_skills:
        return f"Skill '{skill_name}' is already loaded. Its instructions are already active."

    responses = await backend.adownload_files([target_skill["path"]])
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

    result_parts = [content]
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
            "messages": [
                ToolMessage(
                    content=result_content,
                    tool_call_id=runtime.tool_call_id,
                ),
            ],
        },
    )
```

**关于 `Command` 模式的说明**。此处的 `Command` 使用方式与 `FilesystemMiddleware` 的 `write_file` 工具完全一致。当 `write_file` 成功写入文件后，它返回 `Command(update={"files": res.files_update, "messages": [ToolMessage(content=..., tool_call_id=runtime.tool_call_id)]})` 来同时更新状态和返回工具响应。`load_skill` 采用相同的模式：成功加载后返回 `Command` 来更新 `skills_loaded` 状态并返回技能内容。

### 3.3 系统提示优化（`wrap_model_call` 增强）

`wrap_model_call` 的核心逻辑（调用 `modify_request` 注入系统提示）保持不变，但 `_format_skills_list` 将被增强以反映加载状态和资源信息。

#### 3.3.1 增强后的 `_format_skills_list`

```python
def _format_skills_list(
    self,
    skills: list[SkillMetadata],
    loaded: list[str],
    resources: dict[str, list[ResourceMetadata]],
) -> str:
    """格式化技能列表用于系统提示显示。
    
    V2 增强：显示加载状态标记和资源摘要。
    """
    if not skills:
        paths = [f"{source_path}" for source_path in self.sources]
        return (
            f"(No skills available yet. You can create skills in "
            f"{' or '.join(paths)})"
        )

    lines = []
    for skill in skills:
        name = skill["name"]
        annotations = _format_skill_annotations(skill)
        
        # V2: 标记已加载状态
        status = " [Loaded]" if name in loaded else ""
        desc_line = f"- **{name}**{status}: {skill['description']}"
        if annotations:
            desc_line += f" ({annotations})"
        lines.append(desc_line)
        
        if skill["allowed_tools"]:
            lines.append(
                f"  -> Recommended tools: {', '.join(skill['allowed_tools'])}"
            )
        
        # V2: 显示资源摘要
        skill_resources = resources.get(name, [])
        if skill_resources:
            resource_summary = _format_resource_summary(skill_resources)
            lines.append(f"  -> Resources: {resource_summary}")
        
        # V2: 引导使用 load_skill 工具
        if name not in loaded:
            lines.append(
                f'  -> Use `load_skill("{name}")` to read full instructions'
            )
        
    return "\n".join(lines)


def _format_resource_summary(resources: list[ResourceMetadata]) -> str:
    """格式化资源摘要，按类型分组。"""
    by_type: dict[str, int] = {}
    for r in resources:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    
    parts = []
    for rtype, count in sorted(by_type.items()):
        parts.append(f"{count} {rtype}{'s' if count > 1 else ''}")
    return ", ".join(parts)
```

#### 3.3.2 修改 `modify_request`

```python
def modify_request(self, request: ModelRequest) -> ModelRequest:
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

    new_system_message = append_to_system_message(
        request.system_message, skills_section,
    )
    return request.override(system_message=new_system_message)
```

#### 3.3.3 更新 `SKILLS_SYSTEM_PROMPT` 模板

```python
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

**When to Use Skills:**
- User's request matches a skill's domain (e.g., "research X" -> \
web-research skill)
- You need specialized knowledge or structured workflows
- A skill provides proven patterns for complex tasks

Remember: Skills make you more capable and consistent. When in doubt, check \
if a skill exists for the task!
"""
```

**变更说明**。相比 V1 模板，V2 模板的主要变化是：将步骤 2 从"Read the skill's full instructions（使用 path）"改为"Load the skill（使用 `load_skill`）"，引导 Agent 使用专用工具而非通用的 `read_file`。同时移除了"Executing Skill Scripts"和"Example Workflow"部分，因为这些信息会在 `load_skill` 返回的内容中按需提供，符合渐进式披露原则。

### 3.4 `allowed-tools` 策略引擎（`wrap_tool_call` 新增）

`wrap_tool_call` 是 V2 新增的 hook，专门用于实施 `allowed-tools` 运行时策略。

#### 3.4.1 策略模式设计

`allowed-tools` 的语义需要特别注意。在 Agent Skills 规范中，`allowed-tools` 被标记为**实验性**字段，其语义是"推荐使用的工具"（recommendation），而非"限制只能使用的工具"（restriction）。当前 V1 代码注释也将其描述为 `"Tool names the skill recommends using"`。

然而，Claude Code 原生系统中 `allowed-tools` 的语义是"活跃时无需询问权限的工具"（tools that don't need permission when active），这是一种更强的语义。

为了同时支持两种语义，V2 引入一个可配置的策略模式：

```python
from enum import Enum


class AllowedToolsPolicy(str, Enum):
    """allowed-tools 字段的执行策略。"""
    RECOMMEND = "recommend"   # 默认：仅在系统提示中推荐，不阻止其他工具
    RESTRICT = "restrict"     # 严格：阻止未在 allowed-tools 中列出的工具调用
```

**`RECOMMEND` 模式**（默认）：`allowed-tools` 信息仅在系统提示中显示为推荐，不进行运行时阻止。这保持了与 Agent Skills 规范的一致性，也是 V1 的行为。

**`RESTRICT` 模式**：当至少一个已加载的技能定义了 `allowed-tools` 时，未在列表中的工具调用将被阻止。

#### 3.4.2 实现方案

```python
# 内置工具白名单：这些工具始终允许调用，不受 allowed-tools 限制
_ALWAYS_ALLOWED_TOOLS = frozenset({
    "load_skill",       # 技能加载工具本身
    "write_todos",      # 任务管理
    "read_file",        # 文件读取（资源访问需要）
    "ls",               # 目录列表（资源发现需要）
})


def wrap_tool_call(
    self,
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """拦截工具调用以实施 allowed-tools 策略。
    
    在 RECOMMEND 模式下，此方法直接透传所有调用。
    在 RESTRICT 模式下，此方法会检查工具是否在已加载技能的
    allowed-tools 列表中，不在列表中的工具调用将被阻止。
    """
    # 快速路径：RECOMMEND 模式不做任何拦截
    if self._allowed_tools_policy != AllowedToolsPolicy.RESTRICT:
        return handler(request)
    
    # RESTRICT 模式：检查 allowed-tools
    block_message = self._check_allowed_tools(request)
    if block_message is not None:
        return block_message
    
    return handler(request)


async def awrap_tool_call(
    self,
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
) -> ToolMessage | Command:
    """拦截工具调用以实施 allowed-tools 策略（异步版本）。"""
    if self._allowed_tools_policy != AllowedToolsPolicy.RESTRICT:
        return await handler(request)
    
    block_message = self._check_allowed_tools(request)
    if block_message is not None:
        return block_message
    
    return await handler(request)


def _check_allowed_tools(self, request: ToolCallRequest) -> ToolMessage | None:
    """检查工具调用是否符合 allowed-tools 策略。
    
    Returns:
        None 如果允许调用，ToolMessage（status="error"）如果需要阻止。
    """
    tool_name = request.tool_call["name"]
    
    # 内置工具始终允许
    if tool_name in _ALWAYS_ALLOWED_TOOLS:
        return None
    
    # 获取已加载技能的 allowed-tools 集合
    state = request.runtime.state
    loaded_skills = set(state.get("skills_loaded", []))
    if not loaded_skills:
        return None  # 没有加载任何技能时不限制
    
    skills_metadata = state.get("skills_metadata", [])
    all_allowed: set[str] = set()
    has_any_restriction = False
    
    for skill in skills_metadata:
        if skill["name"] in loaded_skills and skill["allowed_tools"]:
            has_any_restriction = True
            all_allowed.update(skill["allowed_tools"])
    
    if not has_any_restriction:
        return None  # 已加载的技能都没有定义 allowed-tools
    
    if tool_name not in all_allowed:
        return ToolMessage(
            content=(
                f"Tool '{tool_name}' is not in the allowed-tools list for the "
                f"currently loaded skills. Allowed tools: "
                f"{', '.join(sorted(all_allowed))}. "
                f"If you believe this tool is necessary, explain your reasoning."
            ),
            tool_call_id=request.tool_call["id"],
            status="error",
        )
    
    return None
```

**设计决策说明**。`_ALWAYS_ALLOWED_TOOLS` 白名单确保了核心功能不会被意外阻止。`load_skill` 必须始终可用（否则无法加载新技能），`read_file` 和 `ls` 必须可用（否则无法访问技能资源），`write_todos` 必须可用（否则无法管理任务）。

---

## 4. 向后兼容性保证

### 4.1 公开 API 兼容性

| API 元素 | V1 | V2 | 兼容性 |
| :--- | :--- | :--- | :---: |
| `SkillsMiddleware.__init__(backend, sources)` | ✅ | ✅（新增可选参数 `allowed_tools_policy`，默认 `RECOMMEND`） | ✅ |
| `SkillMetadata` TypedDict | 7 个字段 | 7 个字段（不变） | ✅ |
| `SkillsState.skills_metadata` | `NotRequired` | `NotRequired`（不变） | ✅ |
| `create_deep_agent(skills=...)` | 传入 source 路径列表 | 传入 source 路径列表（不变） | ✅ |
| `__all__` 导出 | `["SkillMetadata", "SkillsMiddleware"]` | `["SkillMetadata", "SkillsMiddleware", "AllowedToolsPolicy", "ResourceMetadata"]` | ✅ |

### 4.2 行为兼容性

**现有 SKILL.md 文件**。所有现存的 `SKILL.md` 文件无需任何修改。V2 新增的资源发现是增量功能——如果技能目录下没有 `scripts/`, `references/`, `assets/` 子目录，`skill_resources` 中对应的列表为空，不影响任何现有行为。

**Agent 行为**。V2 的系统提示引导 Agent 使用 `load_skill` 工具，但 Agent 仍然可以通过 `read_file` 直接读取 `SKILL.md`。区别在于：通过 `read_file` 读取不会触发状态更新（`skills_loaded` 不会被更新），因此不会获得资源摘要和加载状态标记。这是一种优雅降级，不会导致错误。

**`allowed_tools_policy` 默认值**。默认为 `RECOMMEND`，与 V1 行为完全一致（仅显示，不限制）。只有显式设置为 `RESTRICT` 才会启用运行时限制。

### 4.3 SubAgent 隔离

当前架构中，主 Agent 和 SubAgent 各自拥有独立的 `SkillsMiddleware` 实例（在 `graph.py` 中分别创建）。由于 `skills_loaded` 和 `skill_resources` 都使用 `PrivateStateAttr`，它们不会传播到父级或子级 Agent。这意味着：

- 主 Agent 加载的技能不会自动在 SubAgent 中生效。
- SubAgent 的 `skills_loaded` 状态独立于主 Agent。
- 通用子代理（general-purpose subagent）自动继承主 Agent 的 skills sources 配置（由 `graph.py` 保证），但其加载状态是独立的。

---

## 5. 错误处理与降级策略

### 5.1 资源发现降级

如果 `backend.ls_info()` 在扫描资源目录时抛出异常（例如某些简化的 backend 实现不支持目录列表），`_discover_resources` 会捕获异常并记录警告，返回空列表。这确保了资源发现失败不会阻止技能系统的正常运行。

### 5.2 `load_skill` 工具错误处理

`load_skill` 工具的所有错误都通过返回描述性错误字符串来处理（而不是抛出异常或返回 `Command`），这确保了 Agent 可以理解错误并采取替代行动：

| 错误场景 | 返回类型 | 返回消息 | Agent 可采取的行动 |
| :--- | :---: | :--- | :--- |
| 技能名称不存在 | `str` | `"Error: Skill 'xxx' not found. Available skills: ..."` | 检查可用技能列表，修正名称 |
| 技能已加载 | `str` | `"Skill 'xxx' is already loaded."` | 直接使用已加载的技能指令 |
| 文件读取失败 | `str` | `"Error: Failed to read skill file at ..."` | 使用 `read_file` 作为后备 |
| 文件超过大小限制 | `str` | `"Error: Skill file at ... exceeds maximum size"` | 报告问题给用户 |
| 编码错误 | `str` | `"Error: Failed to decode skill file: ..."` | 报告问题给用户 |
| 成功加载 | `Command` | 技能内容 + 资源摘要（通过 `ToolMessage`） | 按照技能指令执行 |

**关键设计**：只有成功加载时才返回 `Command`（更新 `skills_loaded` 状态），所有错误情况都返回普通字符串（不更新状态）。这确保了只有真正成功加载的技能才会被标记为"已加载"。

### 5.3 `wrap_tool_call` 降级

`wrap_tool_call` 的 `_check_allowed_tools` 方法在以下情况下自动放行：

1. 策略为 `RECOMMEND` 模式（默认）。
2. 没有任何技能被加载（`skills_loaded` 为空）。
3. 已加载的技能都没有定义 `allowed-tools` 字段。

这种多层降级确保了 `allowed-tools` 限制只在明确需要时才生效。

---

## 6. 测试策略

### 6.1 单元测试

以下测试用例应覆盖 V2 的所有新功能：

| 测试类别 | 测试用例 | 验证目标 |
| :--- | :--- | :--- |
| 资源发现 | `test_discover_resources_standard_dirs` | 正确发现 `scripts/`, `references/`, `assets/` 下的文件 |
| 资源发现 | `test_discover_resources_empty_skill` | 无资源目录时返回空列表 |
| 资源发现 | `test_discover_resources_backend_error` | backend 异常时优雅降级，返回空列表 |
| 资源发现 | `test_discover_resources_non_standard_dirs_ignored` | 非标准目录（如 `temp/`）被忽略 |
| 资源发现 | `test_discover_resources_root_level_files` | 根级别非 SKILL.md 文件被标记为 `"other"` 类型 |
| 状态初始化 | `test_before_agent_initializes_new_state` | `skills_loaded` 初始化为 `[]`，`skill_resources` 正确填充 |
| 状态初始化 | `test_before_agent_idempotent` | 重复调用返回 `None`，不覆盖已有状态 |
| load_skill | `test_load_skill_returns_command_with_content` | 成功加载返回 `Command`，包含技能内容和资源摘要 |
| load_skill | `test_load_skill_updates_skills_loaded` | `Command.update` 中 `skills_loaded` 包含新技能名称 |
| load_skill | `test_load_skill_not_found_returns_error` | 技能不存在时返回错误字符串（非 `Command`） |
| load_skill | `test_load_skill_already_loaded_returns_message` | 已加载技能返回提示字符串（非 `Command`） |
| load_skill | `test_load_skill_file_read_error` | 文件读取失败时返回错误字符串 |
| load_skill | `test_load_skill_file_size_exceeded` | 超过 `MAX_SKILL_FILE_SIZE` 时返回错误字符串 |
| 权限控制 | `test_allowed_tools_recommend_mode_passthrough` | `RECOMMEND` 模式不拦截任何工具调用 |
| 权限控制 | `test_allowed_tools_restrict_mode_allows_listed` | `RESTRICT` 模式允许列表内工具 |
| 权限控制 | `test_allowed_tools_restrict_mode_blocks_unlisted` | `RESTRICT` 模式阻止列表外工具，返回 `ToolMessage(status="error")` |
| 权限控制 | `test_allowed_tools_whitelist_always_allowed` | 白名单工具（`load_skill`, `read_file` 等）始终不被阻止 |
| 权限控制 | `test_allowed_tools_no_loaded_skills_passthrough` | 无已加载技能时不限制 |
| 权限控制 | `test_allowed_tools_no_restrictions_defined_passthrough` | 已加载技能无 `allowed-tools` 定义时不限制 |
| 系统提示 | `test_format_skills_list_with_loaded_status` | 已加载技能显示 `[Loaded]` 标记 |
| 系统提示 | `test_format_skills_list_with_resources` | 资源摘要正确显示（如 "2 scripts, 1 reference"） |
| 系统提示 | `test_format_skills_list_load_skill_guidance` | 未加载技能显示 `load_skill("name")` 引导 |
| 向后兼容 | `test_v1_skills_work_without_modification` | 无 V2 字段的 SKILL.md 正常工作 |
| 向后兼容 | `test_default_policy_is_recommend` | 默认策略为 `RECOMMEND` |
| 向后兼容 | `test_read_file_still_works_for_skills` | 通过 `read_file` 读取技能不会导致错误 |

### 6.2 集成测试

集成测试应验证 `SkillsMiddleware` 与其他中间件的协作：

1. **与 `FilesystemMiddleware` 的协作**：验证 `load_skill` 工具和 `read_file` 工具可以共存，且 Agent 可以先用 `load_skill` 加载技能，再用 `read_file` 读取资源。
2. **与 `SubAgentMiddleware` 的协作**：验证主 Agent 和 SubAgent 的 `skills_loaded` 状态相互隔离。
3. **与 `SummarizationMiddleware` 的协作**：验证技能系统提示在上下文压缩后仍然正确。

---

## 7. 扩展路线图

本节描述 V2 之后的扩展方向，这些功能在当前版本中仅预留扩展点，不实现。

### 7.1 Phase 3: 高级 Frontmatter 字段支持

| 字段 | 描述 | 实现思路 | 复杂度 |
| :--- | :--- | :--- | :---: |
| `disable-model-invocation` | 禁止模型自动加载技能 | 在 `_format_skills_list` 中为标记了此字段的技能添加 `(Manual only)` 标记，并在系统提示中说明"不要自动加载此技能" | 低 |
| `argument-hint` | 参数提示 | 在系统提示中显示提示文本，如 `load_skill("deploy", args="[env-name]")` | 低 |
| `model` | 模型覆盖 | 需要与 `wrap_model_call` 集成，在加载了指定 `model` 的技能后通过 `request.override` 切换模型。可能需要框架层面支持 | 高 |
| `context: fork` | 子代理执行 | 需要与 `SubAgentMiddleware` 深度集成，在 `load_skill` 时创建子代理上下文。可通过 `agent jumps` 机制（返回 `{"jump_to": "tools"}` 等）实现流程控制 | 高 |

### 7.2 Phase 4: 事件钩子系统

Claude Code 的 hooks 系统支持 14 种事件类型（`PreToolUse`, `PostToolUse`, `SessionStart` 等），处理器类型包括 `command`（Shell 命令）、`prompt`（LLM 提示）和 `agent`（代理钩子）。

在 DeepAgents 中实现类似系统的可行路径是：

1. **在 `SkillMetadata` 中新增 `hooks` 字段**，解析 SKILL.md frontmatter 中的 hooks 定义（YAML 格式）。
2. **将 hooks 事件映射到 `AgentMiddleware` 的 hook 点**：`PreToolUse` 映射到 `wrap_tool_call`（前置检查），`PostToolUse` 映射到 `wrap_tool_call`（后置处理），`SessionStart` 映射到 `before_agent`。
3. **实现 `command` 类型处理器**：通过 `backend.execute()`（如果 backend 实现了 `SandboxBackendProtocol`）执行 Shell 命令。
4. **实现 `prompt` 类型处理器**：将提示注入到下一次模型调用的上下文中。
5. **支持 `matcher` 模式匹配**：在 `wrap_tool_call` 中根据 matcher 正则表达式匹配工具名称。
6. **支持 `once` 字段**：技能级别的 hooks 支持 `once: true`，运行一次后自动移除。

这一扩展的主要挑战在于安全性——需要确保 hooks 中的 Shell 命令在沙箱环境中执行，且不会绕过权限控制。

### 7.3 Phase 5: CLI 集成

CLI 的 `deepagents skills list/create/info` 命令需要与 V2 的新功能兼容：

1. `deepagents skills list` 应显示资源计数。
2. `deepagents skills info <name>` 应显示资源详情。
3. `deepagents skills create` 应生成包含标准资源目录的脚手架。

这些变更限于 `libs/cli/deepagents_cli/skills/` 目录，不影响核心中间件。

---

## 8. 实施计划

### 8.1 分阶段交付

| 阶段 | 时间估算 | 核心任务 | 交付物 | 验收标准 |
| :--- | :---: | :--- | :--- | :--- |
| **Phase 1** | 2-3 天 | 扩展 `SkillsState` 和 `SkillsStateUpdate`；实现 `_discover_resources` / `_adiscover_resources`；增强 `before_agent` / `abefore_agent`；创建 `load_skill` 工具（sync + async） | 支持资源发现和状态追踪的中间件 | 所有 V1 测试通过 + 13 个新增单元测试通过 |
| **Phase 2** | 2-3 天 | 实现 `AllowedToolsPolicy` 枚举；实现 `wrap_tool_call` / `awrap_tool_call`（`allowed-tools` 策略）；优化 `_format_skills_list` 和系统提示模板 | 完整的 V2 中间件 | 所有 24 个单元测试通过 + 3 个集成测试通过 |
| **Phase 3** | 1 天 | 文档更新、代码审查、性能测试 | 可合并的 PR | 代码审查通过、无性能回归 |

### 8.2 文件变更清单

| 文件 | 变更类型 | 变更内容 |
| :--- | :---: | :--- |
| `deepagents/middleware/skills.py` | 修改 | 新增 `ResourceMetadata`、`AllowedToolsPolicy`；扩展 `SkillsState` / `SkillsStateUpdate`；新增 `_discover_resources` / `_adiscover_resources`；增强 `before_agent` / `abefore_agent`；新增 `_create_load_skill_tool` / `_execute_load_skill` / `_aexecute_load_skill`；新增 `wrap_tool_call` / `awrap_tool_call` / `_check_allowed_tools`；增强 `_format_skills_list` / `modify_request`；更新 `SKILLS_SYSTEM_PROMPT`；更新 `__all__` |
| `tests/unit_tests/middleware/test_skills_middleware.py` | 修改 | 新增 24 个测试用例 |
| `tests/integration_tests/test_skills_integration.py` | 新增 | 3 个集成测试 |

**不变更的文件**：`graph.py`、`middleware/__init__.py`、`middleware/_utils.py`、`middleware/filesystem.py`、`middleware/memory.py`、`middleware/subagents.py`、`middleware/summarization.py`、`middleware/patch_tool_calls.py`、`backends/protocol.py`。

---

## 附录 A：完整的新增/修改方法清单

| 方法 | 类型 | 描述 |
| :--- | :---: | :--- |
| `_discover_resources()` | 新增（模块级） | 同步资源发现 |
| `_adiscover_resources()` | 新增（模块级） | 异步资源发现 |
| `_format_resource_summary()` | 新增（模块级） | 资源摘要格式化 |
| `SkillsMiddleware.__init__()` | 修改 | 新增 `allowed_tools_policy` 参数、`self.tools` 属性 |
| `SkillsMiddleware._create_load_skill_tool()` | 新增 | 创建 load_skill 工具 |
| `SkillsMiddleware._get_backend_from_runtime()` | 新增 | 从 ToolRuntime 解析 backend |
| `SkillsMiddleware._execute_load_skill()` | 新增 | load_skill 同步核心逻辑 |
| `SkillsMiddleware._aexecute_load_skill()` | 新增 | load_skill 异步核心逻辑 |
| `SkillsMiddleware._format_skills_list()` | 修改 | 新增 `loaded` 和 `resources` 参数 |
| `SkillsMiddleware.modify_request()` | 修改 | 传入新状态字段 |
| `SkillsMiddleware.before_agent()` | 修改 | 新增资源发现和状态初始化 |
| `SkillsMiddleware.abefore_agent()` | 修改 | 新增资源发现和状态初始化（异步） |
| `SkillsMiddleware.wrap_tool_call()` | 新增 | allowed-tools 策略检查 |
| `SkillsMiddleware.awrap_tool_call()` | 新增 | allowed-tools 策略检查（异步） |
| `SkillsMiddleware._check_allowed_tools()` | 新增 | allowed-tools 权限检查逻辑 |

---

## 参考文献

[1]: Agent Skills. "Agent Skills Specification." agentskills.io. Accessed Feb 16, 2026. https://agentskills.io/specification

[2]: Anthropic. "Skills - Claude Code." code.claude.com. Accessed Feb 16, 2026. https://code.claude.com/docs/en/skills

[3]: LangChain. "Custom Middleware." docs.langchain.com. Accessed Feb 16, 2026. https://docs.langchain.com/oss/python/langchain/middleware/custom

[4]: LangChain. "Deep Agents Skills." docs.langchain.com. Accessed Feb 16, 2026. https://docs.langchain.com/oss/python/deepagents/skills
