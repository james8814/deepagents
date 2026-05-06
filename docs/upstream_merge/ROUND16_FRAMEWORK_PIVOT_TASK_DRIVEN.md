# Round 16 Framework Pivot — Calendar-Driven → Task-Driven

**触发**：项目负责人 2026-05-06 EOD 框架更正
**生效**：自本 commit 起立即全量适用（按立规 §2.7）
**作用域**：Round 16 Stage B + Phase 1.5 + Phase 2 全部工作流

---

## 1. 根本性更正

**项目负责人洞察**：AI 团队不按工作日运行，按任务完成度运行。Calendar-Driven 范式是把人类项目管理错误套在 AI 团队上。

**Pivot**：

| 维度 | Calendar-Driven（旧）| Task-Driven（新）|
|---|---|---|
| 进度推进 | "X 日完成 Y" 预排 | 任务依赖到达即推进 |
| Checkpoint | calendar 时点（5-7 09:00 GMT+8）| 事件触发（"T+12h soak 完成后"）|
| Cutover 窗口 | 5-13 周三 hard deadline | 双方 ready 后协调的可移动协调点 |
| Slip | calendar 反推（5-9 Sat EOD trigger）| 事件驱动（持续超可接受 / 异常 / drift 不可调和）|
| Cadence | 每日 EOD 强制 ping | 任务完成 → L1 / 异常 → 立即 / 例行 healthy → 不报告 |

---

## 2. 保留项（governance 与 calendar 无关）

| 类别 | 项 |
|---|---|
| 任务依赖顺序 | Phase 1a→1b→1c→Gate 1→2a→2c→2d→2e→2f→Gate 1.5→Hold→Phase 2b→Gate 2 |
| Gates | Gate 1 / Gate 1.5 / Gate 2 + 三重前置（pmagent 桶 2.5.5 + 协调窗口 + cutover_dry_run baseline） |
| 协调 SLA | Phase 2d/2e push 后 ≤5 min ping pmagent + ≤30 min pmagent ack；Phase 2b push 后 ≤5 min 通知 + ≤30 min cutover |
| 步步为营原则 | "L2 ack 后不修改" / 行为完整性 > schedule > 治理 |
| 验收标准 | 11 项保护 + StateBackend RYW + `_PermissionMiddleware` re-export + Gate 1.5 委员会 audit |
| 立规库 7 项 | §2.1 / §2.4 / §2.4 v2 / §2.5 / §2.7 / §2.8 / §2.8 v2 / §2.9 |

---

## 3. CTO 流水线（事件驱动）

```text
事件 1: Network 恢复触发
  → Gate 1 完整单测（~30 min 含 venv 重建）
  → A15 fork-side patch（~10 min, TestModifiedBackspaceDeleteWordLeft 补回）
  → Phase 2a（3 PR low-conflict, ~1h）
  → Phase 2c（filesystem/permissions, ~1.5h, +50% buffer）
  → Phase 2d（skills.py PR #2976，⚠️ ping pmagent SLA ≤5 min + 等 ≤30 min ack）
  → Phase 2e（subagents.py PR #3045，⚠️ 同上）
  → Phase 2f（sandbox PR #2695，~0.5h）
  → Gate 1.5 audit submission（含 §5A multi-source）

事件 2: Gate 1.5 委员会 ≤24h ack
  → Hold at 2b
  → 三重前置 Gate 全闭环（pmagent 桶 2.5.5 + 协调窗口 + dry-run baseline）

事件 3: Cutover 协调窗口（双方 ready 后协商）
  → Phase 2b push（#2892 + #3082）
  → atomic cutover trigger
  → ≤5 min ping pmagent + ≤30 min pmagent cutover
  → 24h 观察期

事件 4: Phase 2b 完成 + 24h 观察期内
  → DEFERRED Group A 4 PR 处理（#2978 / #2992 / #3067 / #3078）
  → 桶 6 5 层测试启动

事件 5: Phase 1 验收 + 7 工作日稳定
  → 桶 2.6 NEW Phase 1.5 polish（pmagent 主导，CTO 不参与）
```

---

## 4. Slip 触发条件（事件驱动）

| 触发场景 | 处置 |
|---|---|
| A. CTO Network 持续 blocked 超可接受窗口 + Layer 2 30% gap 不可接受 | 协调下一个 cutover 窗口（不锁日期） |
| B. pmagent 桶 2.5.X 任一异常 stop → rollback → 评估 | 修复后回归流水线 |
| C. Phase 2d/2e fork drift 影响 V2 不可调和 | pmagent 桶 2.5.2-bis snapshot 修订 → 回归流水线 |

**无固定日期 slip**——任务流连续推进，到达点即处理。

---

## 5. 现有 ROUND16 文档中 Calendar-Driven 残留（待自然 supersede）

按 §4 cadence 简化（"例行 healthy checkpoint 不主动转达"），现有文档中的日历日表述**不立即重写**——等 Phase 2 启动 / Phase 2b push 完成等任务完成时一并 supersede（避免 mid-period commit noise）。

| 文档 | 含日历日章节 | 处理 |
|---|---|---|
| `ROUND16_GOVERNANCE.md` §4 Path C 窗口 | 主 5-13 周三 + 备 5-19 周二 | 改为"双方 ready 协商"——Phase 2b 协调时一并改 |
| `ROUND16_GOVERNANCE.md` §5 Slip 机制 timeline | T-72h/-48h/-24h/-30min 反推 5-13 | 改为事件驱动（§4 修订版）——同上 |
| `ROUND16_GATE_1_5_AUDIT_TEMPLATE.md` §6 Audit 时序 SLA | 5-10/5-11/5-12/5-13 | 改为"Phase 2f 完成 → Gate 1.5 → ≤24h ack → ..."——Gate 1.5 提交时一并改 |
| `ROUND16_PROGRESS.md` 各 Phase 行 | "(下次会话)"等 | 已自然过期（Phase 1a/1b/1c 已完成），无需改 |
| `ROUND16_DEFERRED_BACKLOG.md` §1 Group A SLA "5-13 evening" | 改为"Phase 2b push 完成后立即" | DEFERRED Group A 处理时一并改 |

**审计可追溯性**：本文档作为 framework pivot 权威记录，未来引用时优先查本文档而非现有文档中的 calendar 表述。

---

## 6. Cadence 简化（按项目负责人 §4）

| 触发 | CTO 报告 |
|---|---|
| 任务完成（Phase / Gate / 桶）| 自然交付 L1 报告 |
| Δ 偏离 / 异常 / blocker | 立即转达 |
| 重大决策点（Cutover 协调 / Phase 2 触发评估）| 双方在群同步 |
| 例行 healthy checkpoint | **不主动转达** |

**取消项**：
- 每日 EOD 强制 ping
- 5-7 / 5-8 / Day N calendar checkpoint

---

## 7. CTO 当前状态（事件驱动）

```yaml
HEAD: e6a04490 (GATE_1_5 §5A multi-source 增补)
Branch: upstream-sync-round16
等待事件: Network 恢复触发 → Layer 1 启动 (~5-6h Stage B 完成)
备选事件: Network 持续 blocked → Layer 2 准备 + 协调下一窗口

不等: 日历日 / "下次会话" / EOD ping
等: 任务依赖事件触发
```

---

## 8. 立规适用性（不变）

7 立规与 Calendar / Task-Driven 无关，全部继续生效：

- §2.1 三层动态实证（Layer 1/2/3）
- §2.4 双轨 ULTRATHINK（Track A + Track B）
- §2.4 v2 RED/AMBER 5 维度首次必含
- §2.5 三维度 Drift Gate
- §2.7 立规即时全量生效（**本文件即应用此立规：framework pivot 即时生效**）
- §2.8 / §2.8 v2 multi-source measurement + LOCK
- §2.9 异常 vs baseline 调查协议

---

## 9. Refs

- 项目负责人 2026-05-06 EOD framework pivot 指令
- 立规 §2.7 即时全量生效
- ROUND16_GOVERNANCE.md / ROUND16_GATE_1_5_AUDIT_TEMPLATE.md / ROUND16_DEFERRED_BACKLOG.md
- 7 立规库 (§2.1/§2.4/§2.4 v2/§2.5/§2.7/§2.8/§2.8 v2/§2.9)

**生成者**：CTO（deepagents fork）
**前缀**：`docs(round16-governance):` (framework pivot 决策落档)
