# DeepAgents SDK 升级说明

**版本**: V2.0
**日期**: 2026-02-18
**适用对象**: 使用 DeepAgents SDK 的外部研发团队

---

## 快速总结

**一句话**: SkillsMiddleware V2 是**向后兼容**的功能增强版，现有代码无需修改即可升级。

**核心变化**:
- ✅ **新增** `load_skill` / `unload_skill` 工具
- ✅ **新增** 上下文预算控制 (默认 10 个技能)
- ✅ **新增** 资源自动发现
- ✅ **保持** 所有现有 API 不变
- ✅ **保持** 现有 SKILL.md 文件兼容

---

## 1. 升级内容详解

### 1.1 新增功能

| 功能 | 说明 | 影响 |
| :--- | :--- | :--- |
| `load_skill` 工具 | 专用工具加载技能完整内容 | Agent 不再需要手动 `read_file` |
| `unload_skill` 工具 | 卸载已加载技能释放上下文 | 防止上下文溢出 |
| `[Loaded]` 标记 | 系统提示显示已加载技能 | Agent 清楚知道哪些技能已激活 |
| 资源发现 | 自动扫描 `scripts/`, `references/`, `assets/` | Agent 知道技能有哪些资源文件 |
| 上下文预算 | 默认最多 10 个同时加载技能 | 防止性能下降 |

### 1.2 与官方 Agent Skills 规范的差异

| 维度 | 官方规范 | DeepAgents V2 | 说明 |
| :--- | :--- | :--- | :--- |
| 技能加载 | 手动 | `load_skill` 工具 | 更灵活 |
| 技能卸载 | ❌ 不支持 | ✅ `unload_skill` | **DeepAgents 特有** |
| 资源发现 | 自动 | 延迟发现 | 性能优化 |
| 上下文预算 | 无限制 | `max_loaded_skills=10` | **DeepAgents 特有** |
| `allowed-tools` | 推荐语义 | 推荐语义 | 与规范一致 |

**重要**: DeepAgents 是基于 Agent Skills 规范的**扩展实现**，不是官方参考实现。

---

## 2. 兼容性保证

### 2.1 向后兼容

```python
# V1 代码无需修改，直接使用
from deepagents.middleware import SkillsMiddleware

middleware = SkillsMiddleware(
    backend=backend,
    sources=["/skills/"],
)
```

### 2.2 SKILL.md 文件格式

```yaml
# 现有 SKILL.md 文件无需任何修改
---
name: web-research
description: Structured approach to web research
license: MIT
---
```

### 2.3 状态字段扩展

V2 新增的状态字段（不影响现有代码）:

```python
class SkillsState(AgentState):
    skills_metadata: ...  # V1 已有
    skills_loaded: ...    # V2 新增 - 已加载技能列表
    skill_resources: ...  # V2 新增 - 资源缓存
```

---

## 3. 使用示例

### 3.1 基础使用（与 V1 相同）

```python
from deepagents import create_deep_agent
from deepagents.middleware import SkillsMiddleware
from deepagents.backends import FilesystemBackend

agent = create_deep_agent(
    skills=["/path/to/skills/"],
    backend=FilesystemBackend(root_dir="/workspace"),
)
```

### 3.2 V2 新功能（可选）

```python
# Agent 现在可以使用专用工具
# load_skill("skill-name") - 加载技能
# unload_skill("skill-name") - 卸载技能

# 自定义上下文预算
middleware = SkillsMiddleware(
    backend=backend,
    sources=["/skills/"],
    max_loaded_skills=15,  # 默认 10，可调大/小
)
```

---

## 4. 升级检查清单

如果你的团队使用了 SkillsMiddleware，请确认：

- [ ] **现有代码** - 无需修改，直接兼容
- [ ] **SKILL.md 文件** - 无需修改，直接兼容
- [ ] **测试用例** - 建议运行一次完整测试
- [ ] **文档** - 更新内部文档说明 V2 新功能
- [ ] **监控** - 观察 `max_loaded_skills` 是否合理（默认 10）

---

## 5. 已知限制

| 限制 | 说明 | 缓解策略 |
| :--- | :--- | :--- |
| 并行工具调用 | 当前框架不支持并行 | 未来可添加 reducer |
| `sources` 运行时不可变 | `__init__` 时固定 | 重启 agent 以识别新 `sources` |
| SubAgent 技能隔离 | 状态不共享 | SubAgent 自行 `load_skill` |
| 卸载不删除历史 | 仅移除状态标记 | 预期行为 |

---

## 6. 技术联系

**问题反馈**: 请提交 GitHub Issue
**文档**:
- [SkillsMiddleware V2 设计文档](./DeepAgents_SkillsMiddleware_V2_升级设计方案_final.md)
- [核查报告](./SkillsMiddleware_V2_核查报告.md)
- [Phase3 审查报告](./Phase3_CodeReview_Report.md)

---

## 附录 A: 完整变更列表

### A.1 新增类型

```python
class ResourceMetadata(TypedDict):
    path: str
    type: Literal["script", "reference", "asset", "other"]
    skill_name: str
```

### A.2 新增状态字段

```python
# SkillsState 扩展
skills_loaded: list[str]           # 已加载技能名称
skill_resources: dict[...]         # 资源缓存
```

### A.3 新增工具

```python
# SkillsMiddleware.tools 自动包含
- load_skill(skill_name: str) -> Command | str
- unload_skill(skill_name: str) -> Command | str
```

### A.4 新增参数

```python
def __init__(
    self,
    *,
    backend: BACKEND_TYPES,
    sources: list[str],
    max_loaded_skills: int = 10,  # V2 新增
) -> None:
```

### A.5 新增函数

```python
# 模块级函数
def _discover_resources(...) -> list[ResourceMetadata]
def _adiscover_resources(...) -> list[ResourceMetadata]
def _format_resource_summary(...) -> str
def _format_skill_annotations(...) -> str
```

---

**升级完成日期**: 2026-02-18
**Git Commit**: `178b14e feat(skills): SkillsMiddleware V2 完整实施`

---

## Round 8+9 变更摘要 (2026-03-28~29)

### SDK 变更（向后兼容）

**FileData 类型放松**:

- `FileData.created_at` 和 `FileData.modified_at` 从 `str` 改为 `NotRequired[str]`
- 外部代码构造 `FileData` 时不再需要提供这两个字段
- `create_file_data()` 仍然可用，签名不变

**HumanMessage 驱逐**:

- `FilesystemMiddleware` 新增参数 `human_message_token_limit_before_evict: int | None = 50000`
- 超过阈值的 HumanMessage 自动写入文件系统并替换为截断预览
- 有默认值，不传参时行为不变

**CRLF 规范化**:

- `FilesystemBackend.edit()` 自动将 `old_string`/`new_string` 中的 `\r\n`/`\r` 规范化为 `\n`

**wrap_model_call 返回类型扩展**:

- `FilesystemMiddleware.wrap_model_call` 返回类型从 `ModelResponse[ResponseT]` 扩展为 `ModelResponse[ResponseT] | ExtendedModelResponse`
- ⚠️ 如果外部团队有自定义 middleware 子类覆写了 `wrap_model_call`/`awrap_model_call`，需要检查返回类型标注

### 依赖版本

- `langchain-core` → 1.2.22
- `cryptography` → 46.0.6
- `langchain-google-genai` → >=4.2.1

### 迁移检查清单

- [ ] 确认自定义 `FileData` 构造代码在缺少 `created_at`/`modified_at` 时仍正常
- [ ] 如有自定义 middleware 覆写 `wrap_model_call`，检查返回类型兼容性
- [ ] 如严格锁定 `langchain-*` 版本，做依赖求解验证

---

## Round 10 变更摘要 (2026-04-02)

### ⚠️ Backend Factory 废弃（行为变更）

`StateBackend(runtime)` factory callable 模式已废弃。直接使用 `StateBackend()`，runtime 由 middleware 内部注入。

```python
# 旧方式（已废弃，会打印 DeprecationWarning）
backend = lambda rt: StateBackend(rt)
create_deep_agent(model=model, backend=backend)

# 新方式
backend = StateBackend()
create_deep_agent(model=model, backend=backend)
```

### 其他变更

- **recursion_limit**: 10001 → 9999
- **deprecated protocol methods**: `ls_info()`/`glob_info()`/`grep_raw()` 返回类型恢复为原始类型（`list[FileInfo]`等），降低自定义 backend 升级摩擦
- **State backend offloading**: `_offload_to_backend` 返回 `tuple[str|None, dict|None]`，支持 `files_update` 传递
- **async sub-agents**: 修复 TypeError，移除 `from __future__ import annotations`
- **OpenAI-compatible**: `resolve_model()` 自动禁用非 OpenAI 端点的 Responses API
- **http_request tool**: 已从 CLI agent 中移除
- **pygments**: 升级到 2.20.0（安全修复 GHSA-5239-wwwm-4pmq）

### 迁移检查清单

- [ ] 将 `StateBackend(runtime)` / `lambda rt: StateBackend(rt)` 改为 `StateBackend()`
- [ ] 如使用 `_offload_to_backend` 返回值，适配新的 tuple 返回类型
- [ ] 如有调用 `http_request` 工具的代码，需移除相关引用

---

## Round 10+ 变更摘要 (2026-04-04)

### SubAgent 实时进度 Streaming

SubAgent 执行过程中通过 `stream_writer` 发出 `subagent_progress` 自定义事件，客户端可实时获取工具调用、工具结果、AI 思考等进度信息。

**前端接入要求**:

- `streamMode` 必须包含 `"custom"`：`streamMode: ["values", "messages", "custom"]`
- 处理 `event.type === "custom"` 中的 `subagent_progress` 事件

**事件数据结构**:

```typescript
{
  type: "subagent_progress",
  subagent_type: string,      // SubAgent 名称
  message_count: number,       // 当前消息总数
  step_type?: "tool_call" | "tool_result" | "thinking",
  tool_name?: string,          // 工具名称
  content_preview?: string,    // 内容摘要（最多 300 字符，不含工具参数）
}
```

**诊断开关**: `DEEPAGENTS_SUBAGENT_STREAM_DIAGNOSTICS=1` 可启用服务端诊断日志。

### ⚠️ _EXCLUDED_STATE_KEYS 扩展（并行 SubAgent 修复）

新增三个字段到 `_EXCLUDED_STATE_KEYS`：`skills_loaded`、`skill_resources`、`_summarization_event`。

**影响**: 修复并行 SubAgent 执行时的 `InvalidUpdateError: At key 'skills_loaded': Can receive only one value per step`。

**根因**: `astream(stream_mode="values")` 使用 `stream_channels`（不过滤 `PrivateStateAttr`），导致这些字段从 SubAgent 结果泄漏回父 Agent。`invoke()` 路径不受影响（`output_channels` 正确过滤了 `PrivateStateAttr`）。

**⚠️ 自定义 Backend 注意**: 如有自定义 Backend 实现的 `ls()`/`glob()` 返回 `list` 而非 `LsResult`/`GlobResult`，框架现在会自动包装并发出 `DeprecationWarning`。**v0.7 将移除此兼容支持**，请尽快迁移到正确的返回类型。

### 迁移检查清单

- [ ] 前端 `streamMode` 配置添加 `"custom"` 以接收 SubAgent 进度事件
- [ ] 如有自定义 Backend 的 `ls()`/`glob()` 返回 `list`，改为返回 `LsResult`/`GlobResult`
- [ ] 并行 SubAgent 场景：确认升级后 `InvalidUpdateError` 不再出现

---

## Round 11 变更摘要 (2026-04-05)

### ⚠️ Legacy SubAgent API 移除（向后兼容 shim 保留）

上游删除了 `_get_subagents_legacy()`、`SubAgentKwargs`、`CompiledSubAgent` 中的 `Unpack` 用法。

**本地保留了向后兼容 shim**：`SubAgentMiddleware` 仍接受 `default_model`/`default_tools`/`general_purpose_agent`，但会发出 `DeprecationWarning`。

```python
# 旧方式（仍可用，但会发出 DeprecationWarning）
SubAgentMiddleware(default_model="openai:gpt-4o", default_tools=[...])

# 新方式（推荐）
SubAgentMiddleware(
    backend=StateBackend(),
    subagents=[{"name": "...", "model": "...", "tools": [...], ...}],
)
```

### SubAgent interrupt_on 继承（尚未合入）

> **注意**: 此变更存在于上游 (`acad9bb6`) 但**尚未合入本仓库 master**。
> 当前行为：Declarative SubAgent **不会**继承 parent 的 `interrupt_on`。
> 上游计划行为：默认继承，opt-out 通过 `interrupt_on: {}` 实现。
> 外部团队的防御性 opt-out（F1）仍然推荐，为未来合入做准备。

### 其他变更

- Parent `RunnableConfig` 转发到 SubAgent（LangSmith trace 连续性）
- `_EXCLUDED_STATE_KEYS` 扩展（防止并行 SubAgent 的 `InvalidUpdateError`）
- `WriteResult`/`EditResult` 的 `files_update` 增加 deprecation warning（v0.7 移除）

### 迁移检查清单

- [ ] 将 `SubAgentMiddleware(default_model=...)` 改为新 API
- [ ] 如有 SubAgent 依赖"静默执行不弹审批"，添加 `interrupt_on: {}`
- [ ] 如有自定义 middleware 覆写 `wrap_model_call`，检查返回类型

### SSE 长连接注意事项

SubAgent 执行可能持续 5-15 分钟。在单步 LLM 推理或工具执行期间，SSE 连接可能因 HTTP idle timeout（通常 2 分钟）断开。建议：

- **反向代理层**（nginx/Caddy 等）：将 SSE 路由的 `proxy_read_timeout` 调至 15-30 分钟
- **前端**：保留 `onDisconnect: "continue"` 配置 + 轮询兜底机制
- 框架的 `stream_writer` 在 SubAgent 活跃步骤间正常发出事件，但无法覆盖单步长时间执行的空闲期
