# SubAgent 终止最佳实践 + OPDCA-style Workflow 预期行为

**起草日期**: 2026-05-03
**起草人**: deepagents CTO
**目标**: 为 Track 2 P0 核查（pmagent 90s post-Stage 9 行为定性）提供参考框架；同时作为长期文档供 deepagents 用户参考
**对应 Phase A v2 §5.2 P3**: pmagent 表态"建议加"

---

## 1. 背景

deepagents `SubAgentMiddleware` 提供 `task` 工具，允许主 agent 调用 SubAgent 完成隔离任务。SubAgent 完成后通过 `_return_subagent_command()` ([subagents.py:333-361](libs/deepagents/deepagents/middleware/subagents.py#L333-L361)) 返回 `ToolMessage` 给主 agent。

**主 agent 接收 ToolMessage 后是否终止**完全取决于：

1. 主 agent 的 system prompt 设计（是否明确终止条件）
2. 主 agent 是否还有未完成的 OPDCA workflow 阶段（如 reflection、HIL 提交）
3. LLM 模型对"任务完成"的判断（受 prompt + 历史 + 工具描述影响）

deepagents SDK **本身不强制终止**——主 agent 在收到 ToolMessage 后可以继续生成 `tool_calls`、调用其他工具、或生成 final `AIMessage`。这是设计意图，符合 ReAct + 多阶段 workflow 的灵活性需求。

---

## 2. 两种典型 workflow 终止模式

### 2.1 Mode A: ReAct 单 task 终止（简单模式）

**场景**：主 agent 收到一个用户问题，调用一次 SubAgent 完成研究，立即生成 final 答复。

**预期工具序列**：

```
User → Main Agent
  ↓ task(subagent_type="researcher", description="研究 X")
  ↓
Main Agent ← ToolMessage(researcher 结果)
  ↓
Main Agent → final AIMessage（终止）
```

**预期 LLM 调用次数**：≤ 2 次（task 调用 + final 答复）

**适用场景**：
- 简单问答助手
- 单次研究 + 总结
- ReAct 模式的标准实现

**测试断言**：

```python
def test_react_single_task_termination():
    result = await agent.ainvoke({"messages": [HumanMessage("研究 Scrum")]})
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert len(ai_messages) <= 2
    assert ai_messages[-1].tool_calls == []  # 最后一条 AIMessage 无 tool_calls
```

### 2.2 Mode B: OPDCA-style 多 stage workflow（复杂模式）

**场景**：主 agent 采用 Observe → Plan → Do → Check → Act 工作流，SubAgent 完成 Do 阶段后还有 Check + Act 阶段。

**预期工具序列**：

```
User → Main Agent (Observe + Plan)
  ↓ task(subagent_type="researcher")     ← Do 阶段
  ↓
Main Agent ← ToolMessage(研究报告)
  ↓ task(subagent_type="reflection")    ← Check 阶段（评估质量）
  ↓
Main Agent ← ToolMessage(reflection 结果)
  ↓ write_file(报告保存)                 ← Act 阶段开始
  ↓ submit_deliverable(...)              ← Act 阶段（HIL 触发）
  ↓
[HIL interrupt → 用户审批]
  ↓
Main Agent → final AIMessage（终止）
```

**预期 LLM 调用次数**：5-10 次（视 OPDCA 工具数量）

**适用场景**：
- 研究报告生成（pmagent Deep Research 模式）
- 内容创作 + review + 发布
- 任何需要 self-reflection 或 HIL 审批的工作流

**测试断言**：

```python
def test_opdca_workflow_termination():
    result = await agent.ainvoke({"messages": [HumanMessage(...)]})
    tool_call_sequence = extract_tool_call_sequence(result["messages"])

    # 断言 OPDCA 预期工具序列
    assert "task:researcher" in tool_call_sequence  # Do
    assert "task:reflection" in tool_call_sequence  # Check
    assert "submit_deliverable" in tool_call_sequence  # Act

    # 断言最后是 final AIMessage 或 HIL interrupt
    last_msg = result["messages"][-1]
    assert (isinstance(last_msg, AIMessage) and not last_msg.tool_calls) \
        or "interrupt" in result.get("__interrupt__", [])
```

---

## 3. 终止条件 prompt checklist

主 agent system prompt 应包含以下终止条件之一：

### 3.1 ReAct 单 task 模式（简单）

```text
## 终止条件
当 SubAgent 完成研究并返回结果后，立即生成 final AIMessage 总结答复用户。
不要重复调用同一个 SubAgent，不要调用其他工具。
```

### 3.2 OPDCA-style 多 stage 模式（复杂）

```text
## 工作流：OPDCA
1. **Observe**: 理解用户需求
2. **Plan**: 制定研究计划
3. **Do**: 调用 task(subagent_type="researcher")
4. **Check**: 调用 task(subagent_type="reflection") 评估研究质量
5. **Act**: 调用 write_file 保存报告 + submit_deliverable 触发 HIL

## 终止条件
- 完成 Act 阶段（submit_deliverable 调用）后，进入 HIL 等待
- HIL 返回后，生成 final AIMessage 总结
- 任何阶段如出现致命错误，立即生成 final AIMessage 报告失败原因
- **禁止**在 Act 阶段完成后继续调用任何工具（除非用户在 HIL 后明确要求）
```

### 3.3 反模式（导致 Track 2 调查中怀疑的"未终止 loop"）

```text
❌ 不要这样写 prompt：

"研究完成后，请进行更深入的反思和分析以确保质量。"
（→ 模型可能反复调用 reflection_agent，进入循环）

"如果有任何遗漏或不清楚的地方，请继续调用工具补充。"
（→ 模型可能无限制地"补充"，永不终止）

"在生成最终答复之前，请尽可能使用所有可用工具收集信息。"
（→ 模型可能枚举所有工具，进入耗尽式探索）
```

---

## 4. 90 秒 post-stage 9 行为定性框架（Track 2 P0 核查参考）

基于 Phase A v2 §3.1 提供的二选一定性表，pmagent 团队 P0 核查时按以下框架判断：

### 4.1 定性 (A): by design

**判定条件**（**全部满足**）：

- ✅ 主 prompt 明确包含 OPDCA workflow（如 §3.2 模板）
- ✅ 90s 内 6 次 LLM 调用对应的工具**全部**符合 OPDCA 预期序列
- ✅ 调用顺序：reflection → write_file → submit_deliverable（含子项扩展）
- ✅ 最终预期是 HIL interrupt 或 final AIMessage

**后续动作**：

- 关闭 Track 2 修复任务
- 转入 §5.2 文档化"OPDCA workflow 预期行为"（本文档已提供模板）
- pmagent 添加 OPDCA-aware 测试断言（H-3 风格）

### 4.2 定性 (B): unintended loop

**判定条件**（**任一满足**）：

- 🔴 主 prompt 缺少明确终止条件
- 🔴 调用工具序列**不**符合 OPDCA 预期（如 reflection 被调用 3 次以上）
- 🔴 工具调用包含未在 prompt 中声明的工具
- 🔴 同一工具用相同参数被重复调用

**后续动作**：

- 启动 §5.1 P0-2 + P1-1 修复
- 修订主 prompt（参考 §3.2、§3.3 模板）
- 检查 reflection_agent profile.yaml 的 auto-trigger 条件

---

## 5. 监控 + Telemetry（可选）

如 pmagent 后续希望在生产环境监控终止行为，可订阅 deepagents §5.2 P3 的 SubAgentMiddleware telemetry hook（待实现）：

```python
# 计划中的 hook（pmagent 表态可推迟到 Phase 1 完成后）
@subagent_middleware.on_subagent_return
def track_termination_behavior(parent_state, subagent_result):
    # 记录 SubAgent 返回后 parent 在 N 次内是否终止
    # 用于 OPDCA workflow 健康度诊断
    ...
```

**短期替代方案**（pmagent 可现在就实现）：

- 在 `MessagePairingValidator` 中统计 post-SubAgent 的 LLM 调用次数
- 超过阈值（如 10 次）时打 WARNING log
- 阈值可配置：ReAct 模式 = 2、OPDCA 模式 = 10

---

## 6. 总结：deepagents 框架视角的 SubAgent 终止职责矩阵

| 层 | 责任 | 实现 |
|---|------|------|
| **deepagents SDK** | ✅ 提供 `task` 工具 + `_return_subagent_command()` 正确返回 ToolMessage | 已实现，[subagents.py:333-361](libs/deepagents/deepagents/middleware/subagents.py#L333-L361) |
| **deepagents SDK** | ⚪ **不负责**强制终止逻辑 | 这是 agent 设计自由度 |
| **应用层（如 pmagent）** | 🟢 通过 prompt 设计明确终止条件 | 参考 §3.1 / §3.2 模板 |
| **应用层（如 pmagent）** | 🟢 通过 OPDCA-aware 测试断言验证终止行为 | 参考 §2 测试断言 |
| **应用层（如 pmagent）** | 🟡 监控 + 告警生产环境的异常终止 | 参考 §5 |
| **LLM 模型** | ⚪ 实际决策"是否调用工具/终止" | 受 prompt + history 影响，应用层不可强制 |

---

**文档状态**：✅ 起草完成 2026-05-03
**deepagents CTO 签字**：✅ 2026-05-03
**用途**：
1. Phase A Track 2 P0 核查参考框架（短期）
2. deepagents 长期文档库的"SubAgent 终止最佳实践"指南（长期）

**配套文档**：[`2026-05-03-phase-1-handoff-package.md`](2026-05-03-phase-1-handoff-package.md)（H-1 + H-2 + H-3 装配支援）
