# DeepAgents Skills Middleware V2 升级设计方案

**版本**: 2.0（最终修订版）
**日期**: 2026-02-18
**状态**: 生产就绪
**变更说明**: 本版本在 V1.0 设计稿基础上，融合了**优化建议验证版**（废除 `RESTRICT` 模式、废除描述层预算、新增 `unload_skill` 工具）和**研发团队的三条补充建议**（Reducer 并发说明、SubAgent 场景指南、描述预算排除技能可加载性说明），形成最终可实施方案。

---

## 目录

1. [概述](#1-概述)
2. [架构设计](#2-架构设计)
3. [实现方案](#3-实现方案)
4. [上下文预算管理](#4-上下文预算管理)
5. [`allowed-tools` 推荐策略](#5-allowed-tools-推荐策略)
6. [向后兼容性保证](#6-向后兼容性保证)
7. [错误处理与降级策略](#7-错误处理与降级策略)
8. [测试策略](#8-测试策略)
9. [扩展路线图](#9-扩展路线图)
10. [实施计划](#10-实施计划)
11. [已知限制与约束](#11-已知限制与约束)

---

## 1. 概述

### 1.1 文档目的

本文档为 `deepagents.middleware.skills.SkillsMiddleware` 的 V2 版本升级提供完整的设计与实现方案。方案基于对 [Agent Skills 开放规范][1]、[Claude Code 原生 Skill 系统][2]、[Coze 技能系统][3]、以及 DeepAgents 现有框架架构的深入分析，旨在将现有中间件从基础的技能发现与提示注入器，升级为一个功能聚焦、安全可控、高度可扩展的技能运行时系统。

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

**缺乏状态追踪**。系统无法追踪哪些技能已被 Agent 实际"加载"（即读取了完整的 `SKILL.md` 内容）。当前的渐进式披露是单向的——Agent 在系统提示中看到技能列表后，通过通用的 `read_file` 工具读取 `SKILL.md`，但中间件对此过程完全无感知。这意味着无法基于"已加载技能"实施任何策略（如上下文优化、状态标记）。

**无资源发现机制**。Agent Skills 规范定义了 `scripts/`, `references/`, `assets/` 三个标准资源目录，但 V1 仅发现 `SKILL.md` 文件本身，不会扫描或报告这些资源目录的内容。Agent 必须依赖 `SKILL.md` 中的文本引用来猜测资源路径。

**缺少专用加载/卸载工具**。Agent 必须使用通用的 `read_file` 工具来加载技能内容，这不仅增加了操作复杂性，也使得中间件无法区分"读取技能"和"读取普通文件"的行为。同时，Agent 无法主动释放已加载的技能以管理上下文空间。

**无上下文预算管理**。Agent 可以无限制地加载技能内容，导致上下文窗口被技能指令占满，模型回忆准确性下降（Context Rot）[6]。

### 1.3 设计原则

本次升级严格遵循以下四项核心设计原则，它们按优先级排列：

| 优先级 | 原则 | 约束 |
| :---: | :--- | :--- |
| P0 | **向后兼容性** | 所有现存的 `SKILL.md` 文件无需任何修改即可继续工作。V1 的公开 API（`SkillsMiddleware.__init__` 签名、`SkillMetadata` TypedDict、`SkillsState` schema）保持不变。新功能作为增量引入。 |
| P0 | **最小侵入性** | 所有变更严格限制在 `skills.py` 文件内部。不修改 `create_deep_agent` 函数签名、`AgentMiddleware` 基类、`BackendProtocol` 接口、或任何其他中间件。新工具通过 `self.tools` 属性提供（与 `FilesystemMiddleware` 模式一致），由框架自动收集。 |
| P1 | **遵循既有模式** | 复用 DeepAgents 框架中已建立的设计模式：通过 `BackendProtocol` 进行文件操作、通过 `PrivateStateAttr` 隔离中间件状态、通过 `self.tools` 提供中间件工具、通过 `Command` 进行工具内状态更新、通过 `ToolRuntime` 在工具函数中访问 state 和 backend。 |
| P2 | **模块化与可扩展性** | 为未来的高级功能（事件钩子 `hooks`、子代理执行 `context: fork`、模型覆盖 `model`）预留清晰的扩展点，但不在本次升级中实现。 |

### 1.4 升级范围

本次升级的范围经过优化和聚焦，最终确定如下：

| 范围 | 内容 |
| :--- | :--- |
| **纳入范围** | 技能加载状态追踪、延迟资源发现、专用 `load_skill` 工具、**专用 `unload_skill` 工具**、`allowed-tools` 系统提示推荐（仅提示，不拦截）、系统提示优化、**上下文预算管理（仅内容层）** |
| **排除范围** | `allowed-tools` 运行时拦截（`RESTRICT` 模式）、描述层预算截断、`hooks` 事件系统实现、`context: fork` 子代理执行、`model` 字段覆盖、`argument-hint` / `$ARGUMENTS` 替换、`disable-model-invocation` / `user-invocable` 控制、CLI 命令扩展、SubAgent 技能继承 |

> **关于排除范围的设计决策说明**：
>
> **废除 `RESTRICT` 模式**。经过验证，`RESTRICT` 模式（通过 `wrap_tool_call` 拦截工具调用）与 DeepAgents 的 Agent 自主性哲学相悖，且与 `HITL` 中间件在功能上存在重叠。现代大型语言模型完全有能力理解系统提示中的"软性"工具推荐并做出合理判断。废除此模式可移除约 150 行代码和 8 个测试用例，显著降低复杂度。
>
> **废除描述层预算**。按发现顺序截断技能描述是一种武断的策略，可能隐藏重要技能。将技能组织的责任交给开发者（通过 `sources` 参数控制不同 Agent 可见的技能范围），是更合理、更可控的策略。这使系统行为更简单、更可预测——所有在 `sources` 中发现的技能都会在系统提示中展示，不存在被截断的情况。
>
> **新增 `unload_skill` 工具**。在保留 `max_loaded_skills` 上限的前提下，`unload_skill` 是解决"加载上限僵局"的关键。它使 Agent 能够像人类一样动态管理"工作记忆"，形成完整的技能生命周期（加载 → 使用 → 卸载）。

排除范围中的功能将在后续版本中按优先级逐步引入，本文档第 9 节提供了详细的扩展路线图。

---

## 2. 架构设计

### 2.1 Hook 使用规划

V2 仅使用 V1 已有的两个 hook（`before_agent` 和 `wrap_model_call`），不新增 hook。废除 `RESTRICT` 模式后，`wrap_tool_call` 不再需要。这一决策最大程度地简化了实现，降低了维护成本。

| Hook | V1 使用 | V2 使用 | 职责 |
| :--- | :---: | :---: | :--- |
| `before_agent` / `abefore_agent` | ✅ | ✅ | 技能发现、元数据解析、**状态初始化（新增 `skills_loaded`, `skill_resources`）** |
| `wrap_model_call` / `awrap_model_call` | ✅ | ✅ | 系统提示注入（**含加载状态标记、`load_skill`/`unload_skill` 引导语**） |
| `wrap_tool_call` / `awrap_tool_call` | ❌ | ❌ | 不使用（`allowed-tools` 仅通过系统提示推荐） |
| `before_model` | ❌ | ❌ | 预留：未来可用于技能上下文预检 |
| `after_model` | ❌ | ❌ | 预留：未来可用于技能使用统计 |
| `after_agent` | ❌ | ❌ | 预留：未来可用于状态清理 |

> **重要说明**：所有 hook 方法都需要同时提供同步和异步版本（如 `before_agent` 和 `abefore_agent`），这与 V1 的模式一致。

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

V2 将引入两个新的专用工具 `load_skill` 和 `unload_skill`，通过 `self.tools` 属性提供给框架。这与 `FilesystemMiddleware` 在 `__init__` 中创建 `self.tools = [self._create_ls_tool(), self._create_read_file_tool(), ...]` 的模式完全一致。

#### 2.3.1 `load_skill` 工具

```
load_skill(skill_name: str) -> str | Command
```

**工具行为**：

1. 从 `runtime.state["skills_metadata"]` 中查找匹配的技能，获取其 `path`。
2. **幂等性检查**：如果 `skill_name` 已在 `skills_loaded` 中，返回提示消息。
3. **内容层预算检查**：如果 `skills_loaded` 长度已达到 `max_loaded_skills`，返回错误消息，**引导 Agent 使用 `unload_skill` 释放空间**。
4. 通过 `backend.download_files([path])` 读取 `SKILL.md` 的完整内容。
5. **延迟资源发现**：如果 `skill_resources` 中没有该技能的缓存，按需扫描资源目录并缓存结果。
6. 构建返回内容：`SKILL.md` 内容 + 资源摘要（如果有资源）。
7. **状态更新**：通过返回 `Command` 将 `skill_name` 添加到 `skills_loaded` 列表中，同时更新 `skill_resources` 缓存，并携带 `ToolMessage` 作为工具响应。

#### 2.3.2 `unload_skill` 工具

```
unload_skill(skill_name: str) -> str | Command
```

**工具行为**：

1. **验证检查**：如果 `skill_name` 不在 `skills_loaded` 中，返回错误消息。
2. 从 `skills_loaded` 列表中移除 `skill_name`。
3. **可选清理**：从 `skill_resources` 缓存中移除该技能的资源条目（释放内存）。
4. **状态更新**：通过返回 `Command` 更新 `skills_loaded` 和 `skill_resources` 状态，并携带 `ToolMessage` 确认卸载成功。

**`unload_skill` 的语义说明**。卸载技能仅从状态中移除加载标记和资源缓存，**不会**从对话历史中删除之前 `load_skill` 返回的技能内容（对话历史由框架管理，中间件无法也不应修改）。卸载的效果是：(1) 系统提示中该技能不再显示 `[Loaded]` 标记；(2) 内容层预算释放一个名额，允许加载新技能；(3) 如果再次需要该技能，Agent 需要重新调用 `load_skill`。

#### 2.3.3 工具提供机制

**关键设计决策：状态更新在工具函数内部完成**。与 `FilesystemMiddleware` 的 `write_file` 工具模式一致，`load_skill` 和 `unload_skill` 工具函数在需要更新状态时直接返回 `Command` 对象。`Command` 的 `update` 字段包含要合并到 agent state 中的字段（如 `skills_loaded`），同时通过 `messages` 字段携带 `ToolMessage` 作为工具响应。

**为何不引入 `load_skill_resource` 工具**。现有的 `read_file` 工具（由 `FilesystemMiddleware` 提供）已经完全能够读取资源文件，且 `load_skill` 返回的资源摘要中会包含完整的路径。引入冗余工具会增加 Agent 的认知负担，违反"最小侵入性"原则。

**`load_skill` 的幂等性说明**。`load_skill` 的幂等性是基于自身状态（`skills_loaded`）的，不感知外部 `read_file` 操作。如果 Agent 先通过 `read_file` 读取了 `SKILL.md`，再调用 `load_skill`，由于 `skills_loaded` 中没有该技能名称，工具会正常执行并返回 `Command`。这是预期行为——`read_file` 是通用文件读取操作，不会触发技能系统的状态更新。只有通过 `load_skill` 加载的技能才会被纳入状态追踪。

### 2.4 上下文预算管理（概述）

V2 采用**单层内容预算管理机制**，聚焦于控制同时加载的技能数量（默认 10 个，可配置），不实施描述层预算截断。核心设计决策包括：

- **描述层：开发者责任制**——所有在 `sources` 中发现的技能都完整展示，不截断。
- **内容层：`max_loaded_skills` 限制**——通过 `load_skill` / `unload_skill` 动态管理加载名额。
- **与 `unload_skill` 的协同**——使内容层预算从“硬性限制”变为“弹性限制”。

详细的预算策略、行业对比和可配置性说明见第 4 节。


---

## 3. 实现方案

### 3.1 `__init__` 扩展

`SkillsMiddleware.__init__` 新增一个可选参数 `max_loaded_skills`，保持最小化的 API 变更以保证向后兼容：

```python
class SkillsMiddleware(AgentMiddleware):
    state_schema = SkillsState

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        sources: list[str],
        # V2 新增参数
        max_loaded_skills: int = 10,
    ) -> None:
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

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `max_loaded_skills` | `int` | `10` | 内容层预算，控制同时加载的技能数量上限。Agent 可通过 `unload_skill` 释放空间后加载新技能。 |

> **与 V1.0 设计稿的差异说明**：V1.0 设计稿包含 4 个新增参数（`allowed_tools_policy`、`max_description_budget`、`max_loaded_skills`、`always_allowed_tools`）。经过优化，V2 仅保留 `max_loaded_skills` 一个参数。`allowed_tools_policy` 和 `always_allowed_tools` 因废除 `RESTRICT` 模式而移除；`max_description_budget` 因废除描述层预算而移除。这使 API 变更降到最低，进一步增强了向后兼容性。

### 3.2 延迟资源发现

V2 采用延迟发现策略（Lazy Discovery）：`before_agent` 阶段不再扫描资源目录，资源发现推迟到 `load_skill` 被调用时按需执行。

**延迟发现 vs 即时发现的对比**：

| 维度 | 即时发现（Eager） | 延迟发现（Lazy，V2 采用） |
| :--- | :--- | :--- |
| 扫描时机 | `before_agent` 阶段扫描所有技能的资源目录 | `load_skill` 被调用时按需扫描单个技能 |
| I/O 开销 | O(技能数 × 标准目录数)，如 50 技能 × 3 目录 = 150 次 `ls_info` 调用 | O(1 × 标准目录数)，每次 `load_skill` 最多 3 次 `ls_info` 调用 |
| 首次响应延迟 | 较高（需等待所有资源扫描完成） | 极低（`before_agent` 仅做技能发现） |
| 资源信息可用性 | 所有技能的资源信息立即可用 | 仅已加载技能的资源信息可用 |
| 内存占用 | 较高（缓存所有技能的资源列表） | 较低（仅缓存已加载技能的资源） |

这一决策基于以下考量：

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

    if len(loaded_skills) >= self._max_loaded_skills:
        return (
            f"Error: Cannot load skill '{skill_name}'. "
            f"Maximum number of simultaneously loaded skills reached "
            f"({self._max_loaded_skills}). "
            f"Currently loaded: {', '.join(loaded_skills)}. "
            f"Use `unload_skill(\"skill-name\")` to unload a skill you no "
            f"longer need, then retry loading."
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

### 3.5 `unload_skill` 工具实现

`unload_skill` 与 `load_skill` 对称，提供完整的技能生命周期管理。

```python
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
```

#### 3.5.1 `_execute_unload_skill` 核心逻辑

```python
def _execute_unload_skill(
    self,
    skill_name: str,
    runtime: ToolRuntime[None, SkillsState],
) -> Command | str:
    """unload_skill 核心逻辑。

    注意：unload_skill 不需要 backend 访问（不涉及文件操作），
    因此同步和异步版本可以共用同一个实现。
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

**`unload_skill` 的设计要点**：

1. **无需 backend 访问**。卸载操作仅涉及状态更新（移除列表项和字典键），不需要文件系统操作，因此同步和异步版本可以共用同一个实现函数。
2. **资源缓存清理**。从 `skill_resources` 中移除该技能的条目，释放内存。如果技能被重新加载，资源会被重新发现。
3. **透明的状态反馈**。返回消息明确告知 Agent 当前加载状态和可用名额，帮助 Agent 做出后续决策。
4. **对话历史不受影响**。卸载技能不会从对话历史中删除之前 `load_skill` 返回的内容——对话历史由框架管理，中间件无法也不应修改。Agent 仍然可以参考之前加载的技能内容，但系统提示中该技能不再显示 `[Loaded]` 标记。

### 3.6 系统提示优化（`wrap_model_call` 增强）

`wrap_model_call` 的核心逻辑（调用 `modify_request` 注入系统提示）保持不变，但 `_format_skills_list` 将被增强以反映加载状态。由于废除了描述层预算，此函数的逻辑大幅简化。

#### 3.6.1 增强后的 `_format_skills_list`

```python
def _format_skills_list(
    self,
    skills: list[SkillMetadata],
    loaded: list[str],
    resources: dict[str, list[ResourceMetadata]],
) -> str:
    """格式化技能列表用于系统提示显示。

    V2 增强：显示加载状态标记、资源摘要、load_skill/unload_skill 引导语。
    所有在 sources 中发现的技能都会完整展示，不进行截断。
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
    """格式化资源摘要，按类型分组。"""
    by_type: dict[str, int] = {}
    for r in resources:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    parts = []
    for rtype, count in sorted(by_type.items()):
        parts.append(f"{count} {rtype}{'s' if count > 1 else ''}")
    return ", ".join(parts)
```

#### 3.6.2 修改 `modify_request`

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

#### 3.6.3 更新 `SKILLS_SYSTEM_PROMPT` 模板

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

**变更说明**。相比 V1 模板，V2 模板的主要变化是：(1) 将步骤 2 从"Read the skill's full instructions（使用 path）"改为"Load the skill（使用 `load_skill`）"，引导 Agent 使用专用工具而非通用的 `read_file`；(2) 新增步骤 5，引导 Agent 在技能不再需要时使用 `unload_skill` 释放空间；(3) 移除了"Executing Skill Scripts"和"Example Workflow"部分，因为这些信息会在 `load_skill` 返回的内容中按需提供，符合渐进式披露原则。


---

## 4. 上下文预算管理

上下文预算管理是 V2 新增的核心机制，旨在防止技能系统因加载过多技能而导致对话上下文膨胀，引发模型回忆准确性下降（Context Rot）[6]。

**上下文预算架构概览**：

```
┌─────────────────────────────────────────────────────────┐
│                    模型上下文窗口                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  系统提示（System Prompt）                          │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  技能描述层（Skills List）                     │  │  │
│  │  │  • 所有已发现技能的 name + description        │  │  │
│  │  │  • 无截断（开发者通过 sources 管理数量）        │  │  │
│  │  │  • 已加载技能标记 [Loaded] + 资源摘要          │  │  │
│  │  │  • 未加载技能显示 load_skill() 引导            │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  对话历史（Conversation History）                   │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  技能内容层（Loaded Skill Content）            │  │  │
│  │  │  • load_skill() 返回的 SKILL.md 全文           │  │  │
│  │  │  • 受 max_loaded_skills 限制（默认 10）        │  │  │
│  │  │  • 可通过 unload_skill() 释放名额              │  │  │
│  │  │  • 卸载后内容仍在历史中，但不再标记 [Loaded]    │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  其他对话内容                                  │  │  │
│  │  │  • 用户消息、工具调用结果、Agent 回复等         │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

预算控制点：
  描述层 → 无截断（开发者通过 sources 路径管理）
  内容层 → max_loaded_skills 参数（默认 10）+ unload_skill 动态释放
```

### 4.1 单层内容预算模型

V2 采用**单层内容预算管理机制**，聚焦于控制同时加载的技能数量。这一设计参考了业界成熟系统的实践：

| 系统 | 描述层限制 | 内容层限制 | 策略 |
| :--- | :--- | :--- | :--- |
| **Claude Code** [5] | 2% 上下文窗口（fallback 16,000 chars） | 无明确限制，按需加载 | 超出预算的技能从系统提示中排除 |
| **Coze** [3] | 无明确字符限制 | 50 个编程技能 / 30 个第三方技能 | 硬数量限制 |
| **OpenAI Assistants** [4] | 无明确限制 | 128 个工具 | 硬数量限制 |
| **Manus** | ~100 tokens/技能 | <5K tokens/技能 | 三阶段渐进式 |
| **DeepAgents V2** | **无截断**（开发者通过 `sources` 管理） | **可配置**（默认 10 个） | 内容层预算 + `unload_skill` 动态管理 |

#### 4.1.1 描述层策略：开发者责任制

V2 **不实施描述层预算截断**。所有在 `sources` 中发现的技能都会在系统提示中完整展示。这一决策基于以下考量：

1. **避免武断决策**：按发现顺序截断技能描述可能隐藏重要技能，且截断策略难以做到"智能"。
2. **可预测性**：系统行为更简单——开发者配置了哪些 `sources`，Agent 就能看到哪些技能，没有隐藏的截断逻辑。
3. **鼓励良好实践**：促使开发者从一开始就合理组织技能目录（按项目、按团队、按功能拆分 `sources`），而非依赖框架的自动截断。

**开发者指南**：如果技能数量较多（>50 个），建议通过以下方式管理：

- **按功能拆分 `sources`**：为不同的 Agent 配置不同的 `sources` 路径，确保每个 Agent 只看到与其职责相关的技能。
- **合理控制描述长度**：在 `SKILL.md` 的 frontmatter 中保持 `description` 简洁（建议 <200 字符），避免系统提示过长。
- **分层技能目录**：将通用技能和专用技能分别放在不同的目录中，通过 `sources` 的优先级覆盖机制管理。

#### 4.1.2 内容层预算（同时加载的技能数量）

**问题**。每次 `load_skill` 调用会将完整的 `SKILL.md` 内容注入到对话上下文中。如果 Agent 连续加载多个大型技能，对话上下文会迅速膨胀，导致模型回忆准确性下降（Context Rot）[6]。

**方案**。在 `_execute_load_skill` 中引入 `max_loaded_skills` 参数（默认 10，可配置），检查 `skills_loaded` 列表的长度。如果已加载的技能数量达到上限，阻止加载新技能并返回描述性错误消息，**引导 Agent 使用 `unload_skill` 释放空间**。

**默认值选择依据**。默认值 10 基于以下考量：

- 典型的 SKILL.md 文件在 1-5KB 之间，10 个技能约占 10-50KB 的上下文空间。
- 对于 128K-200K token 的模型上下文窗口，这约占 3-6%，留有充足空间给对话历史和其他中间件。
- Coze 的第三方技能限制为 30 个，OpenAI Assistants 限制为 128 个工具——10 个技能是一个保守但合理的起点。
- 此值可通过 `max_loaded_skills` 参数按需调整。

**与 `unload_skill` 的协同**。`unload_skill` 工具使内容层预算从"不可恢复的硬性限制"变为"可动态管理的弹性限制"。Agent 可以根据任务需要，主动卸载不再需要的技能，为新技能腾出空间。这极大地提升了 Agent 的自主性和灵活性。

### 4.2 预算参数的可配置性

`max_loaded_skills` 通过 `__init__` 的可选参数暴露，开发者可以根据目标模型的上下文窗口大小进行调整：

```python
# 针对 Claude 3.5 Sonnet / GPT-4o (128K-200K context) 的默认配置
middleware = SkillsMiddleware(
    backend=backend,
    sources=["skills/"],
)

# 针对小模型 (32K context) 的紧凑配置
middleware = SkillsMiddleware(
    backend=backend,
    sources=["skills/"],
    max_loaded_skills=3,
)

# 针对大规模技能库的宽松配置
middleware = SkillsMiddleware(
    backend=backend,
    sources=["skills/"],
    max_loaded_skills=20,
)
```

### 4.3 与行业实践的对比

| 维度 | Claude Code | Coze | AgentScope | Manus | DeepAgents V2 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 描述层限制 | 2% 上下文窗口（~16K chars） | 无明确字符限制 | 无（全量展示） | ~100 tokens/技能 | 无截断（开发者通过 `sources` 管理） |
| 内容层限制 | 无明确数量限制 | 50 编程 / 30 第三方 | 无明确限制 | <5K tokens/技能 | 可配置（默认 10 个） |
| 超出策略 | 排除技能，`/context` 可查 | 硬拒绝 | 不适用 | 三阶段渐进式 | 拒绝加载 + 引导 `unload_skill` |
| 动态卸载 | 无 | 无 | 有（`remove_agent_skill`） | 无 | 有（`unload_skill` 工具） |
| 可配置性 | 否（系统固定） | 否（系统固定） | 是（API 参数） | 否（系统固定） | 是（`max_loaded_skills` 可配置） |

> **关于 AgentScope 的说明**：AgentScope 的 `remove_agent_skill` 已经证明了动态卸载模式的价值。DeepAgents V2 的 `unload_skill` 工具借鉴了这一模式，但通过 `Command` 状态更新机制实现，与 DeepAgents 框架的既有模式保持一致。

---

## 5. `allowed-tools` 推荐策略

### 5.1 `allowed-tools` 字段的语义分析

在设计 `allowed-tools` 策略之前，需要理解该字段在不同系统中的语义差异：

| 系统 | `allowed-tools` 语义 | 字段状态 | 执行方式 |
| :--- | :--- | :--- | :--- |
| **Agent Skills 规范** [1] | “推荐使用的工具”（recommendation） | **实验性**字段 | 仅提示，不强制 |
| **Claude Code** [2] | “活跃时无需询问权限的工具”（tools that don't need permission when active） | 生产就绪 | 与权限系统集成 |
| **DeepAgents V1** | “Tool names the skill recommends using”（代码注释） | 仅解析和展示 | 仅在系统提示中显示 |

Agent Skills 规范明确将 `allowed-tools` 标记为**实验性**字段，其语义是“推荐使用的工具”，而非“限制只能使用的工具”。Claude Code 中的语义更强——“活跃时无需询问权限的工具”，但这是因为 Claude Code 拥有完整的权限系统。DeepAgents V1 的实现与 Agent Skills 规范一致，仅在系统提示中展示推荐工具。

### 5.2 设计决策：仅推荐，不拦截

V2 对 `allowed-tools` 字段采用**纯推荐策略**（RECOMMEND-only），不进行运行时拦截。这一决策基于以下考量：

1. **与 DeepAgents 哲学的一致性**：DeepAgents 的核心是 Agent 的自主性。运行时拦截通过硬编码的规则限制 Agent 的行为，与自主性原则相悖。推荐模式通过提供信息来辅助 Agent 决策，更符合人机协同的理念。
2. **与 HITL 中间件的关系**：如果需要对高风险工具进行权限控制，`HITL`（Human-in-the-Loop）中间件提供了更灵活的、基于用户确认的方案。废除运行时拦截避免了功能冗余和潜在的策略冲突。
3. **简化性**：移除了 `wrap_tool_call` / `awrap_tool_call` / `_check_allowed_tools` 等约 150 行代码和 8 个测试用例，显著降低了设计的复杂度和维护成本。

### 5.3 实现方式

`allowed-tools` 信息通过系统提示中的 `Recommended tools` 行展示（见 3.6.1 节 `_format_skills_list` 代码）。Agent 在调用工具时可以参考这些推荐，但不会被强制限制。

```
- **web-research** [Loaded]: Research topics using web search (requires: search)
  -> Recommended tools: search, read_file
  -> Resources: 2 scripts, 1 reference
```

> **与 V1.0 设计稿的差异说明**：V1.0 设计稿包含 `RESTRICT` 模式和完整的 `wrap_tool_call` 策略引擎。经过优化评估，V2 废除了 `RESTRICT` 模式，统一为 `RECOMMEND` 模式。如果未来有强制限制的需求，建议通过 `HITL` 中间件实现，或在 `SkillsMiddleware` 中重新引入 `wrap_tool_call` hook。当前架构为此预留了扩展空间——`AgentMiddleware` 基类已定义 `wrap_tool_call` 接口，未来可以在不修改公开 API 的情况下添加实现。

---

## 6. 向后兼容性保证

### 6.1 公开 API 兼容性

| API 元素 | V1 | V2 | 兼容性 |
| :--- | :--- | :--- | :---: |
| `SkillsMiddleware.__init__(backend, sources)` | ✅ | ✅（新增可选参数 `max_loaded_skills`，有默认值） | ✅ |
| `SkillMetadata` TypedDict | 7 个字段 | 7 个字段（不变） | ✅ |
| `SkillsState.skills_metadata` | `NotRequired` | `NotRequired`（不变） | ✅ |
| `create_deep_agent(skills=...)` | 传入 source 路径列表 | 传入 source 路径列表（不变） | ✅ |
| `__all__` 导出 | `["SkillMetadata", "SkillsMiddleware"]` | `["SkillMetadata", "SkillsMiddleware", "ResourceMetadata"]` | ✅ |

### 6.2 行为兼容性

**现有 SKILL.md 文件**。所有现存的 `SKILL.md` 文件无需任何修改。V2 新增的资源发现是增量功能——如果技能目录下没有 `scripts/`, `references/`, `assets/` 子目录，`skill_resources` 中对应的列表为空，不影响任何现有行为。

**Agent 行为**。V2 的系统提示引导 Agent 使用 `load_skill` 工具，但 Agent 仍然可以通过 `read_file` 直接读取 `SKILL.md`。区别在于：通过 `read_file` 读取不会触发状态更新（`skills_loaded` 不会被更新），因此不会获得资源摘要和加载状态标记。这是一种优雅降级，不会导致错误。

> **幂等性边界说明**：如果 Agent 先通过 `read_file` 读取了 `SKILL.md`，再调用 `load_skill`，由于 `skills_loaded` 为空（`read_file` 不更新状态），`load_skill` 会成功执行并返回 `Command`。这是**预期行为**——`load_skill` 的幂等性基于自身状态（`skills_loaded`），不感知外部 `read_file` 操作。Agent 会收到重复的内容，但状态会被正确更新。

**`allowed-tools` 行为**。V2 采用纯推荐模式，与 V1 行为完全一致（仅在系统提示中显示推荐工具，不进行运行时限制）。

**预算参数默认值**。`max_loaded_skills=10` 的默认值足够宽松，不会影响现有小规模技能库的行为。

### 6.3 SubAgent 隔离

当前架构中，主 Agent 和 SubAgent 各自拥有独立的 `SkillsMiddleware` 实例（在 `graph.py` 中分别创建）。由于 `skills_loaded` 和 `skill_resources` 都使用 `PrivateStateAttr`，它们不会传播到父级或子级 Agent。这意味着：

- 主 Agent 加载的技能不会自动在 SubAgent 中生效。
- SubAgent 的 `skills_loaded` 状态独立于主 Agent。
- 通用子代理（general-purpose subagent）自动继承主 Agent 的 skills sources 配置（由 `graph.py` 保证），但其加载状态是独立的。

---

## 7. 错误处理与降级策略

### 7.1 资源发现降级

如果 `backend.ls_info()` 在扫描资源目录时抛出异常（例如某些简化的 backend 实现不支持目录列表），`_discover_resources` 会捕获异常并记录警告，返回空列表。这确保了资源发现失败不会阻止技能系统的正常运行。

### 7.2 `load_skill` 工具错误处理

`load_skill` 工具的所有错误都通过返回描述性错误字符串来处理（而不是抛出异常或返回 `Command`），这确保了 Agent 可以理解错误并采取替代行动：

| 错误场景 | 返回类型 | 返回消息 | Agent 可采取的行动 |
| :--- | :---: | :--- | :--- |
| 技能名称不存在 | `str` | `"Error: Skill 'xxx' not found. Available skills: ..."` | 检查可用技能列表，修正名称 |
| 技能已加载 | `str` | `"Skill 'xxx' is already loaded."` | 直接使用已加载的技能指令 |
| 加载数量达到上限 | `str` | `"Error: Cannot load skill 'xxx'. Maximum ... Use unload_skill(...) ..."` | 使用 `unload_skill` 释放空间后重试 |
| 文件读取失败 | `str` | `"Error: Failed to read skill file at ..."` | 使用 `read_file` 作为后备 |
| 文件超过大小限制 | `str` | `"Error: Skill file at ... exceeds maximum size"` | 报告问题给用户 |
| 编码错误 | `str` | `"Error: Failed to decode skill file: ..."` | 报告问题给用户 |
| 成功加载 | `Command` | 技能内容 + 资源摘要（通过 `ToolMessage`） | 按照技能指令执行 |

**关键设计**：只有成功加载时才返回 `Command`（更新 `skills_loaded` 和 `skill_resources` 状态），所有错误情况都返回普通字符串（不更新状态）。这确保了只有真正成功加载的技能才会被标记为"已加载"。

### 7.3 `unload_skill` 工具错误处理

| 错误场景 | 返回类型 | 返回消息 | Agent 可采取的行动 |
| :--- | :---: | :--- | :--- |
| 技能未加载 | `str` | `"Error: Skill 'xxx' is not currently loaded. Currently loaded: ..."` | 检查已加载列表，修正名称 |
| 成功卸载 | `Command` | 卸载确认 + 当前加载状态（通过 `ToolMessage`） | 继续加载新技能或执行任务 |

**与 `load_skill` 一致的设计**：`unload_skill` 同样遵循"错误返回字符串、成功返回 `Command`"的模式，确保只有成功卸载时才更新状态。

---

## 8. 测试策略

### 8.1 单元测试

以下测试用例覆盖 V2 的所有新功能（共 24 个）：

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
| load_skill | `test_load_skill_max_loaded_reached` | 达到 `max_loaded_skills` 上限时返回错误字符串，消息中包含 `unload_skill` 引导 |
| unload_skill | `test_unload_skill_success` | 成功卸载返回 `Command`，`skills_loaded` 中移除技能名称 |
| unload_skill | `test_unload_skill_clears_resources` | 卸载后 `skill_resources` 中移除对应条目 |
| unload_skill | `test_unload_skill_not_loaded_returns_error` | 未加载技能返回错误字符串（非 `Command`） |
| unload_skill | `test_unload_skill_then_reload` | 卸载后可以重新加载同一技能（资源重新发现） |
| 系统提示 | `test_format_skills_list_with_loaded_status` | 已加载技能显示 `[Loaded]` 标记 |
| 系统提示 | `test_format_skills_list_with_resources` | 资源摘要正确显示（如 "2 scripts, 1 reference"） |
| 系统提示 | `test_format_skills_list_load_skill_guidance` | 未加载技能显示 `load_skill("name")` 引导 |
| 向后兼容 | `test_v1_skills_work_without_modification` | 无 V2 字段的 SKILL.md 正常工作 |
| 向后兼容 | `test_read_file_still_works_for_skills` | 通过 `read_file` 读取技能不会导致错误 |

### 8.2 集成测试

集成测试验证 `SkillsMiddleware` 与其他中间件的协作以及端到端场景：

1. **与 `FilesystemMiddleware` 的协作**：验证 `load_skill` 工具和 `read_file` 工具可以共存，且 Agent 可以先用 `load_skill` 加载技能，再用 `read_file` 读取资源。
2. **与 `SubAgentMiddleware` 的协作**：验证主 Agent 和 SubAgent 的 `skills_loaded` 状态相互隔离，SubAgent 在主 Agent 加载技能后可以独立加载。
3. **与 `SummarizationMiddleware` 的协作**：验证技能系统提示在上下文压缩后仍然正确。
4. **`load_skill` 后系统提示更新**：验证 `load_skill` 成功后，下一次 `wrap_model_call` 的系统提示中正确显示 `[Loaded]` 标记和资源摘要。
5. **`unload_skill` 后系统提示更新**：验证 `unload_skill` 成功后，下一次 `wrap_model_call` 的系统提示中该技能不再显示 `[Loaded]` 标记，且重新显示 `load_skill` 引导语。
6. **load → unload → reload 完整生命周期**：验证技能可以被加载、卸载、再次加载，且每次加载都正确触发资源发现和状态更新。

---

## 9. 扩展路线图

本节描述 V2 之后的扩展方向，这些功能在当前版本中仅预留扩展点，不实现。

### 9.1 Phase 3: 高级 Frontmatter 字段支持

| 字段 | 描述 | 实现思路 | 复杂度 |
| :--- | :--- | :--- | :---: |
| `disable-model-invocation` | 禁止模型自动加载技能 | 在 `_format_skills_list` 中为标记了此字段的技能添加 `(Manual only)` 标记，并在系统提示中说明"不要自动加载此技能" | 低 |
| `argument-hint` | 参数提示 | 在系统提示中显示提示文本，如 `load_skill("deploy", args="[env-name]")` | 低 |
| `model` | 模型覆盖 | 需要与 `wrap_model_call` 集成，在加载了指定 `model` 的技能后通过 `request.override` 切换模型。可能需要框架层面支持 | 高 |
| `context: fork` | 子代理执行 | 需要与 `SubAgentMiddleware` 深度集成，在 `load_skill` 时创建子代理上下文。可通过 `agent jumps` 机制（返回 `{"jump_to": "tools"}` 等）实现流程控制 | 高 |

### 9.2 Phase 4: 事件钩子系统

Claude Code 的 hooks 系统支持 14 种事件类型（`PreToolUse`, `PostToolUse`, `SessionStart` 等），处理器类型包括 `command`（Shell 命令）、`prompt`（LLM 提示）和 `agent`（代理钩子）。

在 DeepAgents 中实现类似系统的可行路径是：

1. **在 `SkillMetadata` 中新增 `hooks` 字段**，解析 SKILL.md frontmatter 中的 hooks 定义（YAML 格式）。
2. **将 hooks 事件映射到 `AgentMiddleware` 的 hook 点**：`PreToolUse` 映射到 `wrap_tool_call`（前置检查），`PostToolUse` 映射到 `wrap_tool_call`（后置处理），`SessionStart` 映射到 `before_agent`。
3. **实现 `command` 类型处理器**：通过 `backend.execute()`（如果 backend 实现了 `SandboxBackendProtocol`）执行 Shell 命令。
4. **实现 `prompt` 类型处理器**：将提示注入到下一次模型调用的上下文中。
5. **支持 `matcher` 模式匹配**：在 `wrap_tool_call` 中根据 matcher 正则表达式匹配工具名称。
6. **支持 `once` 字段**：技能级别的 hooks 支持 `once: true`，运行一次后自动移除。

这一扩展的主要挑战在于安全性——需要确保 hooks 中的 Shell 命令在沙箱环境中执行，且不会绕过权限控制。

### 9.3 Phase 5: SubAgent 技能继承策略

当前 V2 的 SubAgent 技能隔离是合理的默认行为，但某些场景下可能需要技能继承（例如主 Agent 加载了 `web-research` 技能后委托 SubAgent 进行研究任务）。

可行的实现路径是在 `SkillsMiddleware.__init__` 中新增 `subagent_inherit` 参数（`"isolated"` | `"inherit"`），并在 `graph.py` 中创建 SubAgent 的 `SkillsMiddleware` 实例时传递父级的 `skills_loaded` 状态。这需要修改 `graph.py`，因此不纳入 V2 范围。

### 9.4 Phase 6: CLI 集成

CLI 的 `deepagents skills list/create/info` 命令需要与 V2 的新功能兼容：

1. `deepagents skills list` 应显示资源计数。
2. `deepagents skills info <name>` 应显示资源详情。
3. `deepagents skills create` 应生成包含标准资源目录的脚手架。

这些变更限于 `libs/cli/deepagents_cli/skills/` 目录，不影响核心中间件。

### 9.5 Phase 7: `allowed-tools` 运行时拦截（可选）

如果未来有明确的需求需要运行时拦截（而非仅推荐），可以在 `SkillsMiddleware` 中重新引入 `wrap_tool_call` hook。当前架构已为此预留了扩展空间：

1. `AgentMiddleware` 基类已定义 `wrap_tool_call` / `awrap_tool_call` 接口。
2. 可以新增 `AllowedToolsPolicy` 枚举（`RECOMMEND` / `RESTRICT`）和 `allowed_tools_policy` 参数。
3. 在 `RESTRICT` 模式下，`wrap_tool_call` 检查工具调用是否在已加载技能的 `allowed-tools` 并集中。
4. 内置工具白名单（`load_skill`, `unload_skill`, `read_file`, `ls` 等）始终放行。

这一扩展不需要修改任何现有接口，可以作为 `__init__` 的新可选参数引入。

---

## 10. 实施计划

### 10.1 分阶段交付

| 阶段 | 时间估算 | 核心任务 | 交付物 | 验收标准 |
| :--- | :---: | :--- | :--- | :--- |
| **Phase 1** | 2-3 天 | 扩展 `SkillsState` 和 `SkillsStateUpdate`（新增 `skills_loaded`, `skill_resources`）；实现 `_discover_resources` / `_adiscover_resources`（延迟模式）；增强 `before_agent` / `abefore_agent`（初始化新状态字段）；创建 `load_skill` 工具（sync + async，含内容层预算检查）；创建 `unload_skill` 工具（sync + async） | 支持延迟资源发现、状态追踪、加载限制和动态卸载的中间件 | 所有 V1 测试通过 + 19 个新增单元测试通过（资源发现 5 + 状态初始化 2 + load_skill 8 + unload_skill 4） |
| **Phase 2** | 1-2 天 | 优化 `_format_skills_list`（含加载状态标记和资源摘要）；更新 `SKILLS_SYSTEM_PROMPT` 模板；更新 `modify_request` 传入新状态 | 完整的 V2 中间件 | 所有 24 个单元测试通过 + 6 个集成测试通过 |
| **Phase 3** | 1 天 | 文档更新、代码审查、性能测试（50+ 技能场景） | 可合并的 PR | 代码审查通过、无性能回归 |

### 10.2 文件变更清单

| 文件 | 变更类型 | 变更内容 |
| :--- | :---: | :--- |
| `deepagents/middleware/skills.py` | 修改 | 新增 `ResourceMetadata`；扩展 `SkillsState` / `SkillsStateUpdate`（新增 `skills_loaded`, `skill_resources`）；新增 `_discover_resources` / `_adiscover_resources`；增强 `before_agent` / `abefore_agent`；新增 `_create_load_skill_tool` / `_create_unload_skill_tool` / `_get_backend_from_runtime` / `_execute_load_skill` / `_aexecute_load_skill` / `_execute_unload_skill`；增强 `_format_skills_list` / `_format_resource_summary` / `modify_request`；更新 `SKILLS_SYSTEM_PROMPT`；扩展 `__init__`（新增 `max_loaded_skills` 可选参数）；更新 `__all__` |
| `tests/unit_tests/middleware/test_skills_middleware.py` | 修改 | 新增 24 个测试用例（资源发现 5 + 状态初始化 2 + load_skill 8 + unload_skill 4 + 系统提示 3 + 向后兼容 2） |
| `tests/integration_tests/test_skills_integration.py` | 新增 | 6 个集成测试 |

**不变更的文件**：`graph.py`、`middleware/__init__.py`、`middleware/_utils.py`、`middleware/filesystem.py`、`middleware/memory.py`、`middleware/subagents.py`、`middleware/summarization.py`、`middleware/patch_tool_calls.py`、`backends/protocol.py`。

---

## 11. 已知限制与约束

本节汇总了 V2 设计方案中所有已知的限制和设计约束，以确保研发团队在实施时有清晰的预期。

### 11.1 状态更新语义与并发安全性

**状态更新语义**。`skills_loaded` 和 `skill_resources` 字段没有定义自定义 reducer。在没有 reducer 的情况下，LangGraph 的默认行为是**覆盖**（last-write-wins）。`_execute_load_skill` 和 `_execute_unload_skill` 使用"读取全量 → 修改 → 写回全量"的模式，这在覆盖语义下是正确的。

**与 FilesystemMiddleware 的对比**。`FilesystemMiddleware` 的 `files` 字段使用了自定义 reducer `_file_data_reducer`，因为 `write_file` 只发送 delta（单个文件的更新），需要 reducer 来合并。而 `load_skill` / `unload_skill` 发送的是全量 `skills_loaded` 列表，不需要 reducer 来合并。这是两种不同的状态更新模式：

| 模式 | 使用场景 | 是否需要 reducer |
| :--- | :--- | :---: |
| Delta 更新 | `write_file` 发送单个文件的更新 | 是（`_file_data_reducer` 合并 delta） |
| 全量更新 | `load_skill` / `unload_skill` 发送完整的 `skills_loaded` 列表 | 否（覆盖语义即可） |

**并发安全性**。当前 DeepAgents 框架不支持并行工具调用（parallel tool calls），所有工具调用是顺序执行的。因此，`load_skill` 和 `unload_skill` 不会并发执行，"读取全量 → 修改 → 写回全量"的模式是安全的，不会出现竞态条件。

**未来扩展（研发团队关注点）**。如果未来 DeepAgents 支持并行工具调用，需要为 `skills_loaded` 和 `skill_resources` 定义自定义 reducer。具体方案如下：

```python
# 示例：为 skills_loaded 定义 append-only reducer
def _skills_loaded_reducer(
    current: list[str],
    update: list[str],
) -> list[str]:
    """合并 skills_loaded 更新，去重保序。"""
    seen = set(current)
    result = list(current)
    for name in update:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result
```

此 reducer 可以在 `SkillsState` 的类型注解中通过 `Annotated[list[str], _skills_loaded_reducer]` 引入。但在当前框架不支持并行工具调用的前提下，**不建议提前引入 reducer**，以避免不必要的复杂性。

### 11.2 `sources` 运行时不可变

`SkillsMiddleware` 的 `sources` 参数在 `__init__` 时固定，运行时不可变。这意味着如果用户在 Agent 运行期间通过 `write_file` 创建了新的技能目录（例如 `/home/ubuntu/new_skills/`），中间件不会自动发现这个新目录。Agent 需要重新启动才能识别新的 `sources`。这与 V1 的行为一致，不是 V2 引入的新限制。

### 11.3 SubAgent 技能隔离与典型场景应对指南

V2 不支持 SubAgent 技能继承。主 Agent 和 SubAgent 的技能加载状态是完全隔离的。以下是典型场景的应对指南（研发团队关注点）：

| 场景 | 当前行为 | 推荐应对方式 |
| :--- | :--- | :--- |
| 主 Agent 加载了 `web-research` 技能，委托 SubAgent 进行研究 | SubAgent 不继承 `web-research` 技能，需要自行加载 | SubAgent 的 `SkillsMiddleware` 配置相同的 `sources`，SubAgent 在执行任务时自行调用 `load_skill("web-research")` |
| 主 Agent 加载了 `code-review` 技能，创建 SubAgent 执行代码审查 | SubAgent 不继承 `code-review` 技能 | 在主 Agent 的系统提示或任务描述中明确指示 SubAgent 加载所需技能 |
| SubAgent 需要使用主 Agent 已加载技能的资源文件 | SubAgent 无法访问主 Agent 的 `skill_resources` 状态 | 资源文件路径是确定性的（基于 `sources` 配置），SubAgent 可以通过 `read_file` 直接访问资源文件，或通过 `load_skill` 重新发现资源 |

**设计原则**：SubAgent 的技能隔离是有意的设计选择，确保了状态的可预测性和安全性。如果未来需要技能继承，参见 9.3 节的扩展路线图。

### 11.4 技能卸载的语义边界

`unload_skill` 从状态中移除技能名称和资源缓存，但**不会从对话历史中删除之前 `load_skill` 返回的内容**。这意味着：

1. **Agent 仍可参考已卸载技能的内容**：对话历史中的 `ToolMessage` 不会被删除，Agent 在后续推理中仍可能参考这些内容。
2. **系统提示中不再标记为 `[Loaded]`**：下一次 `wrap_model_call` 时，该技能在系统提示中不再显示 `[Loaded]` 标记，而是重新显示 `load_skill` 引导语。
3. **重新加载会触发资源重新发现**：由于 `skill_resources` 中的缓存已被清除，重新加载时会重新扫描资源目录。

这一行为与操作系统的"关闭文件"语义类似——关闭文件不会删除之前读取的数据，但释放了文件描述符（加载名额）。

### 11.5 性能与日志

**性能影响分析**。V2 的性能开销主要集中在以下新增的操作中：

| 操作 | 额外开销 | 调用频率 | 影响评估 |
| :--- | :--- | :--- | :--- |
| `load_skill` | 1-3 次 `backend.ls_info` 调用（延迟资源发现） | 低（每个技能仅一次） | 可忽略 |
| `unload_skill` | 无 I/O 操作（仅状态更新） | 低 | 可忽略 |
| `_format_skills_list` | 遍历技能列表 + 加载状态检查 | 中（每次模型调用） | 可忽略 |

在典型场景下（<100 个技能，<10 个已加载技能），这些开销是毫秒级的，不会对整体性能产生显著影响。`before_agent` 的性能与 V1 完全相同（不再扫描资源）。

**日志策略**。方案中的 `logger.warning` 仅为示例。建议在实施时采用结构化日志，记录所有关键事件：

| 事件 | 日志级别 | 示例 |
| :--- | :---: | :--- |
| 技能发现 | `INFO` | `Discovered 15 skills from 2 sources` |
| 技能加载成功 | `INFO` | `Skill 'web-research' loaded (3 resources discovered)` |
| 技能卸载成功 | `INFO` | `Skill 'web-research' unloaded (7/10 slots available)` |
| 加载限制触发 | `WARNING` | `Skill loading limit reached (10/10)` |
| 资源发现失败 | `WARNING` | `Failed to list resources for skill 'deploy'` |
| 技能文件读取失败 | `ERROR` | `Failed to read SKILL.md at skills/deploy/SKILL.md` |

---

## 附录 A：完整的新增/修改方法清单

| 方法 | 类型 | 描述 |
| :--- | :---: | :--- |
| `_discover_resources()` | 新增（模块级） | 同步延迟资源发现 |
| `_adiscover_resources()` | 新增（模块级） | 异步延迟资源发现 |
| `_format_resource_summary()` | 新增（模块级） | 资源摘要格式化 |
| `SkillsMiddleware.__init__()` | 修改 | 新增 `max_loaded_skills` 参数、`self.tools` 属性 |
| `SkillsMiddleware._create_load_skill_tool()` | 新增 | 创建 load_skill 工具 |
| `SkillsMiddleware._create_unload_skill_tool()` | 新增 | 创建 unload_skill 工具 |
| `SkillsMiddleware._get_backend_from_runtime()` | 新增 | 从 ToolRuntime 解析 backend |
| `SkillsMiddleware._execute_load_skill()` | 新增 | load_skill 同步核心逻辑（含内容层预算检查 + 延迟资源发现） |
| `SkillsMiddleware._aexecute_load_skill()` | 新增 | load_skill 异步核心逻辑（含内容层预算检查 + 延迟资源发现） |
| `SkillsMiddleware._execute_unload_skill()` | 新增 | unload_skill 核心逻辑（同步/异步共用） |
| `SkillsMiddleware._format_skills_list()` | 修改 | 新增 `loaded` 和 `resources` 参数、加载状态标记、资源摘要 |
| `SkillsMiddleware.modify_request()` | 修改 | 传入新状态字段 |
| `SkillsMiddleware.before_agent()` | 修改 | 新增 `skills_loaded` 和 `skill_resources` 状态初始化 |
| `SkillsMiddleware.abefore_agent()` | 修改 | 新增 `skills_loaded` 和 `skill_resources` 状态初始化（异步） |

---

## 附录 B：新增类型定义汇总

```python
class ResourceMetadata(TypedDict):
    """技能资源元数据。"""
    path: str                                           # 资源文件路径
    type: Literal["script", "reference", "asset", "other"]  # 资源类型
    skill_name: str                                     # 所属技能名称


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
```

---

## 附录 D：变更对比摘要（V1.0 设计稿 → V2 最终版）

本附录汇总了从 V1.0 设计稿（`skills_middleware_v2_final.md`）到 V2 最终版的所有变更，便于已阅读过 V1.0 设计稿的研发团队快速理解差异。

| 维度 | V1.0 设计稿 | V2 最终版 | 变更原因 |
| :--- | :--- | :--- | :--- |
| `__init__` 新增参数 | 4 个（`allowed_tools_policy`, `max_description_budget`, `max_loaded_skills`, `always_allowed_tools`） | 1 个（`max_loaded_skills`） | 废除 RESTRICT 模式和描述层预算 |
| Hook 使用 | 3 个（`before_agent` + `wrap_model_call` + `wrap_tool_call`） | 2 个（`before_agent` + `wrap_model_call`） | 废除 RESTRICT 模式，移除 `wrap_tool_call` |
| 工具 | 1 个（`load_skill`） | 2 个（`load_skill` + `unload_skill`） | 新增动态卸载能力 |
| `allowed-tools` 策略 | 双模式（`RECOMMEND` + `RESTRICT`） | 单模式（仅 `RECOMMEND`） | 简化设计，避免与 HITL 功能重叠 |
| 描述层预算 | 有（`max_description_budget` 参数 + 截断逻辑） | 无（开发者通过 `sources` 管理） | 避免武断截断，鼓励良好实践 |
| 内容层预算 | 有（`max_loaded_skills`，达到上限时阻止加载） | 有（`max_loaded_skills`，达到上限时引导 `unload_skill`） | `unload_skill` 使限制变为弹性 |
| 单元测试 | 31 个 | 24 个 | 移除 RESTRICT 和描述预算测试，新增 unload_skill 测试 |
| `__all__` 导出 | 新增 `AllowedToolsPolicy`, `ResourceMetadata` | 仅新增 `ResourceMetadata` | 废除 `AllowedToolsPolicy` |
| 新增类型 | `ResourceMetadata`, `AllowedToolsPolicy` | 仅 `ResourceMetadata` | 废除 `AllowedToolsPolicy` |
| SubAgent 说明 | 简要说明隔离行为 | 新增典型场景应对指南表格 | 响应研发团队反馈 |
| 并发安全性说明 | 简要提及未来扩展 | 新增 reducer 示例代码和明确建议 | 响应研发团队反馈 |

---

## 参考文献

[1]: Agent Skills. "Agent Skills Specification." agentskills.io. Accessed Feb 16, 2026. https://agentskills.io/specification

[2]: Anthropic. "Skills - Claude Code." code.claude.com. Accessed Feb 17, 2026. https://code.claude.com/docs/en/skills

[3]: Coze. "使用技能." coze.cn. Accessed Feb 17, 2026. https://www.coze.cn/open/docs/guides/using_skill

[4]: OpenAI. "Assistants API." platform.openai.com. Accessed Feb 17, 2026. https://platform.openai.com/docs/assistants/overview

[5]: Anthropic. "Skills - Claude Code: Context Budget." code.claude.com. Accessed Feb 17, 2026. https://code.claude.com/docs/en/skills#context-budget

[6]: Anthropic. "Effective Context Engineering for AI Agents." anthropic.com. Accessed Feb 17, 2026. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

[7]: LangChain. "Custom Middleware - Deep Agents." docs.langchain.com. Accessed Feb 17, 2026. https://docs.langchain.com/deep-agents/middleware

[8]: LangChain. "Deep Agents Skills." docs.langchain.com. Accessed Feb 17, 2026. https://docs.langchain.com/deep-agents/skills

[9]: AgentScope. "Agent Skills Management." agentscope.io. Accessed Feb 17, 2026. https://agentscope.io/docs/skills
