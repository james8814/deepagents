总评：技术主管的二分诊断框架完全正确，C 路径排除的质疑也成立
通过对实际安装的 LangChain/LangGraph 包源码的精确验证，我们现在可以把几个关键问题从"推断"变成"事实"。

一、对技术主管各点的精确回应（带源码证据）
1. C 路径排除的质疑：成立，但可以加强
技术主管说"576 SSE 事件不足以证明 task() 没崩"——这是正确的质疑。但现在有了更强的论据：

LangGraph 的异常处理机制：如果 atask() 内发生未捕获的 AttributeError，该异常会在 LangGraph 节点执行时抛出。LangGraph 会将其作为节点执行失败处理，通常导致：

运行状态变为 ERROR
后续节点不再执行
SSE 流会出现明显的异常事件或提前终止
"有 576 个正常 SSE 事件且主图继续运行"与"task 工具节点因未捕获异常崩溃"的模式不一致——但技术主管说得对，这仍然不是充分证据，必须用日志闭环。

2. "不带 stream_mode 的 astream 退化"：质疑完全正确，还有更深的问题
技术主管指出"chunk 格式不保证是 state dict"——这被源码验证为精确的：

CompiledStateGraph.astream() 的实际签名（langgraph/pregel/main.py:2709）：


async def astream(
    self,
    input: InputT | Command | None,
    config: RunnableConfig | None = None,
    *,
    stream_mode: StreamMode | Sequence[StreamMode] | None = None,
    **kwargs: Unpack[DeprecatedKwargs],  # DeprecatedKwargs 是空 TypedDict
) -> AsyncIterator[dict[str, Any] | Any]
关键：stream_mode=None 时默认值在 Pregel.__init__:630 中被设为 "values"，所以不带参数的 astream 实际上等价于 stream_mode="values"，输出依然是 state dict——对于 CompiledStateGraph 这种情况退化是安全的。

但对于非 LangGraph Runnable，情况完全不同：

Runnable 类型	astream(state, stream_mode="values") 行为	chunk 格式
CompiledStateGraph	正常，显式接受 stream_mode	完整 state dict（含 messages）
RunnableLambda(lambda)	kwargs 透传给 lambda → TypeError	N/A（被 except 捕获）
有 **kwargs 的自定义 Runnable	静默接受 stream_mode，透传给底层	任意格式，不保证是 state dict
无 astream 的对象	AttributeError	N/A（不被 except 捕获，崩溃）
发现了一个之前分析遗漏的第三条静默失败路径 D：


D：runnable 的 astream 有 **kwargs，静默接受 stream_mode="values"
   → 不抛 TypeError，不触发 fallback
   → 循环确实执行，stream_writer 确实被调用
   → 但 chunk 不是 state dict，chunk.get("messages", []) 返回 []
   → 发出的 custom 事件内容为空（message_count=0，无 step_type）
   → 客户端即使订阅了 "custom" 也看不到有意义的进度信息
   → 外部团队可能把"有 custom 事件但内容为空"误报为"0 custom 事件"
二、精确化后的完整诊断树（委员会终版）

0 custom events（外部团队观测）
│
├── C：task() 因 AttributeError 崩溃（runnable 无 astream 方法）
│   → 未被 except TypeError 捕获，向上冒泡
│   → LangGraph 节点进入 ERROR 状态，主图应当异常终止
│   → 与"576 SSE 正常事件"模式不符，大概率可排除
│   → 确认方式：服务端日志有无 AttributeError traceback
│
├── A：TypeError fallback 触发，stream_writer 从未被调用
│   → subagent.astream() 调用的 runnable 是类 RunnableLambda
│   → lambda 不接受 stream_mode → TypeError: unexpected keyword argument
│   → 被 except TypeError 捕获 → ainvoke() 代替 → stream_writer 循环体从不执行
│   → 确认方式：fallback WARNING 日志出现 / chunk_count=0
│
├── B：stream_writer 被调用，客户端未收到
│   ├── B1：前端 streamMode 未包含 "custom"
│   └── B2：订阅了 "custom" 但消费逻辑丢弃
│   → 确认方式：stream_writer 计数 > 0 但客户端仍 0 custom
│
└── D（新增）：stream_writer 被调用，但 custom 事件内容为空
    → runnable 的 astream 有 **kwargs，静默接受 stream_mode
    → 但 chunk 不是 state dict，_extract_stream_progress 返回空壳
    → 外部团队可能把"内容为空的 custom 事件"误报为"0 custom 事件"
    → 确认方式：stream_writer 计数 > 0 且 custom 事件存在但 message_count=0
三、对两条并行线的具体落地方案
线 1：证据闭环（最小埋点，一次解决 C/A/B/D 全部）

# atask() 修改版（加入完整诊断埋点）
result = None
chunk_count = 0
stream_writer_count = 0
try:
    async for chunk in subagent.astream(subagent_state, stream_mode="values"):
        chunk_count += 1
        result = chunk
        progress = _extract_stream_progress(chunk, subagent_type)
        runtime.stream_writer(progress)
        stream_writer_count += 1
except (TypeError, AttributeError) as err:
    is_streaming_issue = (
        isinstance(err, AttributeError) and any(m in str(err) for m in ["astream", "stream"])
    ) or (
        isinstance(err, TypeError) and any(m in str(err) for m in ["stream_mode", "unexpected keyword argument"])
    )
    if is_streaming_issue:
        result = None
        logger.warning(
            "[DIAG] fallback triggered: %s: %s | subagent=%s | runnable_type=%s",
            type(err).__name__, err, subagent_type, type(subagent).__name__
        )
    else:
        raise
finally:
    logger.debug(
        "[DIAG] atask complete | subagent=%s | chunk_count=%d | stream_writer_count=%d",
        subagent_type, chunk_count, stream_writer_count
    )
if result is None:
    result = await subagent.ainvoke(subagent_state)
return _return_command_with_state_update(result, runtime.tool_call_id)
诊断判定矩阵：

日志观测	根因	修复责任方
AttributeError fallback + 0 chunk	C 路径	框架侧：扩展异常捕获
TypeError fallback + 0 chunk	A 路径	runnable 契约问题或框架兼容
chunk_count>0 + stream_writer_count>0 + 客户端0 custom	B 路径	前端订阅/消费
chunk_count>0 + stream_writer_count>0 + custom 事件 message_count=0	D 路径	runnable 类型不符合契约
线 2：框架工程改进（独立立项，不等外部闭环）
改进 1：扩展异常捕获（精确，不粗暴吞异常）


# 当前（有盲点）
except TypeError as err:
    if "stream_mode" in str(err) or "unexpected keyword argument" in str(err):

# 建议（覆盖 AttributeError 的 streaming 方法缺失情况）
except (TypeError, AttributeError) as err:
    is_streaming_unsupported = (
        isinstance(err, AttributeError)
        and any(m in str(err) for m in ["astream", "stream", "has no attribute"])
    ) or (
        isinstance(err, TypeError)
        and any(m in str(err) for m in ["stream_mode", "unexpected keyword argument"])
    )
    if is_streaming_unsupported:
        result = None
        runtime.stream_writer({
            "type": "subagent_streaming_unsupported",
            "subagent_type": subagent_type,
            "runnable_type": type(subagent).__name__,
            "reason": f"{type(err).__name__}: {err}",
        })
        logger.warning("[subagents] streaming unsupported, falling back to invoke: %s", err)
    else:
        raise
改进 2：chunk 类型守卫（防 D 路径的静默空事件）


def _extract_stream_progress(chunk: dict[str, Any], subagent_type: str) -> dict[str, Any]:
    # 新增：验证 chunk 是否为 state dict 格式
    if not isinstance(chunk, dict):
        return {
            "type": "subagent_progress",
            "subagent_type": subagent_type,
            "step_type": "unknown_chunk_format",
            "chunk_type": type(chunk).__name__,
        }
    # 原有逻辑...
改进 3：CompiledSubAgent 契约文档（明确 streaming 要求）

在 CompiledSubAgent TypedDict 的 runnable 字段 docstring（当前 subagents.py:L112-L117）中添加：


runnable: Runnable
"""A custom agent implementation.

For real-time progress streaming via subagent_progress events, the runnable
MUST support `astream(input, stream_mode="values")` and yield state dicts
containing a 'messages' key. LangGraph CompiledStateGraph satisfies this
contract. Plain LangChain Runnables (e.g., RunnableLambda) do not and
will fall back to blocking invocation without progress events.
"""
改进 4：测试补齐（三类 runnable 全覆盖）


# 需要新增的测试用例
def test_streaming_with_compiled_state_graph():
    """stream_writer should be called with non-empty progress"""

def test_streaming_fallback_with_runnable_lambda():
    """TypeError fallback should trigger, stream_writer never called"""

def test_streaming_fallback_with_attribute_error():
    """AttributeError (no astream) should be caught, not crash"""

def test_streaming_empty_chunks_from_non_state_runnable():
    """D路径：runnable 接受 stream_mode 但 chunk 不是 state dict"""
四、最终结论对齐
判断点	内部研发	技术主管	一致性
外部团队根因错误	✅	✅	一致
C 路径"可排除"需更严谨	补充同意	✅ 质疑成立	一致
A/B 诊断树保留	✅	✅	一致
异常捕获是独立框架缺陷	✅	✅	一致
退化 astream 需类型守卫	新增 D 路径	✅ 方向同意	一致并补强
不签字定论"一定是前端"	✅	✅	一致
两条线并行推进	✅	✅	一致
新增贡献：D 路径（runnable 静默接受 stream_mode 但 chunk 不是 state dict）是之前所有分析均未覆盖的静默失败模式。组合埋点方案（chunk_count + stream_writer_count + fallback WARNING）可一次性把 C/A/B/D 四条路径全部闭环，无需多轮往返。
