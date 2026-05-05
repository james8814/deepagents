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
| \[6\] | Path C 预约窗口：建议工作日周二/周三 GMT+8 上午 10:00-12:00。**Q2 裁决：主 2026-05-12 周二 + 备 1 5-13 周三 + 备 2 5-19 周二** | ✅ | 本文档 §4 |
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

---

## 4. Path C 窗口三档确认（指令 \[6\] / Q2 裁决）

| 优先级 | 窗口 | 触发条件 |
|---|---|---|
| **主** | 2026-05-12 周二 10:00-12:00 GMT+8 | T-24h 三项前置 Gate 全过 |
| 备 1 | 2026-05-13 周三 10:00-12:00 GMT+8 | 主窗口 T-24h 任一前置 Gate 未过，slip 1 天 |
| 备 2 | 2026-05-19 周二 10:00-12:00 GMT+8 | 备 1 仍未达 ready，slip 一周（应对 Gate 1.5 audit 二次 round-trip） |

**拒绝紧版（2026-05-08 周五）**：

- pmagent 桶 2（2.5-3.5d 含 audit gate）+ T-72h pre-flight 在 3 天内不可能同时达成
- 周五窗口违反"24h 观察期跨周末"避免准则
- ❌ 不予采纳

---

## 5. Slip 机制（指令 \[7\] 异常处理具象化）

```text
T-72h (2026-05-09 周六) │ Pre-flight Gate
  ├── pmagent staging cutover_dry_run.py 2 次 PASS
  ├── pmagent cutover_rollback_drill.sh 演练 PASS
  └── 22 invariants baseline 录入
  失败 → slip 主 → 备 1 (2026-05-13 周三)

T-48h (2026-05-10 周日) │ Gate 1.5 audit 截止
  CTO Phase 2c-2f + Gate 1.5 委员会 audit 提交截止
  失败 → slip 主 → 备 1 或 备 2 (2026-05-19)

T-24h (2026-05-11 周一) │ 最终 Go/No-Go
  ├── pmagent 桶 2 整体验收 L3 sign-off
  ├── CTO Gate 1.5 委员会 audit 通过
  ├── Pre-flight 三项全过
  失败 → slip 主 → 备 1 或 备 2

T-30min (2026-05-12 周二 09:30) │ Window-ready
  CTO + 项目负责人 + pmagent AI 三方在线 sync
  失败 → 立即 slip 备 1 (2026-05-13 周三)
```

**slip 决策权**：T-72h / T-48h / T-24h 任一 Gate 失败 → CTO + 项目负责人**双方书面 ack slip** → 自动启用下一备选窗口；**不需重新走 24h 协商**。

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
