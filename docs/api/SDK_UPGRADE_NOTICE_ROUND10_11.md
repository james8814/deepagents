# DeepAgents SDK 升级说明 — Round 10+11

**日期**: 2026-04-05
**适用对象**: 使用 DeepAgents SDK 的外部研发团队
**SDK 版本**: 0.5.0（版本号不变）
**涵盖变更**: Round 10 (2026-04-02) + Round 10+ (2026-04-04) + Round 11 (2026-04-05)

---

## 快速总结

本次升级包含 3 项必须关注的行为变更、6 项废弃预告（v0.7 移除）和多项向后兼容增强。

**必须关注**:
1. Backend Factory callable 模式废弃 → 改用 `StateBackend()` 直接实例化
2. SubAgent `interrupt_on` 继承 → 子代理默认继承父代理的 HITL 配置
3. `wrap_model_call` 返回类型扩展 → 自定义 middleware 需检查类型标注

**废弃预告（v0.7 移除，共 6 项）**: `WriteResult.files_update`、`ls_info()`/`glob_info()`/`grep_raw()` 返回 `list` 兼容、`SubAgentMiddleware(default_model=...)`、`StateBackend(runtime)` — 详见§6

---

## 1. Backend Factory 废弃（必须关注）

### 变更内容

`StateBackend(runtime)` factory callable 模式已废弃。`create_deep_agent` 内部现在直接使用 `StateBackend()` 实例。

### 影响判断

| 使用方式 | 功能影响 | DeprecationWarning | 操作 |
|---------|---------|-------------------|------|
| `StateBackend` 作为 class ref（不带括号） | ✅ 受影响 | 每次工具调用 1x | 改为 `StateBackend()` |
| `StateBackend(runtime)` 传入 runtime 参数 | ✅ 受影响 | 每次工具调用 1x | 改为 `StateBackend()` |
| 自定义 `get_backend_factory()` 返回 callable | ❌ **功能不受影响** | ⚠️ **每次工具调用 1x** | 见下方说明 |
| `FilesystemBackend(root_dir=...)` | ❌ 不受影响 | 无 | 无需改动 |

> **⚠️ 自定义 Backend Factory 警告说明**: `FilesystemMiddleware._get_backend()` 对**所有 callable backend** 发出 `DeprecationWarning`（`filesystem.py:L861`），包括自定义 factory。功能完全正常，但每次 filesystem 工具调用（read_file, write_file, edit_file, ls, glob, grep, execute）都会产生 1 次警告。如果日志噪声不可接受，建议将 factory 返回的结果缓存为实例后传入，或使用 `warnings.filterwarnings("ignore", category=DeprecationWarning, module="deepagents.middleware.filesystem")` 抑制。

### 迁移示例

```python
# ❌ 旧方式（产生 DeprecationWarning）
backend = StateBackend  # class ref, 不是实例
backend = lambda rt: StateBackend(rt)

# ✅ 新方式
backend = StateBackend()

# ⚠️ 自定义 factory 功能正常，但会产生 DeprecationWarning
def get_backend_factory():
    return lambda rt: CompositeBackend(...)  # 功能不受影响，但每次工具调用有警告

# ✅ 消除警告的方式：直接构造实例传入（不用 factory）
backend = CompositeBackend(
    default=StateBackend(),
    routes={"/workspace/": FilesystemBackend(root_dir="/workspace")},
)
create_deep_agent(model=model, backend=backend)
```

---

## 2. SubAgent interrupt_on 继承（必须关注）

### 变更内容

Declarative `SubAgent` 现在**默认继承** parent agent 的 `interrupt_on` 配置。

### 行为变化

| 场景 | 升级前 | 升级后 |
|------|--------|--------|
| parent 设 `interrupt_on={"edit_file": True}`，SubAgent 未配置 | SubAgent 静默执行 `edit_file` | SubAgent **弹出审批** |
| SubAgent 显式设 `interrupt_on: {}` | — | SubAgent 静默执行（opt-out） |
| `CompiledSubAgent` | 不继承 | **仍然不继承** |
| `AsyncSubAgent` | 不继承 | **仍然不继承** |

### opt-out 方法

如果你的 SubAgent 依赖"静默执行不弹审批"的行为：

```python
subagents=[
    {
        "name": "batch-processor",
        "description": "Processes files in batch",
        "system_prompt": "...",
        "interrupt_on": {},  # ← 显式 opt-out，不继承 parent
    }
]
```

---

## 3. wrap_model_call 返回类型扩展（自定义 middleware 需关注）

### 变更内容

`FilesystemMiddleware.wrap_model_call` 返回类型从 `ModelResponse[ResponseT]` 扩展为 `ModelResponse[ResponseT] | ExtendedModelResponse`。

### 影响判断

| 使用方式 | 是否受影响 |
|---------|-----------|
| 使用 `create_deep_agent()` 不覆写 middleware | ❌ 不受影响 |
| 自定义 middleware 子类覆写 `wrap_model_call` | ✅ 需检查返回类型标注 |
| 启用 ty/mypy 类型检查 | ✅ 可能出现新的类型错误 |

### 迁移方式

```python
# 如果你的自定义 middleware 覆写了 wrap_model_call：
from langchain.agents.middleware.types import ExtendedModelResponse

def wrap_model_call(self, request, handler):
    response = handler(request)
    # 返回类型现在可以是 ModelResponse | ExtendedModelResponse
    return response
```

---

## 4. SubAgent Legacy API 废弃（向后兼容 shim 保留）

### 变更内容

上游删除了 `_get_subagents_legacy()`。本仓库保留了向后兼容 shim。

### 影响判断

| 使用方式 | 是否受影响 |
|---------|-----------|
| `SubAgentMiddleware(default_model=..., default_tools=...)` | ⚠️ 产生 DeprecationWarning，但**仍可用** |
| `SubAgentMiddleware(backend=..., subagents=[...])` （新 API） | ❌ 推荐方式 |

### 迁移示例

```python
# ❌ 旧方式（DeprecationWarning）
SubAgentMiddleware(
    default_model="openai:gpt-4o",
    default_tools=[...],
)

# ✅ 新方式
SubAgentMiddleware(
    backend=StateBackend(),
    subagents=[
        {"name": "...", "model": "openai:gpt-4o", "tools": [...], ...},
    ],
)
```

---

## 5. 向后兼容增强（无需改动）

以下变更**向后兼容**，无需修改现有代码：

| 变更 | 说明 |
|------|------|
| `FileData.created_at/modified_at` → `NotRequired` | 构造 `FileData` 时可省略时间戳 |
| `FilesystemMiddleware` + `human_message_token_limit_before_evict` | 超大 HumanMessage 自动驱逐（默认 50k tokens） |
| `FilesystemBackend.edit()` CRLF 规范化 | 自动将 `\r\n` 转为 `\n` |
| SubAgent `stream_writer` 进度事件 | 前端可通过 `stream_mode="custom"` 接收 SubAgent 执行进度 |
| `_EXCLUDED_STATE_KEYS` 扩展 | 防止并行 SubAgent 的 `InvalidUpdateError` |
| Parent `RunnableConfig` 转发到 SubAgent | LangSmith trace 连续性 |
| `create_deep_agent` 返回类型泛型化 | `CompiledStateGraph[AgentState[ResponseT], ContextT, ...]` |
| `recursion_limit` 调整为 9999 | 内部参数，不影响外部行为 |
| `ls_info()` / `glob_info()` 返回原始类型 | 降低自定义 Backend 升级摩擦 |

---

## 6. 废弃预告（v0.7 移除）

以下功能将在 **v0.7** 中移除，请提前规划迁移：

| 废弃项 | 当前行为 | v0.7 行为 | 迁移方式 |
|--------|---------|----------|---------|
| `WriteResult.files_update` | 可用（DeprecationWarning） | 移除 | State 更新由 backend 内部处理 |
| `ls_info()` 返回 `list` | 自动包装为 `LsResult` | 不再兼容 | 返回 `LsResult` |
| `glob_info()` 返回 `list` | 自动包装为 `GlobResult` | 不再兼容 | 返回 `GlobResult` |
| `grep_raw()` 返回 `str` | 自动包装为 `GrepResult` | 不再兼容 | 返回 `GrepResult` |
| `SubAgentMiddleware(default_model=...)` | DeprecationWarning | 移除 | 使用 `backend=...` 新 API |
| `StateBackend(runtime)` | DeprecationWarning | 移除 | 使用 `StateBackend()` |

---

## 7. 依赖版本

| 依赖 | 新版本/下限 | 说明 |
|------|-----------|------|
| `langchain` | >=1.2.15 | 依赖下限提升 |
| `langchain-core` | >=1.2.19 | 依赖下限提升 |
| `cryptography` | 46.0.6 | 安全修复 |
| `pygments` | 2.20.0 | 安全修复 (GHSA-5239-wwwm-4pmq) |

---

## 8. 迁移检查清单

### P1 必须（立即）

- [ ] `StateBackend` → `StateBackend()`（所有调用点）
- [ ] 测试文件中的 `StateBackend` 同步修复
- [ ] 如有 SubAgent 依赖"静默执行"，添加 `interrupt_on: {}`
- [ ] `pip install -e ".[dev]"` 验证依赖解析

### P2 推荐（本周）

- [ ] 自定义 middleware 的 `wrap_model_call` 返回类型检查
- [ ] 依赖求解验证（如严格锁定 `langchain-*` 版本）
- [ ] 完整回归测试

### P3 规划（v0.7 前）

- [ ] `WriteResult.files_update` 调用点排查
- [ ] 自定义 Backend 的 `ls_info()`/`glob_info()`/`grep_raw()` 返回类型迁移
- [ ] `SubAgentMiddleware(default_model=...)` → 新 API 迁移
- [ ] 自定义 Backend Factory 的 DeprecationWarning 处理（改为传入实例或抑制警告）

---

## 9. 已确认无影响项

以下特性对外部团队**无影响**（内部实现调整或未使用的功能）：

- `http_request` 工具移除（CLI 内部工具，SDK 不暴露）
- `_EXCLUDED_STATE_KEYS` 扩展（内部状态管理）
- `base_prompt.md` 删除（内容已合入 `filesystem.py`）
- Eval catalog 自动生成
- ACP 危险 shell 模式检测
- CI 工作流改进

---

**如有疑问，请联系 SDK 维护团队。**
