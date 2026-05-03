# Phase 1.7 + P2 验收 CTO 自查报告 — 撤回 PASS 改判 REJECT/CONDITIONAL

**报告日期**: 2026-05-03
**起草人**: deepagents CTO（自查 + 接受三方专家 review）
**性质**: **撤回先前 PASS 验收**，接受三方专家 deep review 全部判定
**触发**: deepagents 内部三方专家（架构师 + 研发主管 + LangChain/LangGraph/deepagents 专家）联合 review 报告

---

## 1. CTO 立场转变（诚实声明）

### 1.1 先前 CTO 验收（2026-05-03 早些时候）— **错误**

| 验收项 | CTO 先前判定 | 应该判定 |
|---|---|---|
| Phase 1.7 升级 SOP | 🟢 PASS | 🔴 **REJECT — v1.1 重写** |
| Track 2 P2 调查 | 🟢 PASS | 🟡 **CONDITIONAL — v1.1 修订** |

### 1.2 CTO 失误根因（实证自查）

CTO 先前 PASS 验收基于 3 项 cross-validate "一致性"：

| CTO 先前依据 | 实际盲区 |
|---|---|
| "SOP 11/11 + 15/15 引用与 Phase 1.0/1.6 一致" | 🔴 **CTO 对照的是 SOP 文档 ↔ ADR 文档，未对照 SOP ↔ pmagent 真实代码（pyproject.toml + .gitmodules）** |
| "P2 25.2% utilization 实证" | 🔴 **CTO 引用了 pmagent 报告 quote，未读 log 原文验证 25.2% 实际含义** |
| "P0 working notes 70% → P2 85% reasoning model 置信度" | 🔴 **CTO 接受了置信度提升，未做独立 fact-check（Qwen 命名约定、dashscope 文档）** |

**根本失误**：CTO 应用了"内部一致性"的 cross-validate，**没应用 ADR checklist v3 #7 fidelity 量化（与真实代码 / 真实 log / 真实文档对照）**。这是 CTO 自己确立的 checklist，自己没应用。

---

## 2. 三方专家 3 项错误 — CTO 实证验证

### 2.1 错误 #1：SOP 整体基于 PEP 440 PyPI 假设（致命）

**CTO 实证**：

```bash
$ grep deepagents pmagent/pyproject.toml
"deepagents @ file:///Volumes/0-/jameswu%20projects/langgraph_test/pmagent/third_party/deepagents",

$ cat pmagent/.gitmodules
[submodule "third_party/deepagents"]
    path = third_party/deepagents
    url = git@github.com:james8814/deepagents.git
    branch = master
```

✅ **三方专家正确**：

- pmagent 实际用 **git submodule + file:// 本地路径引用** deepagents
- **不是 PyPI ~=0.5.0 PEP 440 锁定**
- SOP 写的"修订 pyproject.toml `deepagents = ~=0.5.X`"完全不适用
- SOP 写的"决策树补丁/minor/major"对本地源码引用没有语义
- SOP 写的"应急升级 CVE security patch"基于 PyPI 发布周期，不适用

**严重程度**：🔴 CRITICAL — SOP 按现状执行会失败。

**CTO 反思**：在 D-2 v1→v2 修订时（CTO 第一次重大失误），我说 "Plan H+ 'pmagent 通过 pip 直接依赖上游 langchain-ai/deepagents'"。但**当前 pmagent 实施现实并非如此** — pmagent 当前用 fork（james8814）submodule。这是 ADR-0002 v3 设计目标 vs 当前实施现实的 gap。CTO 应该知道这个 gap，但起草 D-2 v2 时和 PASS 验收 SOP 时**都未对照 pyproject.toml 实证**。

### 2.2 错误 #2：P2 §2.3 "25.2% utilization" 数据误读（CRITICAL）

**CTO 实证**：

```bash
$ grep "25.2%\|max_input_tokens=252" /tmp/phaseA_test_output.log
[2026-05-03 00:36:29,745] [INFO] - Patched profile for qwen3-max: max_input_tokens=252,000 (utilization: 25.2% of 1M context)
[2026-05-03 00:36:29,756] [INFO] - Patched profile for qwen3-max: max_input_tokens=252,000 (utilization: 25.2% of 1M context)
... (多次重复，全是 model profile 初始化时的元数据)
```

✅ **三方专家正确**：

- "utilization: 25.2% of 1M context" 实际含义：qwen3-max 配置上限 max_input_tokens=252,000 占 1M context 的 25.2%（**model profile 元数据**）
- **不是本次 LLM 调用的实际 input tokens 使用率**
- log 中**完全没有记录每次 LLM 调用的实际 input tokens 数**
- P2 报告 §2.3 "22 messages, max_input_tokens 25.2% utilization, 远低于阈值" → "排除 context size 触发" — **逻辑链断裂**

**严重程度**：🔴 CRITICAL — 排除法核心证据错误。

**真实情况**：22 messages 内含 research_agent Deep Research 9 stage 的大量返回结果（可能 10K+ tokens），**实际 input tokens 数未知，无法排除 context size**。

### 2.3 错误 #3："qwen3-max 是 reasoning model" 未验证 claim（HIGH）

**CTO 实证**：

```bash
# pmagent config.yaml 实际描述
qwen3-max:
  model: "qwen3-max"
# - qwen3-max: Qwen3 系列最强，适合超复杂任务
```

**Qwen 命名约定 fact-check**（来自 review 团队）：

- Qwen 系列 reasoning 模型典型命名：`qwen3-coder-30b-a3b-thinking`（带 `-thinking` 后缀）
- `qwen3-max` **没有 `-thinking` 后缀**
- 真实 reasoning 模型行为可通过 API response 中的 `reasoning_content` / `thinking_tokens` 字段确认 — log 未观察到这些字段

✅ **三方专家正确**：

- "qwen3-max 是 reasoning model" 是 P0 working notes 未验证 claim，P2 直接继承且把置信度从 70% → 85%，**无新增独立证据**
- 命名约定 + log 字段缺失 → **qwen3-max 很可能不是 reasoning model**
- 如果不是 reasoning model，62s 慢响应需要其他解释（候选：超长 prompt content / dashscope 服务端偶发慢路径）

**严重程度**：🟡 HIGH — P2 推荐 Option D（不修复）基于错误前提。

---

## 3. 修订验收结论

### 3.1 Phase 1.7 升级 SOP — 🔴 REJECT

| 项 | CTO v1 判定 | CTO v2 修订判定（接受 review）|
|---|---|---|
| 整体设计 | 🟢 PASS（决策树清晰）| 🔴 **REJECT — 整体基于 PEP 440 错误前提**，需 v1.1 重写为 git submodule 流程 |
| 强制门 1+2+3 设计 | 🟢 PASS | 🟢 **保留** — 设计层次合理，可在 v1.1 中复用 |
| 4 升级路径决策树 | 🟢 PASS | 🟡 **保留 + 重做**：决策树思路合理，但需基于 git submodule + commit hash 重新设计 |
| §6 应急升级 fork+patch | 🟢 PASS（minor 用词问题）| 🔴 **重写** — 基于 PyPI 发布周期假设错误 |
| §6.2 langchain/langgraph 升级路径覆盖 | 未提及 | 🔴 **必须新增** — review 提出的 §2.2 设计错误（HIGH）|
| 审批流程双签 | 未提及 | 🟡 **新增** — review 提出的 §2.3 流程问题（MEDIUM）|

**重写工作量**：~0.5 d（保留 §3 强制门设计 + 重写 §1 决策树 + §3.2 升级执行 + §6 应急流程）

### 3.2 Track 2 P2 调查 — 🟡 CONDITIONAL

| 项 | CTO v1 判定 | CTO v2 修订判定（接受 review）|
|---|---|---|
| 调查方法（排除法）| 🟢 严谨 | 🟡 **方法论保留，但 §2.3 证据错误使排除法链断**，需 v1.1 修订 |
| 时间线 61.7s 实证 | ✅ | ✅ **保留** — 实证准确 |
| ChatQwen 0/22 转换实证 | ✅ | ✅ **保留** — middleware overhead 排除合理 |
| §2.3 "25.2% utilization" 排除 context size | ✅（CTO 未独立验证）| 🔴 **删除 — 数据误读**，改为"实际 input tokens 未记录，无法排除 context size 假设" |
| §3.1 reasoning model 置信度 85% | ✅（CTO 未独立验证）| 🔴 **下调至 50-60% 区间** — 标注为未验证 claim，必须 benchmark 才能提升 |
| §6.3 Option D 不修复推荐 | 🟢 推荐 | 🟡 **降级** — 基于错误前提，应改为"必须先 benchmark 再决定"|
| §8 致 D-2 telemetry 6 项指标 | 🟢 价值 | ✅ **保留** — 业务上下文需求列表对 D-2 v2 仍有价值 |

**修订工作量**：~0.25 d（删除 §2.3 误读 + 重写 §3.1 置信度评估 + 调整 §5/§6 推荐）

### 3.3 Phase 1.6 invariant tests — ✅ PASS（不变）

review 团队对 Phase 1.6 仍 APPROVE，CTO 先前判定保留。

---

## 4. 决策点 (1)~(5) CTO 修订评估

### 决策 (1) 接受 review 报告 + 批准 v1.1 修订

🟢 **CTO 强支持** — review 报告 3 项错误全部实证证实，必须接受。

### 决策 (2) 修订路径选择

🟢 **CTO 推荐 (a) 立即新 commit 修订两份文档 v1.1** — review 团队也推荐 (a)：

- (a) 保留 git history，修订透明 ✅
- (b) revert 78e5547 重写 — 破坏 trust（"假装从没出错"）❌
- (c) 加 warning 头不修订内容 — 留 broken SOP 给未来 ❌

### 决策 (3) 是否同步给 deepagents CTO（v3 checklist #9 沉淀）

🟢 **必须同步** — CTO 已收到本 review 报告并自查 + 撤回 PASS 验收。

### 决策 (4) Phase 1.8 e2e 启动时机（CTO 先前推荐 (a) 现在启动）

🟡 **CTO 修订推荐**：**等 SOP v1.1 完成后再启动 Phase 1.8 e2e**

**理由**：

- Phase 1.8 e2e 通过 → 触发 D-1 fork 归档 SOP 执行
- D-1 SOP 执行依赖 SOP v1.0/1.1 的升级流程框架
- 如 SOP v1.1 仍在修订中，不应执行 D-1（按错误 SOP 归档可能漏 langchain/langgraph 升级路径）
- review 团队明确建议："D-1 fork 归档 SOP 等 SOP v1.1 修订完再启动"

### 决策 (5) Phase 1.2 拓展 / dashscope benchmark

| 决策点 | CTO 修订推荐 |
|---|---|
| Phase 1.2 拓展 | 🟡 不变 — business-driven，不主动启动 |
| dashscope benchmark | 🟡 **修订评估** — review 团队认为是"必需项才能提升 P2 置信度"。CTO 先前不批准基于 Option D，但 Option D 本身基于错误前提。现修订为：**P2 v1.1 修订时由 pmagent 团队评估是否纳入**（不是 CTO 单方决策） |

---

## 5. deepagents 团队职责调整

### 5.1 D-2 v2 telemetry hook 实施

🟢 **不受影响，可继续启动**（review 团队明确：D-2 不依赖 SOP/P2 修订）

- pmagent 团队 R-1~R-6（3 d）
- deepagents CTO review（~1.5 h）

### 5.2 D-1 fork 归档 SOP 执行

🔴 **必须推迟**（review 团队明确：等 SOP v1.1 修订完再启动）

- 原触发条件：Phase 1.8 e2e PASS + 双方授权
- **修订触发条件**：SOP v1.1 修订完成 → Phase 1.8 e2e PASS → 双方授权

### 5.3 deepagents fork（james8814）归档时机重新评估

CTO 先前 PASS 验收时假设 pmagent 已用上游 PyPI deepagents。**实证证实 pmagent 仍用 fork submodule**。

**归档前 prerequisite**：

- pmagent 必须**实际切换**到上游 PyPI deepagents（不是 fork submodule）
- 这是 Plan H+ "消除 fork" 承诺的真实落地，不是文档承诺
- **当前过渡期 pmagent 实际仍依赖 fork**

CTO 先前对 fork 归档时机评估**未基于这个实证**，需在 v1.1 修订过程中重新评估。

---

## 6. ADR checklist v4 增补建议（基于本次 CTO 失误沉淀）

延续 v1+v2+v3，建议加入：

| # | 内容 | 来源 |
|---|---|---|
| **#16** | **任何技术文档（SOP / 调查报告 / 验收报告）的关键 claim 必须配 fact-check checklist + 引用 source 文件具体行号** | review 团队提出 + CTO 失误证实 |
| **#17** | **"内部一致性 cross-validate" 不等于"与真实代码 fidelity 量化"** — 验收必须实测对照真实代码 / log / 文档 | CTO 失误根因 |
| **#18** | **CTO 验收也需要被 review** — review 团队应有权对 CTO 验收提质疑（本次 review 报告即范例） | CTO 失误证实 |
| **#19** | **继承自其他文档的 claim（如 P0 working notes → P2）必须独立 fact-check**，不能因为来源权威就传播 | P0→P2 reasoning model claim 失误 |

---

## 7. CTO 第二次失误 — 元层观察

这是 CTO 在本会话**第二次重大失误**：

| 失误 | 错误 | 修订触发 |
|---|---|---|
| **失误 1**（D-2 v1）| 设计违反 0 monkey-patch + 装配主权 | 项目负责人挑战 + CTO 承认 |
| **失误 2**（Phase 1.7+P2 PASS 验收）| 未对照 pmagent 真实代码做 fidelity 量化 | 三方专家 review 校正 + CTO 承认 |

**两次失误共同根因**：CTO 未严格应用自己确立的 ADR checklist（#3 grep 验证、#4 import test、#7 fidelity 量化）。

**沉淀**：

> **CTO 不是 quality first 的豁免者** — CTO 推荐 / 验收都必须被实证检验。三方专家 + 项目负责人有权（且应该）对 CTO 工作做 review。

未来 CTO 验收报告应明确标注 "待 review 团队复核 / 待项目负责人挑战"，不假设 CTO 单方判定终审。

---

## 8. 修订验收三方签字

| 角色 | 状态 | 备注 |
|---|---|---|
| **三方专家**（架构师 + 研发主管 + LangChain/LangGraph/deepagents 专家）| ✅ Review 完成 + 三方签字 | REJECT SOP / CONDITIONAL P2 |
| **deepagents CTO** | ✅ **撤回 PASS 验收 + 接受 REJECT/CONDITIONAL 改判 2026-05-03** | 含 CTO 自查 + 失误根因 + checklist v4 增补建议 |
| **项目负责人** | ⏳ 待批准 v1.1 修订路径 (a) + 决策点 (3)/(4)/(5) 修订 | CTO 推荐：(3)=同意 / (4)=等 SOP v1.1 / (5)=pmagent 自主决策 benchmark |

---

## 9. 推荐下一步

### 9.1 pmagent 团队（修订）

| # | 工作 | 估时 |
|---|---|---|
| ⏳ | SOP v1.1 重写（基于 git submodule 实际架构 + 覆盖 langchain/langgraph 上游 + 双签流程）| 0.5 d |
| ⏳ | P2 v1.1 修订（删除 utilization 误读 + 标注 reasoning model 未验证 + 评估是否纳入 benchmark）| 0.25 d |
| 🟢 | D-2 v2 telemetry hook 实施 R-1~R-6（独立，不阻塞）| 3 d |

### 9.2 deepagents 团队（CTO）

| # | 工作 | 估时 |
|---|---|---|
| ✅ | 本 CTO 自查报告 | 已完成 |
| ⏳ | review SOP v1.1（与 git submodule 实证一致性）| ~30 min |
| ⏳ | review P2 v1.1（修订是否充分）| ~30 min |
| ⏳ | review D-2 v2 实施（已规划 ~1.5 h）| 已规划 |
| 🔒 | D-1 fork 归档 SOP 执行 — **推迟到 SOP v1.1 + Phase 1.8 e2e 完成** | trigger driven |

### 9.3 ADR checklist v4 沉淀

⏳ ADR-0002 v3 changelog 增补 #16 #17 #18 #19（CTO 起草，~15 min）

---

**报告状态**：✅ CTO 自查 + 撤回 PASS + 接受 REJECT/CONDITIONAL 改判 2026-05-03
**deepagents CTO 签字**：✅ 2026-05-03（撤回先前 PASS 验收 + 第二次失误诚实声明 + 接受 review 团队三方签字判定）

**配套文档**：

- [Phase 1.5 验收报告](2026-05-03-phase-1-5-acceptance-report.md)（先前 PASS，仍有效）
- [Phase 1.6 验收报告](2026-05-03-phase-1-6-acceptance-report.md)（先前 PASS，仍有效）
- ~~[Phase 1.7+P2 验收 PASS 结论]~~ — **本报告撤回**
- [D-2 v2 设计](2026-05-03-d2-subagent-telemetry-hook-design.md)（CTO 第一次失误后修订版）
- [ADR-0002 v3](decisions/0002-fork-customization-strategy.md)（待加 checklist v4 #16-#19）
