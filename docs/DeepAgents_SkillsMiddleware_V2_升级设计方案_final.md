# DeepAgents SkillsMiddleware V2 升级设计方案

**版本**: 1.0（Final）
**日期**: 2026-02-17
**状态**: 生产就绪

---

## 目录

1. [概述](#1-概述)
2. [架构设计](#2-架构设计)
3. [实现方案](#3-实现方案)
4. [上下文预算管理](#4-上下文预算管理)
5. [向后兼容性保证](#5-向后兼容性保证)
6. [错误处理与降级策略](#6-错误处理与降级策略)
7. [测试策略](#7-测试策略)
8. [扩展路线图](#8-扩展路线图)
9. [实施计划](#9-实施计划)
10. [已知限制与约束](#10-已知限制与约束)

---

## 1. 概述

### 1.1 文档目的

本文档为 `deepagents.middleware.skills.SkillsMiddleware` 的 V2 版本升级提供完整的设计与实现方案。方案基于对 [Agent Skills 开放规范][1]、[Claude Code 原生 Skill 系统][2]、[Coze 技能系统][3]、以及 DeepAgents 现有框架架构的深入分析，旨在将现有中间件从基础的技能发现与提示注入器，升级为一个功能完备、安全可控、高度可扩展的技能运行时系统。

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

**无上下文预算管理**。当技能数量增长时，系统提示中的技能列表会无限膨胀，没有任何机制防止 prompt 超长。同时，Agent 可以无限制地加载技能内容，导致上下文窗口被技能指令占满。

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
| **纳入范围** | 技能加载状态追踪、延迟资源发现、专用 `load_skill` 工具、`allowed-tools` 运行时建议/限制、系统提示优化、上下文预算管理（描述层 + 内容层）、白名单可扩展性 |
| **排除范围** | `hooks` 事件系统实现、`context: fork` 子代理执行、`model` 字段覆盖、`argument-hint` / `$ARGUMENTS` 替换、`disable-model-invocation` / `user-invocable` 控制、CLI 命令扩展、SubAgent 技能继承 |

排除范围中的功能将在后续版本中按优先级逐步引入，本文档第 8 节提供了详细的扩展路线图。

---

## 2. 架构设计

### 2.1 Hook 使用规划

V2 将在 V1 的基础上，新增对 `wrap_tool_call` hook 的使用。以下是完整的 hook 使用规划：

| Hook | V1 使用 | V2 使用 | 职责 |
| :--- | :---: | :---: | :--- |
| `before_agent` / `abefore_agent` | ✅ | ✅ | 技能发现、元数据解析、状态初始化 |
| `wrap_model_call` / `awrap_model_call` | ✅ | ✅ | 系统提示注入（含加载状态标记、上下文预算控制） |
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
    4. 作为内容层预算（max_loaded_skills）的计数依据
    """

    # V2 新增
    skill_resources: NotRequired[Annotated[dict[str, list[ResourceMetadata]], PrivateStateAttr]]
    """已发现的技能资源映射，键为技能名称。

    采用延迟发现策略：在 load_skill 被调用时按需扫描该技能的资源目录，
    结果缓存在此字段中。采用 dict 结构（而非 flat list）以支持按技能名称的 O(1) 查找。
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

**设计决策说明**。`skill_resources` 采用 `dict[str, list[ResourceMetadata]]` 而非 `list[ResourceMetadata]`，原因是 `load_skill` 工具在返回技能内容时需要附带该技能的资源列表，按技能名称索引可以避免每次都遍历整个列表。资源与元数据分离（独立状态字段而非扩展 `SkillMetadata`），避免了每次元数据查询都携带资源信息。

### 2.3 工具设计

V2 将引入一个新的专用工具 `load_skill`，通过 `self.tools` 属性提供给框架。这与 `FilesystemMiddleware` 在 `__init__` 中创建 `self.tools = [self._create_ls_tool(), self._create_read_file_tool(), ...]` 的模式完全一致。

#### 2.3.1 `load_skill` 工具

```
load_skill(skill_name: str) -> str | Command
```

**工具行为**：

1. 从 `runtime.state["skills_metadata"]` 中查找匹配的技能，获取其 `path`。
2. **内容层预算检查**：如果 `skills_loaded` 长度已达到 `max_loaded_skills`，返回错误消息。
3. 通过 `backend.download_files([path])` 读取 `SKILL.md` 的完整内容。
4. **延迟资源发现**：如果 `skill_resources` 中没有该技能的缓存，按需扫描资源目录并缓存结果。
5. 构建返回内容：`SKILL.md` 内容 + 资源摘要（如果有资源）。
6. **状态更新**：通过返回 `Command` 将 `skill_name` 添加到 `skills_loaded` 列表中，同时更新 `skill_resources` 缓存，并携带 `ToolMessage` 作为工具响应。

**为何不引入 `load_skill_resource` 工具**。经过评审，我们决定不引入单独的 `load_skill_resource` 工具，原因如下：现有的 `read_file` 工具（由 `FilesystemMiddleware` 提供）已经完全能够读取资源文件，且 `load_skill` 返回的资源摘要中会包含完整的路径。引入冗余工具会增加 Agent 的认知负担，违反"最小侵入性"原则。

**`load_skill` 的幂等性说明**。`load_skill` 的幂等性是基于自身状态（`skills_loaded`）的，不感知外部 `read_file` 操作。如果 Agent 先通过 `read_file` 读取了 `SKILL.md`，再调用 `load_skill`，由于 `skills_loaded` 中没有该技能名称，工具会正常执行并返回 `Command`。这是预期行为——`read_file` 是通用文件读取操作，不会触发技能系统的状态更新。只有通过 `load_skill` 加载的技能才会被纳入状态追踪和权限管理。

#### 2.3.2 工具提供机制

**关键设计决策：状态更新在工具函数内部完成**。与 `FilesystemMiddleware` 的 `write_file` 工具模式一致，`load_skill` 工具函数在需要更新状态时直接返回 `Command` 对象。`Command` 的 `update` 字段包含要合并到 agent state 中的字段（如 `skills_loaded`），同时通过 `messages` 字段携带 `ToolMessage` 作为工具响应。这种模式避免了在 `wrap_tool_call` 中进行复杂的状态更新逻辑，保持了关注点分离。

### 2.4 上下文预算管理

为防止 prompt 超长，V2 引入**双重上下文预算管理机制**。这一设计参考了业界成熟系统的实践：

| 系统 | 描述层限制 | 内容层限制 | 策略 |
| :--- | :--- | :--- | :--- |
| **Claude Code** [5] | 2% 上下文窗口（fallback 16,000 chars） | 无明确限制，按需加载 | 超出预算的技能从系统提示中排除 |
| **Coze** [3] | 无明确字符限制 | 50 个编程技能 / 30 个第三方技能 | 硬数量限制 |
| **OpenAI Assistants** [4] | 无明确限制 | 128 个工具 | 硬数量限制 |
| **Manus** | ~100 tokens/技能 | <5K tokens/技能 | 三阶段渐进式 |

#### 2.4.1 描述层预算（系统提示中的技能列表）

**问题**。每个技能在系统提示中占据一定空间（名称 + 描述 + 注解 + 引导语），当技能数量增长时，系统提示会无限膨胀。根据 Claude Code 的实测数据 [5]，平均每个技能描述约占 263 个字符，16,000 字符的预算约可容纳 42 个技能。

**方案**。在 `_format_skills_list` 中引入 `max_description_budget` 参数（默认 16,000 字符，可配置），对技能列表进行累积字符数检查。当总字符数超过预算时，停止添加更多技能，并附加一条警告消息告知 Agent 有部分技能被省略。

**排除策略**。当预算不足时，按以下优先级保留技能：
1. **已加载的技能**（`skills_loaded` 中的技能）始终保留——它们是当前会话的活跃技能。
2. **未加载的技能**按发现顺序排列，后面的 source 优先级更高（与 V1 的 "last one wins" 语义一致）。

#### 2.4.2 内容层预算（同时加载的技能数量）

**问题**。每次 `load_skill` 调用会将完整的 `SKILL.md` 内容注入到对话上下文中。如果 Agent 连续加载多个大型技能，对话上下文会迅速膨胀，导致模型回忆准确性下降（Context Rot）[6]。

**方案**。在 `_execute_load_skill` 中引入 `max_loaded_skills` 参数（默认 10，可配置），检查 `skills_loaded` 列表的长度。如果已加载的技能数量达到上限，阻止加载新技能并返回描述性错误消息，告知 Agent 已达到加载上限。

**默认值选择依据**。默认值 10 基于以下考量：
- Claude Code 的实测数据显示，16K 字符的描述预算约可容纳 42 个技能描述，但完整 SKILL.md 内容远大于描述。
- Coze 的第三方技能限制为 30 个，编程技能为 50 个。
- 典型的 SKILL.md 文件在 1-5KB 之间，10 个技能约占 10-50KB 的上下文空间，对于 128K-200K token 的模型上下文窗口是合理的。
- 此值可通过 `max_loaded_skills` 参数按需调整。


## 3. 实现方案

### 3.1 `__init__` 扩展

`SkillsMiddleware.__init__` 新增三个可选参数，所有参数均有默认值以保证向后兼容：

```python
class SkillsMiddleware(AgentMiddleware):
    state_schema = SkillsState

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        sources: list[str],
        # V2 新增参数
        allowed_tools_policy: AllowedToolsPolicy = AllowedToolsPolicy.RECOMMEND,
        max_description_budget: int = 16_000,
        max_loaded_skills: int = 10,
        always_allowed_tools: frozenset[str] | None = None,
    ) -> None:
        self._backend = backend
        self.sources = sources
        self.system_prompt_template = SKILLS_SYSTEM_PROMPT

        # V2 新增
        self._allowed_tools_policy = allowed_tools_policy
        self._max_description_budget = max_description_budget
        self._max_loaded_skills = max_loaded_skills
        self._always_allowed_tools = always_allowed_tools or _DEFAULT_ALWAYS_ALLOWED_TOOLS

        # V2: 创建专用工具（与 FilesystemMiddleware 模式一致）
        self.tools = [
            self._create_load_skill_tool(),
        ]
```

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `allowed_tools_policy` | `AllowedToolsPolicy` | `RECOMMEND` | `allowed-tools` 字段的执行策略 |
| `max_description_budget` | `int` | `16_000` | 描述层预算（字符数），控制系统提示中技能列表的最大长度 |
| `max_loaded_skills` | `int` | `10` | 内容层预算，控制同时加载的技能数量上限 |
| `always_allowed_tools` | `frozenset[str] | None` | `None`（使用默认白名单） | RESTRICT 模式下始终允许调用的工具集合 |

### 3.2 延迟资源发现

V2 采用延迟发现策略（Lazy Discovery）：`before_agent` 阶段不再扫描资源目录，资源发现推迟到 `load_skill` 被调用时按需执行。这一决策基于以下考量：

1. 典型技能库可能有 50-100 个技能，每次 invocation 都扫描所有资源目录是不必要的开销。
2. 资源信息仅在技能被实际加载时才有价值——Agent 需要知道加载后的技能有哪些可用资源。
3. 延迟发现不影响 Agent 对技能的理解和选择——技能列表中的 `name` + `description` 足以支持选择决策。

#### 3.2.1 `_discover_resources` 辅助函数

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

**扫描深度说明**。资源发现仅扫描标准资源目录（`scripts/`, `references/`, `assets/`）的第一层子目录，不会递归扫描嵌套目录。例如，`scripts/utils/helper.py` 不会被发现，但 `scripts/helper.py` 会被发现。这是有意的设计选择，与 Agent Skills 规范的扁平资源目录结构一致。如果未来需要支持深层扫描，可以在 `_discover_resources` 中添加递归选项，而不影响公开 API。

### 3.3 增强后的 `before_agent` / `abefore_agent`

`before_agent` 的变更是最小的：仅新增 `skills_loaded` 和 `skill_resources` 的初始化，不再包含资源扫描逻辑。

```python
def before_agent(
    self, state: SkillsState, runtime: Runtime, config: RunnableConfig,
) -> SkillsStateUpdate | None:
    # 幂等检查：如果 skills_metadata 已存在，跳过
    if "skills_metadata" in state:
        return None

    backend = self._get_backend(state, runtime, config)
    all_skills: dict[str, SkillMetadata] = {}

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
    if "skills_metadata" in state:
        return None

    backend = self._get_backend(state, runtime, config)
    all_skills: dict[str, SkillMetadata] = {}

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

**幂等性保证**。V1 通过 `if "skills_metadata" in state` 实现幂等。由于 V2 的 `SkillsStateUpdate` 同时写入所有三个字段，只需检查 `skills_metadata` 即可保证所有字段的幂等性——如果 `skills_metadata` 已存在，则 `skills_loaded` 和 `skill_resources` 也必然已存在（它们在同一个 `StateUpdate` 中写入）。

### 3.4 `load_skill` 工具实现

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
```

#### 3.4.1 `_execute_load_skill` 核心逻辑

```python
def _execute_load_skill(
    self,
    backend: BackendProtocol,
    skill_name: str,
    runtime: ToolRuntime[None, SkillsState],
) -> Command | str:
    """load_skill 核心逻辑（同步版本）。"""
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

    # 内容层预算检查
    if len(loaded_skills) >= self._max_loaded_skills:
        return (
            f"Error: Cannot load skill '{skill_name}'. "
            f"Maximum number of simultaneously loaded skills reached "
            f"({self._max_loaded_skills}). "
            f"Currently loaded: {', '.join(loaded_skills)}. "
            f"Consider whether all loaded skills are still needed for the current task."
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
    """load_skill 核心逻辑（异步版本）。"""
    state = runtime.state
    skills_metadata = state.get("skills_metadata", [])
    skill_resources = dict(state.get("skill_resources", {}))
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

    # 内容层预算检查
    if len(loaded_skills) >= self._max_loaded_skills:
        return (
            f"Error: Cannot load skill '{skill_name}'. "
            f"Maximum number of simultaneously loaded skills reached "
            f"({self._max_loaded_skills}). "
            f"Currently loaded: {', '.join(loaded_skills)}. "
            f"Consider whether all loaded skills are still needed for the current task."
        )

    responses = await backend.adownload_files([target_skill["path"]])
    response = responses[0]

    if response.error or response.content is None:
        return f"Error: Failed to read skill file at {target_skill['path']}: {response.error}"

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

**关于 `Command` 模式的说明**。此处的 `Command` 使用方式与 `FilesystemMiddleware` 的 `write_file` 工具完全一致。当 `write_file` 成功写入文件后，它返回 `Command(update={"files": res.files_update, "messages": [ToolMessage(content=..., tool_call_id=runtime.tool_call_id)]})` 来同时更新状态和返回工具响应。`load_skill` 采用相同的模式：成功加载后返回 `Command` 来更新 `skills_loaded` 和 `skill_resources` 状态并返回技能内容。

### 3.5 系统提示优化（`wrap_model_call` 增强）

`wrap_model_call` 的核心逻辑（调用 `modify_request` 注入系统提示）保持不变，但 `_format_skills_list` 将被增强以反映加载状态，并引入描述层预算控制。

#### 3.5.1 增强后的 `_format_skills_list`

```python
def _format_skills_list(
    self,
    skills: list[SkillMetadata],
    loaded: list[str],
    resources: dict[str, list[ResourceMetadata]],
) -> str:
    """格式化技能列表用于系统提示显示。

    V2 增强：显示加载状态标记、资源摘要、load_skill 引导语，
    并实施描述层预算控制。
    """
    if not skills:
        paths = [f"{source_path}" for source_path in self.sources]
        return (
            f"(No skills available yet. You can create skills in "
            f"{' or '.join(paths)})"
        )

    lines = []
    total_chars = 0
    loaded_set = set(loaded)
    excluded_count = 0

    # 排序：已加载的技能优先（确保它们不会被预算截断）
    sorted_skills = sorted(
        skills,
        key=lambda s: (0 if s["name"] in loaded_set else 1),
    )

    for skill in sorted_skills:
        name = skill["name"]
        annotations = _format_skill_annotations(skill)

        # V2: 标记已加载状态
        status = " [Loaded]" if name in loaded_set else ""
        desc_line = f"- **{name}**{status}: {skill['description']}"
        if annotations:
            desc_line += f" ({annotations})"

        skill_lines = [desc_line]

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

        # 描述层预算检查
        skill_text = "\n".join(skill_lines)
        skill_chars = len(skill_text)

        # 已加载的技能始终保留，不受预算限制
        if name not in loaded_set and total_chars + skill_chars > self._max_description_budget:
            excluded_count += 1
            continue

        total_chars += skill_chars
        lines.append(skill_text)

    # 预算超出警告
    if excluded_count > 0:
        lines.append(
            f"\n({excluded_count} additional skill(s) not shown due to "
            f"description budget limit. Use `ls` to browse skill directories "
            f"for a complete list.)"
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

#### 3.5.2 修改 `modify_request`

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

#### 3.5.3 更新 `SKILLS_SYSTEM_PROMPT` 模板

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

### 3.6 `allowed-tools` 策略引擎（`wrap_tool_call` 新增）

`wrap_tool_call` 是 V2 新增的 hook，专门用于实施 `allowed-tools` 运行时策略。

#### 3.6.1 策略模式设计

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

#### 3.6.2 实现方案

```python
# 内置工具白名单：这些工具始终允许调用，不受 allowed-tools 限制
_DEFAULT_ALWAYS_ALLOWED_TOOLS = frozenset({
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
    if tool_name in self._always_allowed_tools:
        return None

    # 获取已加载技能的 allowed-tools 集合
    state = request.state
    loaded_skills = set(state.get("skills_loaded", []))
    if not loaded_skills:
        return None  # 没有加载任何技能时不限制

    skills_metadata = state.get("skills_metadata", [])
    has_undefined_skill = False
    has_defined_skill = False
    all_allowed: set[str] = set()

    for skill in skills_metadata:
        if skill["name"] in loaded_skills:
            if skill["allowed_tools"]:
                has_defined_skill = True
                all_allowed.update(skill["allowed_tools"])
            else:
                has_undefined_skill = True

    # 如果任何已加载技能没有定义 allowed-tools，则不限制
    if has_undefined_skill or not has_defined_skill:
        return None

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

**白名单可扩展性说明**。`_DEFAULT_ALWAYS_ALLOWED_TOOLS` 作为模块级常量定义默认白名单，但实际使用的白名单存储在实例属性 `self._always_allowed_tools` 中。开发者可以通过 `__init__` 的 `always_allowed_tools` 参数传入自定义白名单，覆盖默认值。这解决了研发团队提出的"白名单维护成本"问题——当新中间件引入新工具时，可以在创建 `SkillsMiddleware` 实例时扩展白名单，而无需修改 `skills.py` 源码。

> **关于模式匹配的说明**：研发团队建议使用前缀模式匹配（如 `_MIDDLEWARE_TOOL_PREFIXES = ("fs_", "todo_", "skill_")`）来降低维护成本。经过评估，当前 DeepAgents 的工具命名不遵循统一前缀规范（`read_file`, `write_file`, `ls`, `grep`, `execute` 等没有 `fs_` 前缀），因此模式匹配在当前阶段不可行。如果未来工具命名规范化，可以在 `_check_allowed_tools` 中添加前缀匹配逻辑。



---

## 4. 上下文预算管理

上下文预算管理是 V2 新增的核心机制，旨在防止技能系统因加载过多技能而导致 prompt 长度超出模型上下文窗口限制。这一机制的设计参考了 Claude Code（2% 上下文窗口描述预算）、Coze（50 个编程技能 / 30 个第三方技能硬限制）、OpenAI Assistants（128 个工具硬限制）以及 Manus（三阶段渐进式加载）的成熟实践。

### 4.1 双层预算模型

V2 采用**双层预算模型**，分别控制描述层和内容层的上下文占用：

```
┌─────────────────────────────────────────────────────────────┐
│                      模型上下文窗口                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  系统提示（base_prompt + 中间件注入）                  │   │
│  │                                                      │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │  描述层（Description Budget）                │     │   │
│  │  │  ≤ max_description_budget (默认 16,000 chars)│     │   │
│  │  │  · 技能名称 + 描述 + 注解                    │     │   │
│  │  │  · 已加载标记 / load_skill 引导语            │     │   │
│  │  │  · 资源摘要（仅已加载技能）                   │     │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  对话历史（messages）                                 │   │
│  │                                                      │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │  内容层（Content Budget）                    │     │   │
│  │  │  ≤ max_loaded_skills (默认 10 个)            │     │   │
│  │  │  · load_skill 返回的完整 SKILL.md 内容       │     │   │
│  │  │  · 附加的资源摘要                            │     │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### 4.1.1 描述层预算（Description Budget）

描述层预算控制系统提示中技能列表的总字符数。默认值 `16,000` 字符参考了 Claude Code 的 2% 上下文窗口策略（200K token 窗口 × 2% ≈ 4K tokens ≈ 16K chars）。

**预算分配策略**：

1. **已加载技能优先**：已加载的技能（`skills_loaded` 中的技能）始终保留在描述列表中，不受预算限制。这确保了 Agent 始终能看到当前活跃技能的状态。
2. **按发现顺序填充**：未加载的技能按发现顺序依次填充，直到达到预算上限。
3. **超出提示**：被排除的技能数量会在列表末尾以提示形式告知 Agent，引导其通过 `ls` 命令浏览完整列表。

**容量估算**：

| 描述长度 | 可容纳技能数（16K 预算） | 适用场景 |
| :--- | :---: | :--- |
| ~100 chars | ~120 个 | 极简描述 |
| ~150 chars | ~80 个 | 简洁描述 |
| ~200 chars | ~60 个 | 标准描述 |
| ~263 chars（Claude Code 实测平均） | ~42 个 | 详细描述 |

**实现位置**：描述层预算在 `_format_skills_list` 方法中实施（见 3.5.1 节代码），通过 `self._max_description_budget` 参数控制。

#### 4.1.2 内容层预算（Content Budget）

内容层预算控制同时加载的技能数量上限。默认值 `10` 个是基于以下估算：

- 典型 SKILL.md 文件大小：2-5 KB（约 500-1250 tokens）
- 10 个技能的最大内容占用：约 50 KB（约 12,500 tokens）
- 对于 200K token 窗口，这约占 6.25%，留有充足空间给对话历史和其他中间件

**实现位置**：内容层预算在 `_execute_load_skill` 方法中实施（见 3.4.1 节代码），通过 `self._max_loaded_skills` 参数控制。当达到上限时，`load_skill` 返回描述性错误消息，提示 Agent 当前已加载的技能列表，引导其评估是否所有已加载技能仍然需要。

**关于技能卸载的说明**。V2 不实现技能卸载机制（Claude Code 同样没有卸载机制）。当 Agent 达到加载上限时，错误消息会引导 Agent 重新评估已加载技能的必要性。如果未来需要卸载能力，可以在 `load_skill` 工具旁新增 `unload_skill` 工具，从 `skills_loaded` 中移除指定技能。这不需要修改任何现有接口。

### 4.2 预算参数的可配置性

所有预算参数均通过 `__init__` 的可选参数暴露，开发者可以根据目标模型的上下文窗口大小进行调整：

```python
# 针对 Claude 3.5 Sonnet (200K context) 的默认配置
middleware = SkillsMiddleware(
    backend=backend,
    sources=["skills/"],
)

# 针对 GPT-4o (128K context) 的优化配置
middleware = SkillsMiddleware(
    backend=backend,
    sources=["skills/"],
    max_description_budget=10_000,  # 128K × 2% ≈ 2.5K tokens ≈ 10K chars
    max_loaded_skills=6,            # 更保守的加载限制
)

# 针对小模型 (32K context) 的紧凑配置
middleware = SkillsMiddleware(
    backend=backend,
    sources=["skills/"],
    max_description_budget=4_000,   # 32K × 2% ≈ 640 tokens ≈ 2.5K chars
    max_loaded_skills=3,
)
```

### 4.3 与行业实践的对比

| 维度 | Claude Code | Coze | DeepAgents V2 |
| :--- | :--- | :--- | :--- |
| 描述层限制 | 2% 上下文窗口（~16K chars） | 无明确字符限制 | 可配置（默认 16K chars） |
| 内容层限制 | 无明确数量限制 | 50 编程 / 30 第三方 | 可配置（默认 10 个） |
| 超出策略 | 排除技能，`/context` 可查 | 硬拒绝 | 排除描述 + 拒绝加载（带引导） |
| 已加载优先 | 是（活跃技能不被排除） | 不适用 | 是（已加载技能不受描述预算限制） |
| 可配置性 | 否（系统固定） | 否（系统固定） | 是（三个参数均可配置） |

---

## 5. 向后兼容性保证

### 5.1 公开 API 兼容性

| API 元素 | V1 | V2 | 兼容性 |
| :--- | :--- | :--- | :---: |
| `SkillsMiddleware.__init__(backend, sources)` | ✅ | ✅（新增可选参数 `allowed_tools_policy`, `max_description_budget`, `max_loaded_skills`, `always_allowed_tools`，均有默认值） | ✅ |
| `SkillMetadata` TypedDict | 7 个字段 | 7 个字段（不变） | ✅ |
| `SkillsState.skills_metadata` | `NotRequired` | `NotRequired`（不变） | ✅ |
| `create_deep_agent(skills=...)` | 传入 source 路径列表 | 传入 source 路径列表（不变） | ✅ |
| `__all__` 导出 | `["SkillMetadata", "SkillsMiddleware"]` | `["SkillMetadata", "SkillsMiddleware", "AllowedToolsPolicy", "ResourceMetadata"]` | ✅ |

### 5.2 行为兼容性

**现有 SKILL.md 文件**。所有现存的 `SKILL.md` 文件无需任何修改。V2 新增的资源发现是增量功能——如果技能目录下没有 `scripts/`, `references/`, `assets/` 子目录，`skill_resources` 中对应的列表为空，不影响任何现有行为。

**Agent 行为**。V2 的系统提示引导 Agent 使用 `load_skill` 工具，但 Agent 仍然可以通过 `read_file` 直接读取 `SKILL.md`。区别在于：通过 `read_file` 读取不会触发状态更新（`skills_loaded` 不会被更新），因此不会获得资源摘要和加载状态标记。这是一种优雅降级，不会导致错误。

> **幂等性边界说明**：如果 Agent 先通过 `read_file` 读取了 `SKILL.md`，再调用 `load_skill`，由于 `skills_loaded` 为空（`read_file` 不更新状态），`load_skill` 会成功执行并返回 `Command`。这是**预期行为**——`load_skill` 的幂等性基于自身状态（`skills_loaded`），不感知外部 `read_file` 操作。Agent 会收到重复的内容，但状态会被正确更新。

**`allowed_tools_policy` 默认值**。默认为 `RECOMMEND`，与 V1 行为完全一致（仅显示，不限制）。只有显式设置为 `RESTRICT` 才会启用运行时限制。

**预算参数默认值**。`max_description_budget=16_000` 和 `max_loaded_skills=10` 的默认值足够宽松，不会影响现有小规模技能库的行为。只有当技能数量超过约 42 个（按平均 263 chars/描述估算）时，描述层预算才会开始生效。

### 5.3 SubAgent 隔离

当前架构中，主 Agent 和 SubAgent 各自拥有独立的 `SkillsMiddleware` 实例（在 `graph.py` 中分别创建）。由于 `skills_loaded` 和 `skill_resources` 都使用 `PrivateStateAttr`，它们不会传播到父级或子级 Agent。这意味着：

- 主 Agent 加载的技能不会自动在 SubAgent 中生效。
- SubAgent 的 `skills_loaded` 状态独立于主 Agent。
- 通用子代理（general-purpose subagent）自动继承主 Agent 的 skills sources 配置（由 `graph.py` 保证），但其加载状态是独立的。

---

## 6. 错误处理与降级策略

### 6.1 资源发现降级

如果 `backend.ls_info()` 在扫描资源目录时抛出异常（例如某些简化的 backend 实现不支持目录列表），`_discover_resources` 会捕获异常并记录警告，返回空列表。这确保了资源发现失败不会阻止技能系统的正常运行。

### 6.2 `load_skill` 工具错误处理

`load_skill` 工具的所有错误都通过返回描述性错误字符串来处理（而不是抛出异常或返回 `Command`），这确保了 Agent 可以理解错误并采取替代行动：

| 错误场景 | 返回类型 | 返回消息 | Agent 可采取的行动 |
| :--- | :---: | :--- | :--- |
| 技能名称不存在 | `str` | `"Error: Skill 'xxx' not found. Available skills: ..."` | 检查可用技能列表，修正名称 |
| 技能已加载 | `str` | `"Skill 'xxx' is already loaded."` | 直接使用已加载的技能指令 |
| 加载数量达到上限 | `str` | `"Error: Cannot load skill 'xxx'. Maximum number of simultaneously loaded skills reached (N). Currently loaded: ..."` | 评估已加载技能的必要性 |
| 文件读取失败 | `str` | `"Error: Failed to read skill file at ..."` | 使用 `read_file` 作为后备 |
| 文件超过大小限制 | `str` | `"Error: Skill file at ... exceeds maximum size"` | 报告问题给用户 |
| 编码错误 | `str` | `"Error: Failed to decode skill file: ..."` | 报告问题给用户 |
| 成功加载 | `Command` | 技能内容 + 资源摘要（通过 `ToolMessage`） | 按照技能指令执行 |

**关键设计**：只有成功加载时才返回 `Command`（更新 `skills_loaded` 和 `skill_resources` 状态），所有错误情况都返回普通字符串（不更新状态）。这确保了只有真正成功加载的技能才会被标记为"已加载"。

### 6.3 `wrap_tool_call` 降级

`wrap_tool_call` 的 `_check_allowed_tools` 方法在以下情况下自动放行：

1. 策略为 `RECOMMEND` 模式（默认）。
2. 没有任何技能被加载（`skills_loaded` 为空）。
3. 已加载的技能都没有定义 `allowed-tools` 字段。

这种多层降级确保了 `allowed-tools` 限制只在明确需要时才生效。

### 6.4 描述层预算降级

当技能描述总量超过 `max_description_budget` 时，`_format_skills_list` 会：

1. 优先保留已加载技能的描述（不受预算限制）。
2. 按发现顺序填充未加载技能，直到达到预算上限。
3. 在列表末尾添加提示，告知 Agent 被排除的技能数量和浏览方式。

这种降级策略确保了 Agent 始终能看到最重要的信息（已加载技能），同时不会因为技能过多而导致 prompt 超长。

---

## 7. 测试策略

### 7.1 单元测试

以下测试用例覆盖 V2 的所有新功能（共 31 个）：

| 测试类别 | 测试用例 | 验证目标 |
| :--- | :--- | :--- |
| 资源发现 | `test_discover_resources_standard_dirs` | 正确发现 `scripts/`, `references/`, `assets/` 下的文件 |
| 资源发现 | `test_discover_resources_empty_skill` | 无资源目录时返回空列表 |
| 资源发现 | `test_discover_resources_backend_error` | backend 异常时优雅降级，返回空列表 |
| 资源发现 | `test_discover_resources_non_standard_dirs_ignored` | 非标准目录（如 `temp/`）被忽略 |
| 资源发现 | `test_discover_resources_root_level_files` | 根级别非 SKILL.md 文件被标记为 `"other"` 类型 |
| 状态初始化 | `test_before_agent_initializes_new_state` | `skills_loaded` 初始化为 `[]`，`skill_resources` 初始化为 `{}` |
| 状态初始化 | `test_before_agent_idempotent` | 重复调用返回 `None`，不覆盖已有状态 |
| load_skill | `test_load_skill_returns_command_with_content` | 成功加载返回 `Command`，包含技能内容和资源摘要 |
| load_skill | `test_load_skill_updates_skills_loaded` | `Command.update` 中 `skills_loaded` 包含新技能名称 |
| load_skill | `test_load_skill_updates_skill_resources` | `Command.update` 中 `skill_resources` 包含延迟发现的资源 |
| load_skill | `test_load_skill_not_found_returns_error` | 技能不存在时返回错误字符串（非 `Command`） |
| load_skill | `test_load_skill_already_loaded_returns_message` | 已加载技能返回提示字符串（非 `Command`） |
| load_skill | `test_load_skill_file_read_error` | 文件读取失败时返回错误字符串 |
| load_skill | `test_load_skill_file_size_exceeded` | 超过 `MAX_SKILL_FILE_SIZE` 时返回错误字符串 |
| load_skill | `test_load_skill_max_loaded_reached` | 达到 `max_loaded_skills` 上限时返回错误字符串 |
| 权限控制 | `test_allowed_tools_recommend_mode_passthrough` | `RECOMMEND` 模式不拦截任何工具调用 |
| 权限控制 | `test_allowed_tools_restrict_mode_allows_listed` | `RESTRICT` 模式允许列表内工具 |
| 权限控制 | `test_allowed_tools_restrict_mode_blocks_unlisted` | `RESTRICT` 模式阻止列表外工具，返回 `ToolMessage(status="error")` |
| 权限控制 | `test_allowed_tools_whitelist_always_allowed` | 白名单工具（`load_skill`, `read_file` 等）始终不被阻止 |
| 权限控制 | `test_allowed_tools_custom_whitelist` | 自定义白名单正确覆盖默认白名单 |
| 权限控制 | `test_allowed_tools_no_loaded_skills_passthrough` | 无已加载技能时不限制 |
| 权限控制 | `test_allowed_tools_no_restrictions_defined_passthrough` | 已加载技能无 `allowed-tools` 定义时不限制 |
| 权限控制 | `test_allowed_tools_multi_skill_union` | 多个已加载技能的 `allowed-tools` 取并集 |
| 系统提示 | `test_format_skills_list_with_loaded_status` | 已加载技能显示 `[Loaded]` 标记 |
| 系统提示 | `test_format_skills_list_with_resources` | 资源摘要正确显示（如 "2 scripts, 1 reference"） |
| 系统提示 | `test_format_skills_list_load_skill_guidance` | 未加载技能显示 `load_skill("name")` 引导 |
| 系统提示 | `test_format_skills_list_description_budget_exceeded` | 超出描述预算时正确截断并显示提示 |
| 系统提示 | `test_format_skills_list_loaded_skills_exempt_from_budget` | 已加载技能不受描述预算限制 |
| 向后兼容 | `test_v1_skills_work_without_modification` | 无 V2 字段的 SKILL.md 正常工作 |
| 向后兼容 | `test_default_policy_is_recommend` | 默认策略为 `RECOMMEND` |
| 向后兼容 | `test_read_file_still_works_for_skills` | 通过 `read_file` 读取技能不会导致错误 |

### 7.2 集成测试

集成测试验证 `SkillsMiddleware` 与其他中间件的协作以及端到端场景：

1. **与 `FilesystemMiddleware` 的协作**：验证 `load_skill` 工具和 `read_file` 工具可以共存，且 Agent 可以先用 `load_skill` 加载技能，再用 `read_file` 读取资源。
2. **与 `SubAgentMiddleware` 的协作**：验证主 Agent 和 SubAgent 的 `skills_loaded` 状态相互隔离，SubAgent 在主 Agent 加载技能后可以独立加载。
3. **与 `SummarizationMiddleware` 的协作**：验证技能系统提示在上下文压缩后仍然正确。
4. **`load_skill` 后系统提示更新**：验证 `load_skill` 成功后，下一次 `wrap_model_call` 的系统提示中正确显示 `[Loaded]` 标记和资源摘要。
5. **RESTRICT 模式跨技能权限累积**：验证多个技能依次加载后，`allowed-tools` 正确取并集，且权限随加载动态扩展。
6. **描述预算与加载预算交互**：验证在描述预算排除了部分技能后，Agent 仍可通过 `load_skill` 加载被排除的技能（只要知道名称）。

---

## 8. 扩展路线图

本节描述 V2 之后的扩展方向，这些功能在当前版本中仅预留扩展点，不实现。

### 8.1 Phase 3: 高级 Frontmatter 字段支持

| 字段 | 描述 | 实现思路 | 复杂度 |
| :--- | :--- | :--- | :---: |
| `disable-model-invocation` | 禁止模型自动加载技能 | 在 `_format_skills_list` 中为标记了此字段的技能添加 `(Manual only)` 标记，并在系统提示中说明"不要自动加载此技能" | 低 |
| `argument-hint` | 参数提示 | 在系统提示中显示提示文本，如 `load_skill("deploy", args="[env-name]")` | 低 |
| `model` | 模型覆盖 | 需要与 `wrap_model_call` 集成，在加载了指定 `model` 的技能后通过 `request.override` 切换模型。可能需要框架层面支持 | 高 |
| `context: fork` | 子代理执行 | 需要与 `SubAgentMiddleware` 深度集成，在 `load_skill` 时创建子代理上下文。可通过 `agent jumps` 机制（返回 `{"jump_to": "tools"}` 等）实现流程控制 | 高 |

### 8.2 Phase 4: 事件钩子系统

Claude Code 的 hooks 系统支持 14 种事件类型（`PreToolUse`, `PostToolUse`, `SessionStart` 等），处理器类型包括 `command`（Shell 命令）、`prompt`（LLM 提示）和 `agent`（代理钩子）。

在 DeepAgents 中实现类似系统的可行路径是：

1. **在 `SkillMetadata` 中新增 `hooks` 字段**，解析 SKILL.md frontmatter 中的 hooks 定义（YAML 格式）。
2. **将 hooks 事件映射到 `AgentMiddleware` 的 hook 点**：`PreToolUse` 映射到 `wrap_tool_call`（前置检查），`PostToolUse` 映射到 `wrap_tool_call`（后置处理），`SessionStart` 映射到 `before_agent`。
3. **实现 `command` 类型处理器**：通过 `backend.execute()`（如果 backend 实现了 `SandboxBackendProtocol`）执行 Shell 命令。
4. **实现 `prompt` 类型处理器**：将提示注入到下一次模型调用的上下文中。
5. **支持 `matcher` 模式匹配**：在 `wrap_tool_call` 中根据 matcher 正则表达式匹配工具名称。
6. **支持 `once` 字段**：技能级别的 hooks 支持 `once: true`，运行一次后自动移除。

这一扩展的主要挑战在于安全性——需要确保 hooks 中的 Shell 命令在沙箱环境中执行，且不会绕过权限控制。

### 8.3 Phase 5: SubAgent 技能继承策略

当前 V2 的 SubAgent 技能隔离是合理的默认行为，但某些场景下可能需要技能继承（例如主 Agent 加载了 `web-research` 技能后委托 SubAgent 进行研究任务）。

可行的实现路径是在 `SkillsMiddleware.__init__` 中新增 `subagent_inherit` 参数（`"isolated"` | `"inherit"`），并在 `graph.py` 中创建 SubAgent 的 `SkillsMiddleware` 实例时传递父级的 `skills_loaded` 状态。这需要修改 `graph.py`，因此不纳入 V2 范围。

### 8.4 Phase 6: CLI 集成

CLI 的 `deepagents skills list/create/info` 命令需要与 V2 的新功能兼容：

1. `deepagents skills list` 应显示资源计数。
2. `deepagents skills info <name>` 应显示资源详情。
3. `deepagents skills create` 应生成包含标准资源目录的脚手架。

这些变更限于 `libs/cli/deepagents_cli/skills/` 目录，不影响核心中间件。

---

## 9. 实施计划

### 9.1 分阶段交付

| 阶段 | 时间估算 | 核心任务 | 交付物 | 验收标准 |
| :--- | :---: | :--- | :--- | :--- |
| **Phase 1** | 2-3 天 | 扩展 `SkillsState` 和 `SkillsStateUpdate`（新增 `skills_loaded`, `skill_resources`）；实现 `_discover_resources` / `_adiscover_resources`（延迟模式）；增强 `before_agent` / `abefore_agent`（初始化新状态字段）；创建 `load_skill` 工具（sync + async，含内容层预算检查） | 支持延迟资源发现、状态追踪和加载限制的中间件 | 所有 V1 测试通过 + 15 个新增单元测试通过（资源发现 5 + 状态初始化 2 + load_skill 8） |
| **Phase 2** | 2-3 天 | 实现 `AllowedToolsPolicy` 枚举；实现 `wrap_tool_call` / `awrap_tool_call`（`allowed-tools` 策略，含可扩展白名单）；优化 `_format_skills_list`（含描述层预算控制和已加载优先排序）；更新 `SKILLS_SYSTEM_PROMPT` 模板 | 完整的 V2 中间件 | 所有 31 个单元测试通过 + 6 个集成测试通过 |
| **Phase 3** | 1 天 | 文档更新、代码审查、性能测试（50+ 技能场景） | 可合并的 PR | 代码审查通过、无性能回归 |

### 9.2 文件变更清单

| 文件 | 变更类型 | 变更内容 |
| :--- | :---: | :--- |
| `deepagents/middleware/skills.py` | 修改 | 新增 `ResourceMetadata`、`AllowedToolsPolicy`；扩展 `SkillsState` / `SkillsStateUpdate`（新增 `skills_loaded`, `skill_resources`）；新增 `_discover_resources` / `_adiscover_resources`；增强 `before_agent` / `abefore_agent`；新增 `_create_load_skill_tool` / `_get_backend_from_runtime` / `_execute_load_skill` / `_aexecute_load_skill`；新增 `wrap_tool_call` / `awrap_tool_call` / `_check_allowed_tools`；增强 `_format_skills_list` / `_format_resource_summary` / `modify_request`；更新 `SKILLS_SYSTEM_PROMPT`；扩展 `__init__`（新增可选参数）；更新 `__all__` |
| `tests/unit_tests/middleware/test_skills_middleware.py` | 修改 | 新增 31 个测试用例（资源发现 5 + 状态初始化 2 + load_skill 8 + 权限控制 8 + 系统提示 5 + 向后兼容 3） |
| `tests/integration_tests/test_skills_integration.py` | 新增 | 6 个集成测试 |

**不变更的文件**：`graph.py`、`middleware/__init__.py`、`middleware/_utils.py`、`middleware/filesystem.py`、`middleware/memory.py`、`middleware/subagents.py`、`middleware/summarization.py`、`middleware/patch_tool_calls.py`、`backends/protocol.py`。

---

## 10. 已知限制与约束

本节汇总了 V2 设计方案中所有已知的限制和设计约束，以确保研发团队在实施时有清晰的预期。

### 10.1 状态更新语义与并发安全性

**状态更新语义**。`skills_loaded` 和 `skill_resources` 字段没有定义自定义 reducer。在没有 reducer 的情况下，LangGraph 的默认行为是**覆盖**（last-write-wins）。`_execute_load_skill` 使用“读取全量 → append → 写回全量”的模式，这在覆盖语义下是正确的。

**与 FilesystemMiddleware 的对比**。`FilesystemMiddleware` 的 `files` 字段使用了自定义 reducer `_file_data_reducer`，因为 `write_file` 只发送 delta（单个文件的更新），需要 reducer 来合并。而 `load_skill` 发送的是全量 `skills_loaded` 列表，不需要 reducer 来合并。这是两种不同的状态更新模式：

| 模式 | 使用场景 | 是否需要 reducer |
| :--- | :--- | :---: |
| Delta 更新 | `write_file` 发送单个文件的更新 | 是（`_file_data_reducer` 合并 delta） |
| 全量更新 | `load_skill` 发送完整的 `skills_loaded` 列表 | 否（覆盖语义即可） |

**并发安全性**。当前 DeepAgents 框架不支持并行工具调用（parallel tool calls），所有工具调用是顺序执行的。因此，`load_skill` 不会并发执行，“读取全量 → append → 写回全量”的模式是安全的，不会出现竞态条件。

**未来扩展**。如果未来 DeepAgents 支持并行工具调用，需要为 `skills_loaded` 和 `skill_resources` 定义自定义 reducer（例如，`skills_loaded` 的 reducer 可以是 `operator.add` + 去重），以确保并发安全。这可以作为 Phase 4 的一部分。

### 10.2 `sources` 运行时不可变

`SkillsMiddleware` 的 `sources` 参数在 `__init__` 时固定，运行时不可变。这意味着如果用户在 Agent 运行期间通过 `write_file` 创建了新的技能目录（例如 `/home/ubuntu/new_skills/`），中间件不会自动发现这个新目录。Agent 需要重新启动才能识别新的 `sources`。这与 V1 的行为一致，不是 V2 引入的新限制。

### 10.3 `allowed-tools` 边界行为

`_check_allowed_tools` 的核心逻辑是：**只要有一个已加载的技能没有定义 `allowed-tools` 字段，就不进行任何工具限制**。这是有意的设计选择，原因如下：

考虑场景：Agent 加载了技能 A（定义了 `allowed-tools: [tool_x, tool_y]`）和技能 B（未定义 `allowed-tools`）。如果仅基于技能 A 的限制来阻止其他工具，技能 B 可能需要的工具会被错误地阻止。因此，安全的默认行为是“存在未定义限制的技能时，不限制”。只有当**所有**已加载的技能都定义了 `allowed-tools` 时，才会取其并集进行限制。

以下是各种边界场景的行为汇总：

| 场景 | 行为 | 原因 |
| :--- | :--- | :--- |
| 无已加载技能 | 不限制 | 无技能上下文 |
| 所有已加载技能都未定义 `allowed-tools` | 不限制 | 无限制定义 |
| 所有已加载技能都定义了 `allowed-tools` | 取并集限制 | 所有技能明确声明了工具范围 |
| 部分定义、部分未定义 | **不限制** | 未定义的技能可能需要任意工具 |
| 白名单工具（`load_skill`, `read_file` 等） | 始终允许 | 基础设施工具不受限制 |

### 10.4 技能卸载

V2 不实现技能卸载机制（`unload_skill` 工具）。当 Agent 达到 `max_loaded_skills` 上限时，错误消息会引导 Agent 重新评估已加载技能的必要性。如果未来需要卸载能力，可以在 `load_skill` 工具旁新增 `unload_skill` 工具，从 `skills_loaded` 中移除指定技能。这不需要修改任何现有接口。

### 10.5 SubAgent 技能继承

V2 不支持 SubAgent 技能继承。主 Agent 和 SubAgent 的技能加载状态是完全隔离的。这一设计在 8.3 节中有详细说明。

### 10.6 性能与日志

**性能影响分析**。V2 的性能开销主要集中在以下两个新增的 hook 中：

| Hook | 额外开销 | 调用频率 | 影响评估 |
| :--- | :--- | :--- | :--- |
| `load_skill` | 1-3 次 `backend.ls_info` 调用（延迟资源发现） | 低（每个技能仅一次） | 可忽略 |
| `wrap_tool_call` | O(N) 遍历已加载技能的 allowed-tools | 高（每次工具调用） | 微秒级（N<10） |
| `_format_skills_list` | 排序 + 预算检查 | 中（每次模型调用） | 可忽略 |

在典型场景下（<100 个技能，<10 个已加载技能），这些开销是毫秒级的，不会对整体性能产生显著影响。`before_agent` 的性能与 V1 完全相同（不再扫描资源）。

**日志策略**。方案中的 `logger.warning` 仅为示例。建议在实施时采用结构化日志，记录所有关键事件：

| 事件 | 日志级别 | 示例 |
| :--- | :---: | :--- |
| 技能发现 | `INFO` | `Discovered 15 skills from 2 sources` |
| 技能加载成功 | `INFO` | `Skill 'web-research' loaded (3 resources discovered)` |
| 加载限制触发 | `WARNING` | `Skill loading limit reached (10/10)` |
| 描述预算超限 | `WARNING` | `Description budget exceeded, 5 skills excluded` |
| 工具调用被阻止 | `WARNING` | `Tool 'execute' blocked by allowed-tools policy` |
| 资源发现失败 | `WARNING` | `Failed to list resources for skill 'deploy'` |
| 技能文件读取失败 | `ERROR` | `Failed to read SKILL.md at skills/deploy/SKILL.md` |

---

## 附录 A：完整的新增/修改方法清单

| 方法 | 类型 | 描述 |
| :--- | :---: | :--- |
| `_discover_resources()` | 新增（模块级） | 同步延迟资源发现 |
| `_adiscover_resources()` | 新增（模块级） | 异步延迟资源发现 |
| `_format_resource_summary()` | 新增（模块级） | 资源摘要格式化 |
| `SkillsMiddleware.__init__()` | 修改 | 新增 `allowed_tools_policy`, `max_description_budget`, `max_loaded_skills`, `always_allowed_tools` 参数、`self.tools` 属性 |
| `SkillsMiddleware._create_load_skill_tool()` | 新增 | 创建 load_skill 工具 |
| `SkillsMiddleware._get_backend_from_runtime()` | 新增 | 从 ToolRuntime 解析 backend |
| `SkillsMiddleware._execute_load_skill()` | 新增 | load_skill 同步核心逻辑（含内容层预算检查 + 延迟资源发现） |
| `SkillsMiddleware._aexecute_load_skill()` | 新增 | load_skill 异步核心逻辑（含内容层预算检查 + 延迟资源发现） |
| `SkillsMiddleware._format_skills_list()` | 修改 | 新增 `loaded` 和 `resources` 参数、描述层预算控制、已加载优先排序 |
| `SkillsMiddleware.modify_request()` | 修改 | 传入新状态字段 |
| `SkillsMiddleware.before_agent()` | 修改 | 新增 `skills_loaded` 和 `skill_resources` 状态初始化 |
| `SkillsMiddleware.abefore_agent()` | 修改 | 新增 `skills_loaded` 和 `skill_resources` 状态初始化（异步） |
| `SkillsMiddleware.wrap_tool_call()` | 新增 | allowed-tools 策略检查 |
| `SkillsMiddleware.awrap_tool_call()` | 新增 | allowed-tools 策略检查（异步） |
| `SkillsMiddleware._check_allowed_tools()` | 新增 | allowed-tools 权限检查逻辑（含可扩展白名单） |

---

## 附录 B：新增类型定义汇总

```python
class ResourceMetadata(TypedDict):
    """技能资源元数据。"""
    path: str                                           # 资源文件路径
    type: Literal["script", "reference", "asset", "other"]  # 资源类型
    skill_name: str                                     # 所属技能名称


class AllowedToolsPolicy(str, Enum):
    """allowed-tools 字段的执行策略。"""
    RECOMMEND = "recommend"   # 默认：仅推荐
    RESTRICT = "restrict"     # 严格：运行时阻止


class SkillsState(TypedDict, total=False):
    """V2 技能状态（扩展 V1）。"""
    skills_metadata: list[SkillMetadata]                # V1: 技能元数据列表
    skills_loaded: Annotated[list[str], PrivateStateAttr]   # V2: 已加载技能名称
    skill_resources: Annotated[                         # V2: 技能资源（延迟填充）
        dict[str, list[ResourceMetadata]], PrivateStateAttr
    ]


class SkillsStateUpdate(TypedDict, total=False):
    """V2 技能状态更新（扩展 V1）。"""
    skills_metadata: list[SkillMetadata]
    skills_loaded: list[str]                            # V2
    skill_resources: dict[str, list[ResourceMetadata]]  # V2
```

---

## 附录 C：模块级常量汇总

```python
# V1 保留
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# V2 新增
RESOURCE_TYPE_MAP: dict[str, Literal["script", "reference", "asset"]] = {
    "scripts": "script",
    "references": "reference",
    "assets": "asset",
}

_DEFAULT_ALWAYS_ALLOWED_TOOLS = frozenset({
    "load_skill",       # 技能加载工具本身
    "write_todos",      # 任务管理
    "read_file",        # 文件读取（资源访问需要）
    "ls",               # 目录列表（资源发现需要）
})
```

---

## 参考文献

[1]: Agent Skills. "Agent Skills Specification." agentskills.io. Accessed Feb 16, 2026. https://agentskills.io/specification

[2]: Anthropic. "Skills - Claude Code." code.claude.com. Accessed Feb 17, 2026. https://code.claude.com/docs/en/skills

[3]: Coze. "使用技能." coze.cn. Accessed Feb 17, 2026. https://www.coze.cn/open/docs/guides/using_skill

[4]: OpenAI. "Assistants API." platform.openai.com. Accessed Feb 17, 2026. https://platform.openai.com/docs/assistants/overview

[5]: Anthropic. "Skills - Claude Code: Context Budget." code.claude.com. Accessed Feb 17, 2026. https://code.claude.com/docs/en/skills#context-budget

[6]: Anthropic. "Effective Context Engineering for AI Agents." anthropic.com. Accessed Feb 17, 2026. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
