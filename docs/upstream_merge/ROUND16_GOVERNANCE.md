# Round 16 Governance — 8 项指令 ACK + Gate 1.5 规范 + Path C 窗口确认

**触发**：项目负责人 2026-05-05 正式指令（Q1 + Q2 + 步步为营 8 项约束）
**作用域**：Round 16 sync 全周期（Phase 1b → Phase 2b atomic cutover → Gate 2）
**用途**：与 cherry-pick 工作显式区分的 governance 决策权威记录

---

## 1. 8 项指令 ACK 清单

| 指令 | 内容 | CTO ACK | 落档位置 |
|---|---|---|---|
| \[1\] | APPROVE β 暂停于 Phase 1a checkpoint，下次会话恢复 Phase 1b。**Q1 澄清裁决：保留 c99f9fd7（Option A）**，Phase 1b 从此 commit 继续 | ✅ | 本文档 §1 / ROUND16_PROGRESS.md |
| \[2\] | Phase 2 顺序重排：1a→1b→1c→Gate 1→2a→2c→2d→2e→2f→**Gate 1.5**→Hold→2b | ✅ | 本文档 §3 / ROUND16_RISK_ASSESSMENT.md §6 |
| \[3\] | Phase 2 每个子 Phase 独立 commit + 独立 L1 报告。**不允许跨 Phase 合并提交** | ✅ | 本文档 §1 |
| \[4\] | Gate 1.5（新增）— Phase 2a-2f 末端、2b 之前必须经委员会 audit；不通过 → 不允许进 2b | ✅ | 本文档 §2 / ROUND16_GATE2_CHECKLIST.md §0 |
| \[5\] | Phase 2b push 三重前置 Gate（pmagent 桶 2 / Path C 窗口 / cutover_dry_run baseline）；任一缺失 → push 阻断 | ✅ | ROUND16_GATE2_CHECKLIST.md §0' |
| \[6\] | Path C 预约窗口：建议工作日周二/周三 GMT+8 上午 10:00-12:00。**Q2 裁决：主 2026-05-12 + 备 1 5-13 + 备 2 5-19**。**ULTRATHINK 修订（2026-05-05 PM）：因桶 2.5 production migration 新增需 24-48h soak 跨周末，主 5-12 → 新主 5-13 周三；备 1 5-19 周二（升级为唯一备选）** | ✅ | 本文档 §4（ULTRATHINK 修订版） |
| \[7\] | 异常 → 停止 + 回滚到 Gate 1.5 + 复盘 + 项目负责人授权 — 禁止"先合并再修复" | ✅ | 本文档 §5 |
| \[8\] | 每 Phase / Gate 报告含：cherry-pick 比 + 冲突类别 + estimate vs actual + 剩余风险 | ✅ | ROUND16_PROGRESS.md Phase 1a 已用此格式 |

---

## 2. Gate 1.5 完整定义（指令 \[4\]）

**触发**：Phase 2a-2f 全部完成 + Stage B 进入 Hold 状态前。
**执行方**：委员会代表 + 质量团队（CTO 准备 evidence，但不能自我 audit）。
**通过条件**：四项 audit 全部 PASS，任一失败 → 不允许进 Phase 2b push。

### 2.1 11 项本地优越特性保护测试通过

- 见 ROUND16_GATE2_CHECKLIST.md §1 表格 11 项保护断言
- 每项验证：(a) 文件存在 + (b) 关键签名/类不变 + (c) 行为单测 PASS
- evidence：`pytest -v -k "skills_v2 or state_schema or summarization_overwrite or converters or subagent_logging or permissions or harness_profile or tool_exclusion"` 输出留档

### 2.2 StateBackend read-your-writes 影响审计完成（PR #2991）

- 新增 read-your-writes 测试 PASS
- 既有 StateBackend 测试 100% PASS（无 regression）
- pmagent 端 audit：grep 57 处 `StateBackend` 用法，标记任何"假设 write 后 read 看不到旧值"的代码 — 清单空 = PASS

### 2.3 `_PermissionMiddleware` re-export 验证完成（PR #3036）

- `from deepagents.middleware.permissions import _PermissionMiddleware, FilesystemPermission` import 仍可工作
- pmagent 31 处 permission import 路径不变（fork 端验证）
- evidence：`python -c "..."` 输出留档

### 2.4 Audit 结果落档

- 委员会出具 Gate 1.5 audit 报告（独立 markdown，含 PASS/FAIL 逐项 + 测试日志附件）
- 报告归档至 `docs/upstream_merge/ROUND16_GATE_1_5_AUDIT.md`
- **未通过 → CTO 不进 Phase 2b**，按指令 \[7\] 停止 + 回滚 + 复盘 + 项目负责人授权后再进

---

## 3. Phase 2 重排顺序固化（指令 \[2\]）

```text
Phase 1a (chore deps) ✅ 完成
   ↓
Phase 1b (CLI feat/fix, est 2h)
   ↓
Phase 1c (Evals/CI/Style/Test, est 1h)
   ↓
Gate 1 (单测基线, est 0.5h)
   ↓
Phase 2a (SDK low-conflict #2991/#2980/#3031, est 1h)
   ↓
Phase 2c (filesystem/permissions #3035/#3036, est 1h)
   ↓
Phase 2d (skills.py #2976, est 0.5h — empty commit 预案)
   ↓
Phase 2e (subagents.py #3045, est 0.5h)
   ↓
Phase 2f (sandbox #2695, est 0.5h)
   ↓
Gate 1.5 ⭐ (committee audit, est 1h, 指令 [4])
   ↓
⏸️ HOLD at 2b
   ├─ Phase 2b push 三重前置 (指令 [5])
   │   ├─ pmagent 桶 2 V2 子类化 sign-off (项目负责人本人)
   │   ├─ pmagent 桶 2.5 production V2 migration + 24-48h soak + L2 ack ⭐ (ULTRATHINK 新增)
   │   ├─ Path C 预约窗口确认 (§4)
   │   └─ cutover_dry_run.py baseline 通过
   ↓
[预约窗口内] Phase 2b ⚡ profiles API push (#2892 + #3082, 2-3h)
   ├─ atomic cutover trigger
   ├─ ≤5 min CTO 通知 pmagent
   └─ ≤30 min pmagent 桶 4+5 cutover (11 + 8 处 import)
   ↓
Gate 2 红线 (11 + 3 项加强, est 1.5h)
   ↓
Stage B 完成 → master fast-forward merge
```

**约束（指令 \[3\]）**：每个 Phase 独立 commit + 独立 L1 报告，不允许跨 Phase 合并。

### 3.1 ULTRATHINK 增补 — 桶 2.5 + Production Scope 立规（CTO 知悉）

**触发**：质量团队 ULTRATHINK 发现 pmagent 桶 2.2/2.3 V2 子类已在 `agent_assembly/builders.py` 实施，但 production graph (`src/agent.py:603, 651-658`) 仍直接构造 V1 → cutover 后 production 路径会 break。

**项目负责人裁决**：新增桶 2.5 — Production V2 Migration + Cutover-State Robustness。

**桶 2.5 子任务**（pmagent 团队执行）：

- 2.5.1: production callsites 列举 + 装配设计（0.5d）
- 2.5.2: cutover-state 鲁棒性修复（V2 在 upstream V1 父类下不能 TypeError，0.5-1d）
- 2.5.3: production swap（agent.py 直接构造 V1 → V2 factory 调用，0.25-0.5d）
- 2.5.4: production soak 24-48h（fork-state 监控异常，被动）
- 2.5.5: cutover-state 实证（临时构造 upstream-only 父类环境，0.25d）

**对 CTO Stage B 的影响**：

| 项 | 影响 |
|---|---|
| Phase 1b/1c/2a/2c/2d/2e/2f 顺序 | **不变** |
| Phase 2b push 时点 | slip 1 天（5-12 → 5-13）匹配桶 2.5 soak 完成 |
| Gate 1.5 audit 截止 | slip 至 2026-05-11 周一（T-48h）|
| Phase 2b 三重前置 \[5\] | **新增第 4 项**：pmagent 桶 2.5 production migration + soak + L2 ack |

**Production Scope 立规增补（CTO 在 Phase 2b push 前自检）**：

- [ ] 在 Phase 2b cutover_dry_run 中实证：production middleware stack（不仅 builders.py）已切到 V2
- [ ] `src/agent.py:603, 651-658` 等位点已切换到 V2 factory，不再直接构造 V1
- [ ] cutover-state 模拟（移除 fork patch，仅 upstream V1 父类）测试 PASS
- [ ] pmagent L1 报告含 production callsite 追溯（含 fallback 路径）

任一未通过 → Phase 2b push 阻断（按指令 \[5\] 三重前置 + 立规增补）。

---

## 4. Path C 窗口确认（指令 \[6\] / Q2 + ULTRATHINK 修订裁决）

### 4.1 ULTRATHINK 修订（2026-05-05 PM）— 主窗口 slip 1 天

**触发**：质量团队 ULTRATHINK 发现 pmagent 桶 2.2/2.3 production scope 缺陷 → 项目负责人新增桶 2.5（production V2 migration + cutover-state robustness）→ 桶 2.5 含 24-48h soak，跨过原主窗口 5-12 的 T-72h Pre-flight Gate（5-9 周六）→ 主窗口 slip 至 5-13 周三。

### 4.2 修订后窗口（生效）

| 优先级 | 窗口 | 触发条件 |
|---|---|---|
| **主**（修订） | **2026-05-13 周三 10:00-12:00 GMT+8** | T-24h（5-12 周二）三项前置 Gate 全过 + 桶 2.5 soak 完成 + Gate 1.5 audit 通过 |
| 备 1（修订） | 2026-05-19 周二 10:00-12:00 GMT+8 | 主窗口 T-24h 任一前置 Gate 未过，slip 1 周（应对 Gate 1.5 audit 二次 round-trip 或桶 2.5 soak 异常） |

**取消的窗口**：

- ~~原主 2026-05-12 周二~~ → 因桶 2.5 soak 无法在 T-72h Pre-flight 完成，slip 至新主 5-13 周三
- ~~原备 1 2026-05-13 周三~~ → 升级为新主
- ~~原备 2 2026-05-19 周二~~ → 升级为唯一备选

**拒绝紧版（2026-05-08 周五）**：

- pmagent 桶 2 + 桶 2.5（含 soak）3 天内不可能同时达成
- 周五窗口违反"24h 观察期跨周末"避免准则
- ❌ 不予采纳

---

## 5. Slip 机制（指令 \[7\] 异常处理具象化 — ULTRATHINK 修订版）

按修订后主窗口 **2026-05-13 周三 10:00 GMT+8** 反推：

```text
T-72h (2026-05-10 周日 10:00 GMT+8) │ Pre-flight Gate
  ├── pmagent staging cutover_dry_run.py 2 次 PASS
  ├── pmagent cutover_rollback_drill.sh 演练 PASS
  ├── 22 invariants baseline 录入
  └── 桶 2.5 soak 进行中（不要求完成，但不能 abort）
  失败 → slip 主 5-13 → 备 1 (2026-05-19 周二)

T-48h (2026-05-11 周一 10:00 GMT+8) │ Gate 1.5 audit 截止
  CTO Phase 2c-2f + Gate 1.5 委员会 audit 提交截止
  失败 → slip 主 5-13 → 备 1 (2026-05-19 周二)

T-24h (2026-05-12 周二 10:00 GMT+8) │ 最终 Go/No-Go
  ├── pmagent 桶 2 整体验收 L3 sign-off
  ├── pmagent 桶 2.5 production migration + soak 完成 + L2 ack
  ├── CTO Gate 1.5 委员会 audit 通过
  ├── Pre-flight 三项全过
  失败 → slip 主 5-13 → 备 1 (2026-05-19 周二)

T-30min (2026-05-13 周三 09:30 GMT+8) │ Window-ready
  CTO + 项目负责人 + pmagent AI 三方在线 sync
  失败 → 立即 slip 备 1 (2026-05-19 周二)
```

**slip 决策权**：T-72h / T-48h / T-24h 任一 Gate 失败 → CTO + 项目负责人**双方书面 ack slip** → 自动启用下一备选窗口；**不需重新走 24h 协商**。

**唯一备选**：备 1 = 2026-05-19 周二 10:00-12:00 GMT+8（无后续备选；slip 至此后再失败 → 项目负责人重新协商窗口）。

**异常处理边界（指令 \[7\]）**：
- ❌ 禁止"先合并再修复"
- ❌ 禁止跳过 Gate 1.5 直接 push 2b
- ✅ 任一 Phase 异常 → 停止 → 回滚到 Gate 1.5 → 复盘 → 项目负责人授权后再进

---

## 6. 落档前缀规范（未来 governance 与代码 commit 区分）

| 落档类型 | commit message 前缀 | 目的 |
|---|---|---|
| Cherry-pick 工作 | `chore(deps):` / `feat(sdk):` / `fix(sdk):` 等 | 沿用 upstream 原 commit message，保持 sync 分支 cherry-pick 纯度 |
| Governance 决策落档 | `docs(round16-governance):` ⭐ | 与 cherry-pick 显式区分，便于 `git log --grep="governance"` 审计 |
| Stage 阶段性报告 | `docs(round16-progress):` | 阶段总结报告（Phase 1a/1b/.../Gate 1.5/Gate 2） |
| 文档结构修订 | `docs(round16):` | 通用文档修订（如 ROUND16_RISK_ASSESSMENT.md / ROUND16_GATE2_CHECKLIST.md 内容更新） |

**已落档 commits 复盘**：

| commit | 类型 | 当时前缀 | 规范应改 |
|---|---|---|---|
| `3f28d796` | Stage B 启动准备 | `docs(round16):` | 沿用，无需改 |
| `4e8be37f` | Phase 1a 完成报告 | `docs(round16):` | 应为 `docs(round16-progress):`（追溯不改，未来执行） |
| `c99f9fd7` | 专家组裁决落档 | `docs(round16):` | 应为 `docs(round16-governance):`（追溯不改，未来执行） |
| `e3a9c891` | 5 项 AMBER 修复 | `docs(round16):` | 通用文档修订，沿用 |

**未来执行**：本 commit 起，governance 决策落档使用 `docs(round16-governance):` 前缀。

---

## 7. CTO 状态约束

提交本文档 commit 后：

- ⏸️ **Stand by** — 等下次会话项目负责人启动 Phase 1b 指令
- **不主动启动**：Phase 1b/1c/2 任何后续 cherry-pick 工作（governance 边界严守）
- **不擅自 reset**：c99f9fd7 + 后续所有 commits 保留（指令 \[7\] 禁止破坏性操作）

---

## 8. Refs

- 多专家组评审 APPROVE 报告（2026-05-05）
- 项目负责人 8 项指令（2026-05-05）+ Q1/Q2 裁决（2026-05-05）
- pmagent 桶 1 验收报告 §6/§12（atomic cutover SLA）
- v3.2.1 §3.3/§5A.1/§6.1/§11/§12（待桶 7 同步 round 13 → 16 命名）
- ADR v5 #16/#17/#19/#20/#22

**生成者**：CTO（deepagents fork）
**落档时间**：2026-05-05
**前缀规范启用 commit**：本 commit
