# Round 16 Deferred Backlog — Phase 1b Skip PRs

**触发**：项目负责人 ULTRATHINK 裁决 Q2 APPROVE option (a)（2026-05-06）
**作用域**：Phase 1b 6 个 skip PR + Phase 1c 可能新增的 skip PR（按 home 分类）
**目的**：避免 deferred items 在长 commit chain 中失踪 + governance 透明度

---

## 1. 6 个 deferred PR 清单（按 home 分类）

### Group A：Phase 2b 后处理（依赖 #2892 解锁）

| PR | 主题 | Skip 根因 | 解锁时点 |
|---|---|---|---|
| #2962 | honor SDK `ProviderProfile` defaults in `create_model` | Stacks on #2892（commit message 明示）；fork 当前 `_HarnessProfile` 8 字段未重构，cherry-pick 会 break | Phase 2b cherry-pick #2892 完成后 |
| #3111 | richer provider auth states + hosted Ollama auth | 与 #2962 关联（`config.py` 中 `_get_provider_kwargs` 同函数冲突）+ `model_selector.py` + `test_app.py` 三文件冲突 | Phase 2b 后，与 #2962 一并 |

**Group A 责任**：CTO（与 Phase 2b push 一并处理）
**Group A 决策时点 SLA**：Phase 2b push 完成后立即（~5-13 evening）

---

### Group B：Fork 架构分歧（需独立决策）

| PR | 主题 | Skip 根因 | Fork 端状态 |
|---|---|---|---|
| #3106 | move internal state under hidden directory | `agent.py` + `main.py` 双冲突 — fork main.py 仅 1 处 upstream-only 痕迹（`Best-effort SDK version lookup` 注释），即 fork 重构了内部 state 路径机制，与 upstream "hidden directory" 设计分歧 | Fork 用不同 state 管理 |
| #3102 | first-run onboarding flow | 依赖 fork 已删除的 `state_migration.py`（`ls`: No such file or directory），即 fork 在 Round 14/15 期间删除了 state migration 机制 | Fork 已删除依赖 |
| #3126 | set-as-default in `/agents` picker, harden persistence | `main.py` + `welcome.py` 二次冲突 — 同 #3106 路径（fork main.py 架构分歧） + welcome.py 已被 #3068 take theirs 改动 | 同 #3106 |
| #3123 | in-TUI API key entry via `/auth` | `command_registry.py` + `model_config.py` 冲突 — fork 内部 command/model config 机制分歧 | Fork command/config 系统差异 |

**Group B 责任**：项目负责人 + CTO 联合决策（涉及 fork 架构方向）
**Group B 决策时点 SLA**：Phase 1 完成后 + 桶 7 文档同步阶段（~5-15 ~ 5-17）

---

## 2. 每个 PR 决策路径模板

每个 deferred PR 在解锁时点应走以下决策树：

```text
Decision Path:

(1) Upstream 重新评估
    - upstream 是否有后续 PR 修正分歧？
    - 如有 → 等更新版本 PR，跳过当前
    - 如无 → 进 (2)

(2) Fork 适配
    - 是否可创建 fork-only 桥接代码（如 V2 method override）？
    - 估时 < 1d 且不破坏 fork 架构 → 实施
    - 估时 ≥ 1d 或破坏架构 → 进 (3)

(3) 永久 skip
    - fork 不需要此功能（用户场景不覆盖）
    - 或 fork 已有等价实现（不同路径）
    - 落档到 ROUND16_DEFERRED_BACKLOG.md §3 永久 skip 记录
```

---

## 3. 永久 skip 记录（待解锁后填入）

| PR | 永久 skip 决策 | 落档时点 | 决策人 |
|---|---|---|---|
| _（待解锁后填入）_ | _（决策路径 (3) 结果）_ | _（YYYY-MM-DD）_ | _（项目负责人/CTO）_ |

---

## 4. 与桶 2.6 NEW 关系澄清（防混淆）

**桶 2.6 NEW scope**（v3 修订版）：
- ONLY framework auto-injection migration（仅 Skills V2 使用框架 auto-injection 路径替代 `agent.py:605/651` 直接构造 V1）
- Skills V2 method overrides 已移到桶 2.5.2-bis（cutover 前完成）

**6 deferred PR 与桶 2.6 NEW 的关系**：
- ❌ **不属于桶 2.6 NEW scope**
- ❌ **不应混淆 governance 边界**
- ✅ Group A 通过 Phase 2b 后处理（CTO 责任）
- ✅ Group B 通过 §2 决策树独立处理（联合决策）

---

## 5. Phase 1c 新增 skip PR（待 Phase 1c 完成后追加）

Phase 1c (51 PR Evals/CI/Style/Test) 完成时，如有新增 skip PR：
- 加入本文档 §1 对应 Group（A/B）或新建 Group C（Phase 1c 独有）
- 走 §2 决策树
- 落档到 §3 永久 skip 记录（如适用）

---

## 6. 决策日志

| 时间 | 事件 | 决策 |
|---|---|---|
| 2026-05-06 | 项目负责人 Q2 APPROVE option (a) | 立即创建本文档 |
| 2026-05-06 | CTO 落档 | 6 deferred PR 分组：Group A (2) + Group B (4) |
| _TBD_ | Phase 2b push 完成 | Group A #2962/#3111 进入解锁评估 |
| _TBD_ | 桶 7 文档同步阶段 | Group B 4 PR 进入联合决策 |

---

## 7. Refs

- ROUND16_PROGRESS.md §Phase 1b 详细记录
- 项目负责人 ULTRATHINK 裁决（2026-05-06）§Q2 答复
- 桶 2.6 NEW scope v3 修订（基于桶 2.5.2-bis Method overrides 接管 feature recovery）
- 立规 §3 落档前缀规范

**生成者**：CTO（deepagents fork）
**前缀规范**：本文件由 `docs(round16-governance):` commit 创建
