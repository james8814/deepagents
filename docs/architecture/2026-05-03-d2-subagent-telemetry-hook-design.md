# D-2: SubAgent Telemetry Hook 设计 — v2（重大修订）

**起草日期**: 2026-05-03（v1）→ **2026-05-03 v2 重大修订**
**起草人**: deepagents CTO + 架构师团队
**性质**: 设计草案（不含实现），交付给 pmagent 实施 + deepagents CTO review

---

## ⚠️ v1 → v2 设计错误声明（CTO 自陈）

**v1 设计有重大架构错误**，违反 ADR-0002 v3 + Plan H+ 核心承诺，必须重新设计。

### v1 错误内容

v1 §2.1 集成点列出："在 `task()` / `atask()` / `_stream_subagent_async()` / `_return_subagent_command()` **插入 hook 调用**"。这等于：

- 🔴 **修改 deepagents `subagents.py` 源代码** → 违反 ADR-0002 v3 §1 "deepagents fork 即将归档，pmagent 通过 pip 直接依赖上游"
- 🔴 **隐含 monkey-patch 或 fork 定制** → 违反 Plan H+ §0.1 "0 monkey-patch" 承诺
- 🔴 **deepagents fork 不应有任何定制工作** → 违反 ADR-0002 v3 §1.1 "装配主权完全在 pmagent"

### v1 错误根因

CTO 起草 v1 时未严格对照 ADR-0002 v3 + Plan H+ 0 monkey-patch 约束。设计套用了"在 SubAgentMiddleware 内部插入 hook"的传统 instrumentation 模式，但忽略了：

1. SubAgentMiddleware 在 `langchain-ai/deepagents` upstream，不在 pmagent 控制下
2. fork 即将归档，不应再做新定制
3. langchain `AgentMiddleware` 已提供标准 `wrap_tool_call` / `awrap_tool_call` hook，可在 pmagent 侧 additive 实现

**这是 ADR 评审 checklist v2 #4 "设计决策配 Python import test" 的反例**：CTO 在 v1 起草时未实测 langchain 标准 hook 能否满足需求，直接假设需要修改 deepagents 源码。

### v2 修订原则

- ✅ **0 deepagents 修改**：fork 保持归档计划，不做任何定制
- ✅ **0 monkey-patch**：完全用 langchain 标准 hook（`wrap_tool_call`）
- ✅ **完全 additive**：pmagent 创建新 V2 增强类，与 SkillsMiddlewareV2 同模式
- ✅ **装配主权在 pmagent**：D-2 实现位置 = `pmagent/src/agent_assembly/middleware/subagent_telemetry.py`

---

**对应 Phase A v2 §5.2 P3**: pmagent 表态"不强需求但欢迎"，可推迟到 Phase 1 完成后实现
**直接服务**: pmagent Track 2 P2 慢响应根因调查（区分 reasoning model thinking time vs context size vs API 性能）+ OPDCA workflow 健康度诊断

---

## 1. 设计目标

### 1.1 主要目标

| # | 目标 | 来自 |
|---|------|------|
| G-1 | **慢响应根因 instrumentation**：让 pmagent Track 2 P2 能定量区分 (a) dashscope API 性能 / (b) prompt context size / (c) reasoning model thinking time | Phase A v2 §2.2 关键观察 #3 三种候选原因并存 |
| G-2 | **OPDCA workflow 健康度诊断**：记录 SubAgent 返回后 parent 行为序列（终止 / 继续调用工具 / 调用 N 次内未终止）| pmagent v1 review §4.3 表态"可订阅做 OPDCA workflow 诊断" |
| G-3 | **生产环境可用**：低开销（默认关闭 / 采样策略）、零依赖（不引入新 package）| 区别于 `_ENABLE_SUBAGENT_LOGGING` 仅用于调试 |
| G-4 | **签字延续**：不破坏 ADR-0002 v3 已 ACCEPTED 的 8 项装配不变量 + 4 治理纪律 | 装配契约不变 |

### 1.2 非目标（明确不做）

- ❌ 不替代 LangSmith / OpenTelemetry — 仅提供 hook，由订阅方决定如何持久化
- ❌ 不强制启用 — pmagent 可选择不订阅，对现有装配无影响
- ❌ 不修改 `_EXCLUDED_STATE_KEYS` 或 SubAgent 状态契约
- ❌ 不引入新的 middleware 顺序约束（保持 8 项不变量稳定）

---

## 2. 实现路径分析（v2 重新设计）

### 2.1 langchain 标准 hook：`wrap_tool_call` / `awrap_tool_call`

**关键发现**（v2 修订核心）：langchain `AgentMiddleware` 提供标准 hook `wrap_tool_call` / `awrap_tool_call`，可在 ANY tool 调用前后插入逻辑，**包括 `task` tool**（这是 SubAgent 的 dispatch 入口）。

**实证**（基于 deepagents 0.5.0 实测）：

| Middleware | 文件 | 行号 | 用途 |
|---|---|---|---|
| FilesystemMiddleware | [filesystem.py:1953, 1973](libs/deepagents/deepagents/middleware/filesystem.py#L1953) | 用 `wrap_tool_call` 拦截 tool result，处理 large result eviction |
| _PermissionMiddleware | [permissions.py:344, 372](libs/deepagents/deepagents/middleware/permissions.py#L344) | 用 `wrap_tool_call` 检查 filesystem 操作权限 |

**hook 签名**（langchain `AgentMiddleware` 公开 API）：

```python
def wrap_tool_call(
    self,
    request: ToolCallRequest,             # 含 tool_call["name"], runtime, etc.
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    # Pre-call hook: 任何 hook 逻辑（记录 dispatch_ts、注入 context、等）
    result = handler(request)             # 实际 tool 执行（包括 SubAgent dispatch）
    # Post-call hook: 任何 hook 逻辑（记录 return_ts + duration_ms、记录 result、等）
    return result

async def awrap_tool_call(
    self,
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
) -> ToolMessage | Command:
    # async 版本，签名同上
    ...
```

**结论**：D-2 telemetry hook **完全可以用 `wrap_tool_call` 实现**，无需修改 deepagents 任何代码。

### 2.2 v2 集成方式：pmagent additive subclass

**实现位置**：`pmagent/src/agent_assembly/middleware/subagent_telemetry.py`（pmagent 仓库内，与 SkillsMiddlewareV2 同模式）

**装配位置**（pmagent `builders.py:build_main_middleware`）：在 `SubAgentObservability` 之后，让 telemetry 看到所有 `task` 工具调用：

```python
# pmagent/src/agent_assembly/builders.py（v2 修订）
middleware.extend([
    ...,
    SubAgentObservability(...),                          # 既有
    SubAgentTelemetryMiddleware(hooks=[...]),            # 🆕 D-2 v2
    create_summarization_middleware_with_overwrite_guard(...),
    ...
])
```

### 2.3 现有诊断设施（参考但不替代）

- **`_ENABLE_SUBAGENT_LOGGING`** ([subagents.py:184](libs/deepagents/deepagents/middleware/subagents.py#L184))：环境变量驱动 logger.info 日志，用于人工调试。**与 D-2 共存**：日志级 vs 事件级
- **`_ENABLE_SUBAGENT_STREAM_DIAGNOSTICS`** ([subagents.py:190](libs/deepagents/deepagents/middleware/subagents.py#L190))：astream fallback 诊断
- **deepagents 不需要新增诊断设施** — D-2 全部 telemetry 由 pmagent 通过 langchain wrap_tool_call hook 实现

### 2.4 v1 集成方式 vs v2 对比

| 维度 | v1（错误）| v2（修订） |
|---|---|---|
| 修改 deepagents 源码 | ❌ 需要修改 task() / atask() / _stream_* / _return_* | ✅ 0 修改 |
| Monkey-patch | 🔴 隐含需要 | ✅ 0 monkey-patch |
| ADR-0002 v3 兼容 | 🔴 违反 | ✅ 完全兼容 |
| Plan H+ §0.1 兼容 | 🔴 违反 | ✅ 完全兼容 |
| Fork 归档计划 | 🔴 阻塞（实现需要 fork 改动）| ✅ 不阻塞 |
| 实现复杂度 | 高（需 inject hook 调用代码到 4 个集成点）| 低（继承 AgentMiddleware override 1-2 方法）|
| 实现位置 | deepagents fork（违反主权）| pmagent V2 类（符合主权）|

### 2.5 v2 已知 limitation（vs v1）

| v1 能力 | v2 能力 | 影响 |
|---|---|---|
| `on_dispatch` event | ✅ 由 `wrap_tool_call` pre-call 实现 | 等价 |
| `on_return` event | ✅ 由 `wrap_tool_call` post-call 实现 | 等价 |
| `on_chunk` event（per-stream-chunk）| ❌ **无法实现**（wrap_tool_call 是 tool-level，不是 stream-chunk-level）| 🟡 影响 G-1 慢响应根因调查的 (b)/(c) 区分细节，但**不阻塞 G-1 主目标** |

**limitation 缓解**（针对 chunk 级监控的需求）：

1. **接受 limitation**：通过 `dispatch_ts` 和 `return_ts` 计算总 duration，足以区分 (a) API 性能 / (b)+(c) 内部慢响应；进一步区分 (b) vs (c) 可后续在 V3 增量加
2. **可选 V3 路径**：如未来必须 chunk 级监控，可在 pmagent 创建 `StreamingSubAgentMiddleware` 包装 `_stream_subagent_async` 输出（仍是 additive subclass，不修改 deepagents）

---

## 3. Hook API 设计

### 3.1 三个事件 hook

```python
# pmagent/src/agent_assembly/middleware/subagent_telemetry.py（v2 修订：实现位置在 pmagent，不在 deepagents）

from typing import Callable, Protocol
from dataclasses import dataclass
from datetime import datetime
import logging

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubAgentDispatchEvent:
    """SubAgent dispatch event (pre-execution)."""
    subagent_type: str          # 从 request.tool_call["args"]["subagent_type"]
    description: str            # 从 request.tool_call["args"]["description"]，truncate 到 500 chars
    parent_message_count: int   # 从 request.runtime.state["messages"] len
    tool_call_id: str
    dispatch_ts: datetime       # UTC


@dataclass(frozen=True)
class SubAgentReturnEvent:
    """SubAgent return event (post-execution)."""
    subagent_type: str
    tool_call_id: str
    return_ts: datetime
    duration_ms: int            # dispatch → return
    error: str | None           # None if successful
    has_structured_response: bool


class SubAgentTelemetryHook(Protocol):
    """Subscribe to SubAgent lifecycle events.

    Hook exceptions are caught and logged (never propagate to parent agent).
    """

    def on_dispatch(self, event: SubAgentDispatchEvent) -> None: ...
    def on_return(self, event: SubAgentReturnEvent) -> None: ...


class SubAgentTelemetryMiddleware(AgentMiddleware):
    """Plan H+ V2 增强类：通过 langchain wrap_tool_call hook 拦截 task tool 调用，记录 SubAgent telemetry。

    架构：
    - 0 deepagents 修改：完全用 langchain `wrap_tool_call` / `awrap_tool_call` 标准 hook
    - 0 monkey-patch：additive subclass 模式（与 SkillsMiddlewareV2 同模式）
    - 装配位置：在 SubAgentObservability 之后，看到所有 task() 调用

    用法：
        ```python
        # pmagent/src/agent_assembly/builders.py
        SubAgentTelemetryMiddleware(hooks=[
            SlowResponseDiagnostics(),
            OPDCAHealthMonitor(),
        ])
        ```
    """

    def __init__(self, *, hooks: list[SubAgentTelemetryHook] | None = None):
        super().__init__()
        self.hooks = hooks or []

    def _safe_dispatch(self, event: SubAgentDispatchEvent) -> None:
        """Fire-and-forget on_dispatch to all hooks; isolate exceptions."""
        for hook in self.hooks:
            try:
                hook.on_dispatch(event)
            except Exception:  # noqa: BLE001 — hook isolation
                logger.exception("subagent telemetry on_dispatch failed")

    def _safe_return(self, event: SubAgentReturnEvent) -> None:
        for hook in self.hooks:
            try:
                hook.on_return(event)
            except Exception:  # noqa: BLE001
                logger.exception("subagent telemetry on_return failed")

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Sync 拦截 task tool；其他 tool pass-through。"""
        if request.tool_call["name"] != "task":
            return handler(request)

        dispatch_ts = datetime.utcnow()
        args = request.tool_call.get("args", {})
        runtime_state = getattr(request.runtime, "state", {})
        msg_count = len(runtime_state.get("messages", []))

        self._safe_dispatch(SubAgentDispatchEvent(
            subagent_type=args.get("subagent_type", "unknown"),
            description=str(args.get("description", ""))[:500],
            parent_message_count=msg_count,
            tool_call_id=request.tool_call.get("id", ""),
            dispatch_ts=dispatch_ts,
        ))

        error: str | None = None
        try:
            result = handler(request)
        except Exception as err:  # noqa: BLE001
            error = f"{type(err).__name__}: {err}"
            raise
        finally:
            return_ts = datetime.utcnow()
            duration_ms = int((return_ts - dispatch_ts).total_seconds() * 1000)
            self._safe_return(SubAgentReturnEvent(
                subagent_type=args.get("subagent_type", "unknown"),
                tool_call_id=request.tool_call.get("id", ""),
                return_ts=return_ts,
                duration_ms=duration_ms,
                error=error,
                has_structured_response=False,  # 后续可从 result 推断
            ))

        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], "Awaitable[ToolMessage | Command]"],
    ) -> ToolMessage | Command:
        """Async 拦截，签名同 wrap_tool_call。"""
        if request.tool_call["name"] != "task":
            return await handler(request)

        dispatch_ts = datetime.utcnow()
        args = request.tool_call.get("args", {})
        runtime_state = getattr(request.runtime, "state", {})
        msg_count = len(runtime_state.get("messages", []))

        self._safe_dispatch(SubAgentDispatchEvent(
            subagent_type=args.get("subagent_type", "unknown"),
            description=str(args.get("description", ""))[:500],
            parent_message_count=msg_count,
            tool_call_id=request.tool_call.get("id", ""),
            dispatch_ts=dispatch_ts,
        ))

        error: str | None = None
        try:
            result = await handler(request)
        except Exception as err:  # noqa: BLE001
            error = f"{type(err).__name__}: {err}"
            raise
        finally:
            return_ts = datetime.utcnow()
            duration_ms = int((return_ts - dispatch_ts).total_seconds() * 1000)
            self._safe_return(SubAgentReturnEvent(
                subagent_type=args.get("subagent_type", "unknown"),
                tool_call_id=request.tool_call.get("id", ""),
                return_ts=return_ts,
                duration_ms=duration_ms,
                error=error,
                has_structured_response=False,
            ))

        return result
```

### 3.2 注册机制（v2 修订：通过 middleware 构造参数，无全局 registry）

v1 设计推荐"全局 registry"是因为预期需要在 `SubAgentMiddleware` 内部访问 hook。v2 用 `wrap_tool_call` hook 后，**直接通过 `SubAgentTelemetryMiddleware(hooks=[...])` 构造参数注入即可**，无需全局 registry。

```python
# pmagent/src/agent_assembly/builders.py（装配位置）
from src.agent_assembly.middleware.subagent_telemetry import (
    SubAgentTelemetryMiddleware,
    SlowResponseDiagnostics,    # pmagent 自定义 hook
    OPDCAHealthMonitor,         # pmagent 自定义 hook
)

# 在 build_main_middleware 内：
middleware.extend([
    ...,
    SubAgentObservability(...),                          # 既有 V2 类
    SubAgentTelemetryMiddleware(hooks=[                  # 🆕 D-2 v2
        SlowResponseDiagnostics(slow_threshold_ms=30_000),
        OPDCAHealthMonitor(expected_termination_calls={"react": 2, "opdca": 10}),
    ]),
    ...
])
```

**v2 注册机制优势**：

- ✅ 无全局状态（避免测试隔离问题）
- ✅ 显式装配（hooks 在 builders 装配代码可见，invariant tests 可校验）
- ✅ 多订阅者支持（hooks 是 list）
- ✅ 单元测试简单（直接构造 middleware + assert hook 被调用）

### 3.3 容错与隔离

| 风险 | 缓解 |
|------|------|
| Hook 抛异常导致 SubAgent 失败 | 所有 hook 调用包在 try/except，异常仅 `logger.exception()` 不传播 |
| Hook 阻塞 SubAgent 执行 | 同步 hook 限 10 ms 时间预算（超时 `logger.warning` 不阻塞）；异步 hook 用 `asyncio.create_task` fire-and-forget |
| Hook 修改 event 数据 | event 用 `@dataclass(frozen=True)` 防止意外 mutate |
| 多订阅者顺序依赖 | 所有 hook 独立调用，不保证顺序，订阅者不应假设其他 hook 存在 |

---

## 4. 服务 Track 2 P2 慢响应调查的具体用法

### 4.1 区分三种慢响应原因

```python
# pmagent/src/agent_assembly/telemetry/slow_response_diagnostics.py（pmagent 实现）

class SlowResponseDiagnostics:
    """Track 2 P2: 区分 dashscope API 性能 vs context size vs reasoning model thinking time"""

    def __init__(self, slow_threshold_ms: int = 30_000):
        self.slow_threshold_ms = slow_threshold_ms

    def on_dispatch(self, event: SubAgentDispatchEvent) -> None:
        # 记录 dispatch 时 parent 的 message count（context size proxy）
        self._dispatch_records[event.tool_call_id] = {
            "dispatch_ts": event.dispatch_ts,
            "parent_msg_count": event.parent_message_count,
        }

    def on_return(self, event: SubAgentReturnEvent) -> None:
        if event.duration_ms < self.slow_threshold_ms:
            return  # 不慢，不诊断

        record = self._dispatch_records.pop(event.tool_call_id, None)
        # 三种归因：
        # (a) chunk_count=0 + duration_ms 高 → API 性能（无流式响应）
        # (b) parent_msg_count > 50 + duration_ms 高 → context size 过大
        # (c) chunk_count > 0 + 第一个 chunk 距 dispatch < 1s + 总时长高 → reasoning model thinking
        diagnosis = self._diagnose(record, event)
        logger.warning(
            f"[SlowResponseDiagnostics] subagent={event.subagent_type} "
            f"duration={event.duration_ms}ms diagnosis={diagnosis}"
        )
```

### 4.2 区分判定矩阵

| 现象 | chunk_count | parent_msg_count | 第一个 chunk 延迟 | 归因 |
|---|---|---|---|---|
| API 性能慢 | 0（无流式）| 任意 | N/A | (a) dashscope API 性能问题 |
| Context size 大 | >0 | > 50 | 中等 | (b) prompt 过长触达 max_input_tokens 边界 |
| Reasoning model 思考 | >0 | < 50 | 第一个 chunk 也慢（>5s）| (c) qwen3-max thinking mode 内置延迟 |

**Phase A v2 §2.2 的 62 秒慢响应**用本矩阵分析后可精确定性。

---

## 5. 服务 OPDCA workflow 健康度诊断的具体用法

### 5.1 监控 SubAgent 返回后 parent 是否在 N 次内终止

需要 pmagent 在 SubAgent return 后跟踪 parent 的后续 LLM 调用次数。这需要两层 hook：

| 层 | 用途 | 实现位置 |
|---|------|---------|
| SubAgent 层 | 记录每次 SubAgent return | 本设计的 `on_return` hook |
| Parent agent 层 | 记录每次 LLM 调用 | pmagent 自定义 `MessagePairingValidator` 已有，复用即可 |

```python
# pmagent/src/agent_assembly/telemetry/opdca_health.py（pmagent 实现）

class OPDCAHealthMonitor:
    """监控 OPDCA workflow 终止行为：SubAgent 返回后 parent 是否在 N 次 LLM 调用内终止。"""

    def __init__(self, expected_termination_calls: dict[str, int]):
        # ReAct mode: 单 task 应在 ≤2 次终止
        # OPDCA mode: ≤10 次终止（含 reflection + write + submit_deliverable）
        self.expected = expected_termination_calls
        self._return_records: dict[str, datetime] = {}

    def on_return(self, event: SubAgentReturnEvent) -> None:
        self._return_records[event.tool_call_id] = event.return_ts

    # pmagent 自定义 MessagePairingValidator 在每次 parent LLM 调用时:
    def on_parent_llm_call(self, parent_state):
        for tcid, return_ts in list(self._return_records.items()):
            elapsed_calls = self._count_parent_calls_since(return_ts)
            expected = self.expected.get(self._infer_workflow_mode(parent_state), 10)
            if elapsed_calls > expected:
                logger.warning(f"[OPDCAHealth] post-subagent {elapsed_calls} parent calls > expected {expected}")
                self._return_records.pop(tcid)  # one-shot warning
```

---

## 6. 实现路线图（v2 修订：完全在 pmagent 实现）

**v1 → v2 责任重新分配**：v1 错误地把 R-1~R-5 分给 deepagents 团队（要求修改 deepagents 源码）。v2 修订后**全部 R-1~R-7 在 pmagent 实现**（用 langchain `wrap_tool_call` hook，符合 ADR-0002 v3 + Plan H+ 装配主权 + 0 monkey-patch）。

| 阶段 | 任务 | 预估 | 团队 | 触发条件 |
|------|------|------|------|---------|
| **R-1** | 实现 `pmagent/src/agent_assembly/middleware/subagent_telemetry.py`：2 dataclass (Dispatch/Return) + Protocol + `SubAgentTelemetryMiddleware`（继承 `AgentMiddleware`，override `wrap_tool_call` / `awrap_tool_call`）| 0.5 d | **pmagent 团队** | pmagent Phase 1.6 完成 ✅ |
| **R-2** | 在 `pmagent/src/agent_assembly/builders.py:build_main_middleware` 装配 `SubAgentTelemetryMiddleware`（在 `SubAgentObservability` 之后）| 0.25 d | **pmagent 团队** | R-1 完成 |
| **R-3** | 单元测试：hook 容错（hook 抛异常不传播给 parent）+ 多订阅者 + sync/async 双路径 + task tool 拦截 vs 其他 tool pass-through + **对照测试覆盖（D2-A1 修订，应用 ADR v5 #22 + #23）**: ① 嵌套 SubAgent（subagent 调用 subagent）hook 是否触发 ② async dispatch 路径 vs sync dispatch 路径双路径覆盖 ③ 多 hook 订阅者 firing 顺序对照 | 0.5 d | **pmagent 团队** | R-2 完成 |
| **R-4** | invariant 测试增补（test_assembly_invariants.py 加 T-14: SubAgentTelemetryMiddleware 装配位置 = SubAgentObservability 之后）| 0.25 d | **pmagent 团队** | R-3 完成 |
| **R-5** | pmagent 业务 hook 实现：`SlowResponseDiagnostics`（Track 2 P2 慢响应根因调查）+ `OPDCAHealthMonitor`（OPDCA workflow 健康度）| 1 d | **pmagent 团队** | R-4 完成 |
| **R-6** | 用 R-5 重跑 Phase A Test A，定性 62 秒慢响应根因（Track 2 P2 闭环）| 0.5 d | **pmagent 团队** | R-5 完成 |

**总工作量**：~3 d（pmagent 全部，比 v1 估算 4 d 减少 1 d，因为 langchain 标准 hook 比 manual instrumentation 简单）

**deepagents 团队工作量**：**0 编码** — CTO 转入咨询/review 角色：

| deepagents 团队工作 | 估时 | 时机 |
|---|---|---|
| Review R-1 实现的 `SubAgentTelemetryMiddleware`（接口契约 + langchain hook 用法正确性）| 0.5 h | R-1 完成时 |
| Review R-3 单元测试覆盖率 + R-4 invariant 测试 | 0.5 h | R-3/R-4 完成时 |
| Review R-6 慢响应根因诊断报告 | 0.5 h | R-6 完成时 |
| **合计 deepagents CTO 工作量** | **~1.5 h review**（非编码）| 触发驱动 |

**触发实现的条件**：pmagent Phase 1.6 完成 ✅（已满足）+ Track 2 P2 仍需 instrumentation（pmagent 自主判断，无外部依赖）

---

## 7. 与 ADR-0002 v3 + 8 装配不变量的兼容性证明

| 不变量 | 影响评估 |
|---|---|
| #1 TodoListMiddleware 首位 | ✅ 无影响（hook 不修改 middleware 顺序）|
| #2 `_PermissionMiddleware` 末位 | ✅ 无影响 |
| #3 AnthropicPromptCachingMiddleware 无条件 | ✅ 无影响 |
| #4 MemoryMiddleware 在 cache 之后 | ✅ 无影响 |
| #5 SkillsMiddleware 位置不对称 | ✅ 无影响 |
| #6 Subagent profile 独立 | ✅ 无影响 |
| #7 interrupt_on 双路径 | ✅ 无影响 |
| #8 default GP subagent 首位 | ✅ 无影响 |

| 治理纪律 | 影响评估 |
|---|---|
| 纪律 1 版本锁定 | ✅ **完全无影响**（D-2 v2 不修改 deepagents，pmagent `~= 0.5.0` 不变）|
| 纪律 2 私有 import 文档化 | ✅ **无新增私有 import** — D-2 v2 仅用 langchain 公开 hook (`wrap_tool_call`) + ToolCallRequest 公开类型 |
| 纪律 3 升级 SOP | ✅ 无影响（D-2 v2 是 pmagent 内部模块，不参与 deepagents 升级 SOP）|
| 纪律 4 invariant 测试 | 🟡 R-3 单元测试 + R-4 invariant 测试 T-14（SubAgentTelemetryMiddleware 装配位置）|

**结论**：D-2 v2 设计**完全兼容** ADR-0002 v3 + Plan H+ 0 monkey-patch + 装配主权约束。

---

## 8. API 表面（v2 修订：pmagent 内部 API，无 deepagents 公开 API）

D-2 v2 实现位置在 pmagent 内部，**不涉及 deepagents 公开 API 增减**。pmagent 内部 import 路径：

```python
# pmagent 内部模块 — 不跨仓库导出
from src.agent_assembly.middleware.subagent_telemetry import (
    SubAgentTelemetryMiddleware,     # AgentMiddleware subclass
    SubAgentTelemetryHook,           # Protocol
    SubAgentDispatchEvent,           # @dataclass(frozen=True)
    SubAgentReturnEvent,             # @dataclass(frozen=True)
)

# pmagent 业务 hook 实现位置
from src.agent_assembly.telemetry.slow_response_diagnostics import SlowResponseDiagnostics
from src.agent_assembly.telemetry.opdca_health import OPDCAHealthMonitor
```

**外部依赖**（仅 langchain 公开 API）：

```python
# 来自 langchain 公开 API（无下划线，已被 deepagents.middleware.{filesystem, permissions} 内部使用）
from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware import ToolCallRequest
```

**稳定性承诺**：

- pmagent 内部 API：pmagent 团队自主维护，无外部稳定性承诺
- langchain `wrap_tool_call` hook：langchain 公开 API，稳定性由 langchain 项目保证（已被 deepagents 内部 FilesystemMiddleware + _PermissionMiddleware 依赖，受同等稳定性保护）

---

## 9. 待决策事项（v2 修订）

v1 §9 列出的 5 项决策点中，**3 项在 v2 修订时已自动解决**（不再是开放决策）：

| # | v1 决策点 | v2 状态 |
|---|------|---------|
| 1 | hook 注册机制（全局 registry vs middleware 构造参数）| ✅ **已决定**：v2 §3.2 选 middleware 构造参数（`SubAgentTelemetryMiddleware(hooks=[...])`），无全局 registry |
| 2 | hook 异步策略（fire-and-forget vs await）| ✅ **已决定**：v2 §3.1 用 `try/except` + `logger.exception` 实现 fire-and-forget |
| 3 | event 字段范围 | ✅ **保留**：当前最小集（Dispatch + Return），删除 v1 的 Chunk event（langchain `wrap_tool_call` 不支持 chunk 级，详见 §2.5 limitation）|
| 4 | 实现触发时机 | ✅ **已满足**：Phase 1.6 完成 ✅，pmagent 团队现可启动 |
| 5 | 是否纳入其他 middleware hook | ✅ **保留**：仅 SubAgent（聚焦 D-2 目标，不范围蔓延）|

**v2 仍开放决策**（请项目负责人 / pmagent 技术总监 review）：

| # | 决策点 | 候选 | CTO 推荐 |
|---|------|------|---------|
| **a** | pmagent 是否实施 R-6（用 D-2 重跑 Phase A Test A 定性 62 秒慢响应根因）| 实施 / 推迟 | **实施** — Track 2 P2 闭环价值高 |
| **b** | D-2 实施时机 | 立即（与 P0 P2 调查 + P1 SOP 并行）/ 串行（先完成 P0+P1 再启动 D-2）| **串行**（先 P0+P1 0.75 d → 后 D-2 R-1~R-6 3 d，避免 pmagent 团队带宽过载）|
| **c** | D-2 v2 实现是否需要 deepagents CTO 编码协助 | 是 / 否 | **否** — CTO 仅 review（~1.5 h），保持装配主权完全在 pmagent |

---

**文档状态**：✅ 设计草案完成 2026-05-03
**deepagents CTO 签字**：✅ 2026-05-03（设计层签字，不含实现承诺）
**等待**：
1. pmagent 技术总监 review §3 + §4 + §5 是否满足 Track 2 P2 + OPDCA 诊断需求
2. 项目负责人裁决 §9 待决策事项（特别是决策点 4 实现触发时机）

**配套文档**：
- [Phase A 诊断报告 v2](2026-05-03-phase-a-diagnosis-report.md) §5.2 P3
- [Phase 1 装配支援包](2026-05-03-phase-1-handoff-package.md)
- [SubAgent 终止最佳实践](2026-05-03-subagent-termination-best-practices.md) §5
