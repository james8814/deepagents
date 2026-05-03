# Phase A 异步问题诊断报告 — deepagents CTO 起草

**报告日期**: 2026-05-03
**起草人**: deepagents CTO + 架构师团队
**版本**: **v2**（吸收 pmagent 技术总监 review 的 4 处 amendments）
**v1 → v2 变更**:
- Gap 1: §3.1 + §5.1 引入 OPDCA workflow 视角，区分 "design intent" vs "unintended loop"
- Gap 2: §3.1 用 "OPDCA workflow 触发" 替换 "多 SubAgent 编排" 表述
- Gap 3: §2.2 + §5.1 P2 慢响应归因升级为 "根因调查 + 监控"（含 context size / reasoning model 排查）
- Gap 4: §5.1 P0-1 估时调整为 0.25-0.5 d（视 prompt 现状），加 system_prompt_v1.md 读取步骤
- §5.1 P0-2 改为条件执行（取决于 P0-1 判定）

**输入**: pmagent 团队 A.1 交付物（PHASE_A_DIAGNOSIS_REPORT.md + 4 个日志文件 + thread state dump）+ pmagent 技术总监 v1 review（OPDCA workflow 视角补充）
**ADR 关联**: ADR-0002 §9.5 sequencing — Phase A 结论作为 Phase 1.5 业务适配输入
**会签状态**: 🟢 **ACCEPTED** — 三方签字完成 2026-05-03
- deepagents CTO: ✅ 起草 v2 完成（2026-05-03）
- pmagent 技术总监: ✅ APPROVE WITH TECHNICAL NOTES（2026-05-03，4 项 D-1~D-4 深度技术 review notes 归档为 P0 working notes 见 `pmagent/docs/bug_fixes/PHASE_A_P0_WORKING_NOTES.md`）
- 项目负责人: ✅ **批准**（2026-05-03，回复"批准"）

**外部视角声明**（CTO 自陈）: 本报告由 deepagents 仓库视角起草，**未直接读取 pmagent 业务侧 prompts/workflow 配置**（如 `system_prompt_v1.md`、`reflection_agent profile.yaml`）。OPDCA workflow 设计意图由 pmagent 技术总监提供。这是 deepagents 团队对 pmagent 业务层的合理盲区，pmagent 团队在 §5.1 P0 阶段的核查具备最终判断权。

---

## 1. 执行摘要

| 项 | 结论 |
|---|---|
| **原始 BadRequestError bug** | ✅ **已不复现**（2026-05-03 当前环境 0/0 出现）|
| **Post-Stage 9 90s 行为性质** | ⚠️ **待 P0 核查后定性**：可能是 OPDCA workflow by design (A) 或 unintended loop (B)；不是框架死锁，是 agent 行为 |
| **归属判定** | 🟢 **pmagent 应用层**（OPDCA workflow / prompt / subagent 配置）|
| **deepagents SDK 责任** | ⚪ **无修复责任**（装配层 0 错误、SubAgentMiddleware 返回正常）|
| **LangGraph 上游责任** | ⚪ **无修复责任**（9/9 stages dispatch 成功、recursion_limit 未触发）|
| **Phase 1.5 业务适配影响** | 🟢 **无阻塞**（Phase A 结论不影响装配实施路径）|

---

## 2. 关键证据链

### 2.1 Test A 完整 stage 转换（research_agent SubAgent 完整跑通）

```
00:36:29 启动（recursion_limit=1000）
   ↓
Stage 1: GOAL_SETTING → 2: PLANNING → 3: DATA_COLLECTION → 4: SOURCE_VALIDATION
   → 5: DATA_ANALYSIS → 6: INSIGHT_EXTRACTION → 7: REPORT_WRITING
   → 8: REVIEW (score=9.2/10, passed=True) → 9: PUBLISH (00:42:44)
   ↓
00:42:44.366 Deep research completed. Report written to /workspace/reports/...
   ↓
[Parent agent post-Stage 9 reasoning loop, 90 sec, NOT stuck — actively LLM-calling]
   ↓
00:44:14 Test 强制中断（8.5 min ainvoke timeout）
```

**结论**：
- research_agent SubAgent 完整跑完 9/9 stages
- Stage 9 PUBLISH 后，**parent agent 接收 ToolMessage 后未终止**，进入持续推理循环
- 8.5 min 内 parent 共发起 **6 次 LLM 调用**（00:42:44 → 00:44:14），每次都生成带 tool_calls 的 AIMessage

### 2.2 Post-Stage 9 90-秒 时间线

| 时间 | 事件 | Message 数 | LLM 耗时 |
|------|------|-----------|---------|
| 00:42:44.366 | research_agent 返回 | — | — |
| 00:42:44.512 | Parent LLM 调用 #1 | 14 | 0.15 s |
| 00:42:50.081 | Parent LLM 调用 #2 | 16 | 5.6 s |
| 00:42:52.213 | Parent LLM 调用 #3 | 18 | 2.1 s |
| 00:42:53.950 | Parent LLM 调用 #4 | 20 | 1.7 s |
| **00:42:53 → 00:43:55** | **62 秒 LLM 单次调用**（dashscope 慢响应）| — | **62 s** |
| 00:43:55.753 | Parent LLM 调用 #5 | 22 | — |
| 00:44:02.408 | MessagePairingValidator: 1 AI tool_calls (**0 SubAgent**) | 3 | 6.6 s |
| 00:44:08.498 | MessagePairingValidator: 2 AI tool_calls (**0 SubAgent**) | 5 | 6.1 s |
| 00:44:09.976 | MessagePairingValidator: 3 AI tool_calls (**0 SubAgent**) | 7 | 1.5 s |
| 00:44:14.613 | LLM 调用 0/1（新 context）| 1 | 4.6 s |

**关键观察**：

1. **每次 LLM 调用都返回 `AIMessage(tool_calls=[...])`**，agent 持续在调用工具，不在生成 final 答复
2. **MessagePairingValidator: "0 SubAgent"**：parent **未递归调用** `task` 工具，在调用其他常规工具（filesystem / search / reflection 等）
3. **62 秒单次 LLM 调用 — 根因待定**（吸收 pmagent v1 review Gap 3）：
   - **当前证据不足以归因**到单一原因
   - 三种候选原因并存，需 §5.1 P2 阶段交叉验证后定性：
     - (a) dashscope API 性能问题（外部依赖）
     - (b) Prompt context size 过大（>100k tokens 触达 max_input_tokens 边界）
     - (c) Reasoning model（如 qwen3-max thinking mode）的内置推理延迟
   - **不再武断归因为外部 API**
4. **Message 数 22 → 3 跳变**：可能是 SummarizationMiddleware 触发（85% context 阈值）或新 context 切入

### 2.3 ChatQwen 消息格式诊断

**17 次调用全部 0/N（0 转换需要）** → ChatQwen 适配类工作正常 → 消息格式无问题。

之前 v3 评审记录的 "ChatQwen Adapter list → JSON string 转换 bug" **已修复**。

### 2.4 51 次 400 错误归因

| 来源 | 次数 | 性质 | 归属 |
|------|------|------|------|
| Serper API (`google.serper.dev`) | 69 | 外部搜索 API 失败 | ⚪ 外部依赖 |
| arxiv API (`export.arxiv.org`) | 15 | 外部学术 API 限流 | ⚪ 外部依赖 |
| LangGraph/LLM API BadRequestError | **0** | — | — |

**结论**：51 次 400 错误**全部来自外部 API**，与框架无关。

---

## 3. 根因定位（三种归属候选评估）

### 3.1 候选 ① pmagent 应用层（OPDCA workflow / prompt 设计）

| 证据 | 支持度 |
|------|--------|
| Stage 9 PUBLISH 完成后 parent 不终止，持续生成 tool_calls | 🟢 **强支持** |
| MessagePairingValidator "0 SubAgent" → parent 调用的不是 task | 🟢 **强支持** |
| 90s 内 6 次 LLM 调用、message 数 14→22→3（疑似 summarization）| 🟢 **强支持** |
| 0 框架错误、0 配对失败、0 BadRequestError | 🟢 **强支持** |
| Test B (HTTP API 简单对话) 5.93s 正常完成 | 🟢 **强支持**（说明问题**特定于 OPDCA workflow Do/Check/Act 流程的触发**，而非简单对话路径）|

**判定**：🟢 **HIGH CONFIDENCE — pmagent 应用层归属**（"应用层"涵盖 OPDCA workflow design + prompt + subagent profile 配置）

**关键澄清（吸收 pmagent v1 review Gap 1）**：

> pmagent 主 agent 采用 **OPDCA 工作流**：Observe → Plan → **Do**（SubAgent 执行）→ **Check**（reflection_agent 评估）→ **Act**（submit_deliverable + HIL）。
>
> 研究完成（Stage 9 PUBLISH）后，主 agent 进入 Check + Act 阶段是**设计意图**，会调用 `reflection_agent`、`write_file`（保存最终产物）、`submit_deliverable`（HIL 触发）等工具链。
>
> **因此 90s 行为存在两种可能性，必须由 pmagent 团队 P0 阶段核查后才能定性**：
>
> | 可能性 | 性质 | 后续动作 |
> |---|---|---|
> | (A) 90s 行为符合 OPDCA Check/Act 预期工具序列 | 🟢 **by design**（非 bug）| 关闭 §5.1 P0-1，转为 §5.2 文档化"OPDCA workflow 预期行为" |
> | (B) 90s 行为不符合 OPDCA 预期序列（如 reflection_agent 递归触发、prompt 缺终止条件、有未预期的 post-research 自动触发链）| 🔴 **unintended loop**（修复目标）| 启动 §5.1 P0-2 + P1-1 调查与修复 |

**具体核查方向**（pmagent 团队 §5.1 P0 阶段，按顺序）：

1. **读 [pmagent/prompts/system_prompt_v1.md](系统提示词)**：明确 OPDCA Do→Check→Act 阶段的工具调用序列预期
2. **对比 90s 内 6 次 LLM 调用对应的工具**：是否符合 OPDCA 预期序列（reflection_agent → write_file → submit_deliverable → END）
3. **如符合** → 关闭怀疑、归档为 by design
4. **如不符合** → 进入子项调查：
   - 4a. reflection_agent profile.yaml 是否有递归 auto-trigger 条件
   - 4b. 主 prompt 是否缺少明确的 OPDCA 终止条件
   - 4c. 是否有未预期的 post-research 自动触发工具链

### 3.2 候选 ② LangGraph 上游 dispatch

| 证据 | 支持度 |
|------|--------|
| 9/9 stages 全部成功转换 | 🔴 **强反对** |
| 0 GraphRecursionError | 🔴 **强反对** |
| Test B HTTP API 5.93s 通过 | 🔴 **强反对** |
| recursion_limit=1000 未触发 | 🔴 **强反对** |

**判定**：⚪ **LOW — LangGraph dispatch 工作正常**

### 3.3 候选 ③ deepagents SDK 装配 / SubAgentMiddleware

| 证据 | 支持度 |
|------|--------|
| 0 BadRequestError | 🔴 **强反对** |
| 0 配对失败 | 🔴 **强反对** |
| `_return_subagent_command()` 返回 ToolMessage 正常（验证 [subagents.py:333-361](libs/deepagents/deepagents/middleware/subagents.py#L333-L361)）| 🔴 **强反对** |
| `_EXCLUDED_STATE_KEYS` workaround 完整覆盖（含 `subagent_logs`、`_summarization_event`）| 🔴 **强反对** |
| ChatQwen 17 次 0/N 转换 → 消息格式无问题 | 🔴 **强反对** |

**判定**：⚪ **LOW — deepagents SDK 装配工作正常**

---

## 4. 归属判定结论

| 层 | 责任 | 证据强度 |
|---|------|---------|
| **pmagent 应用层** | 🟢 **主要怀疑责任**（OPDCA workflow / prompt / subagent 配置）— 待 P0 核查定性 by design vs bug | HIGH |
| **dashscope 单次慢响应（62s）** | 🟡 **根因待定**（API 性能 / context size / reasoning model 三选一，需 §5.1 P2 调查）| MEDIUM（证据不足以定性）|
| **deepagents SDK** | ⚪ **无责任** | HIGH |
| **LangGraph 上游** | ⚪ **无责任** | HIGH |

---

## 5. 修复责任分配建议（A.4 输入）

### 5.1 pmagent 团队（主要怀疑责任 — 待 P0 核查后定性）

> **重要 caveat**（吸收 pmagent v1 review Gap 1）：
> "主要怀疑责任" ≠ "确认为 bug"。P0 核查可能发现 90s 行为是 OPDCA workflow **by design**（非 bug），届时 Track 2 范围将转为"补充终止 telemetry + 文档化预期行为"而非"修复"。pmagent 团队保留此 caveat 权利。

| # | 任务 | 修订点 | 优先级 | 预估 |
|---|------|--------|--------|------|
| **P0-1** | **核查 90s 行为是 OPDCA 设计意图还是 unintended loop**：① 读 `prompts/system_prompt_v1.md`（OPDCA Do/Check/Act 阶段工具序列预期）② 对比 90s 内 6 次 LLM 调用对应的工具序列 ③ 判定 by design vs bug | 替代 v1 P0-1（合并 prompt 检查 + workflow 视角）| P0 | **0.25-0.5 d**（视 prompt 完整度）|
| **P0-2** | **检查 post-research 自动触发工具链**：是否有未预期的工具链（**仅当 P0-1 判定为 bug 时执行**）| v1 P0-2 加条件分支 | P0（条件）| 0.5 d |
| **P1-1** | **检查 `reflection_agent` profile.yaml**：是否有递归 auto-trigger 条件 | 保留 | P1 | 0.25 d |
| **P1-2** | **添加 agent 终止单元测试**：测试断言基于 OPDCA workflow（如"Stage 9 后预期工具序列：reflection→write_file→submit_deliverable→END"），**不是简单"≤2 次 LLM 调用"** | 替代 v1 P1（OPDCA-aware 断言）| P1 | 0.5 d |
| **P2** | **慢响应根因调查 + 监控**：① 调查 62s 单次调用是 dashscope API 性能 vs 大 context（>100k tokens）vs reasoning model 思考时间 ② 根据根因决定缓解（API 切换 / context 压缩 / 告警阈值）| 替代 v1 P2（不武断归因外部 API）| P2 | **0.5 d**（含根因排查）|

**总估时**：1.75 - 2.25 d（v1: 2 d → v2 含 P0-2 条件分支不确定性）

### 5.2 deepagents 团队（无修复责任，但提供支持）

吸收 pmagent v1 review §4.3 表态：

| 任务 | 优先级 | pmagent 立场 | 预估 |
|------|--------|--------------|------|
| **可选**：在 SubAgentMiddleware 添加 telemetry hook（记录 SubAgent 返回后 parent 是否在 N 次内终止）→ pmagent 可订阅做 OPDCA workflow 诊断 | P3 | 🟡 不强需求，但欢迎 | 1 d |
| **建议加**：文档增强 — 在 [docs/api/](docs/api/) 添加 "SubAgent 终止最佳实践 + OPDCA-style workflow 预期行为" 章节（特别澄清非 ReAct 单 task 终止的多 stage workflow 模式）| P3 | 🟢 建议加 | 0.5 d |

> 注：以上为 deepagents 团队**可选** 工作，**不阻塞** Phase 1.5 业务适配。如 deepagents 团队精力有限，**可推迟到 Phase 1 完成后做**（pmagent 同意此排期）。

### 5.3 LangGraph 上游（无修复责任）

无相关 issue 需提交。

---

## 6. Phase 1.5 业务适配影响评估

| 维度 | 影响 |
|------|------|
| **装配实施路径** | 🟢 无影响（Phase A 结论与装配设计无关）|
| **私有 API 治理 4 纪律** | 🟢 无影响 |
| **8 项装配不变量** | 🟢 无影响 |
| **5 V2 增强类** | 🟢 无影响 |
| **Phase 1.0-1.4 启动** | 🟢 **可立即启动**（pmagent agent 终止修复并行进行）|

**结论**：Phase A 诊断完成后，**pmagent 团队可并行**：
- **Track 1**：执行 Phase 1.0-1.5（装配实施，按 ADR-0002 §10）
- **Track 2**：修复 pmagent agent 终止逻辑（本报告 §5.1）

两轨独立，无阻塞依赖。

---

## 7. 待会签事项

| 角色 | 状态 | 日期 | 备注 |
|------|------|------|------|
| deepagents CTO | ✅ v2 起草完成 | 2026-05-03 | v1 → v2 吸收 pmagent 4 处 amendments（OPDCA 视角 + 慢响应根因 + caveat）|
| pmagent 技术总监 | 🟢 v1 APPROVE WITH AMENDMENTS（2026-05-03）→ ⏳ v2 待正式会签 | 2026-05-03 → — | v2 已吸收 4 amendments，待 review 确认 |
| 项目负责人 | ⏳ 待最终批准 v2 | — | 批准转 Accepted（路径 1：v2 修订后批准）|

---

## 8. 会签后即可启动事项

1. ✅ **pmagent 团队**：按 §5.1 P0 任务启动 agent 终止逻辑修复（Track 2）
2. ✅ **pmagent 团队**：按 ADR-0002 §10 启动 Phase 1.0（pmagent 仓库准备 + invariants.py 起草）（Track 1）
3. ✅ **deepagents 团队**：按 ADR-0002，**fork 仓库进入归档准备**，Phase 1 实施期间 fork 不接受新改动

---

## 9. 附录：证据文件位置

| 产物 | 路径 |
|------|------|
| pmagent 主诊断报告 | `pmagent/docs/bug_fixes/PHASE_A_DIAGNOSIS_REPORT.md` |
| validation_results.json | `pmagent/docs/bug_fixes/validation_results.json` |
| Test A 完整日志 | `/tmp/phaseA_test_output.log` (568 行) |
| Test B 完整日志 | `/tmp/phaseA_test_b_output.log` |
| Thread state dump (Test B) | `/tmp/phaseA_thread_state_dump.json` |
| LangGraph Server 启动日志 | `/tmp/phaseA_langgraph_server.log` |
| 修复后的测试脚本 | `pmagent/tests/test_subagent_root_cause_validation.py` |
| **本报告** | `deepagents/docs/architecture/2026-05-03-phase-a-diagnosis-report.md` |

---

**报告状态**: 🟡 Draft v2 — 待 pmagent 技术总监正式会签 + 项目负责人最终批准
**deepagents CTO 签字**: ✅ v2 2026-05-03（含 4 amendments 修订）
**pmagent 技术总监 v2 终局**: 🟢 **APPROVE WITH TECHNICAL NOTES**（2026-05-03）
  - v2 实证核查 19/19 通过（grep 验证 4 amendments 全部落地）
  - 4 项 D-1~D-4 深度技术 review notes 归档至 `pmagent/docs/bug_fixes/PHASE_A_P0_WORKING_NOTES.md`（P0 阶段执行参考）
**项目负责人最终批准**: ✅ **批准**（2026-05-03，回复"批准"）
**当前状态**: 🟢 ACCEPTED — Track 1 + Track 2 双轨启动

**Track 2 范围 caveat（v2 新增）**: Track 2 启动后，pmagent 团队按 §5.1 P0-1 先核查 OPDCA workflow 设计意图。如判定为 by design (A)，Track 2 范围 → "补充 telemetry + 文档化预期行为"；如判定为 unintended loop (B)，Track 2 范围 → "P0-2 + P1-1 调查与修复"。两种情况都不阻塞 Track 1 装配实施。
