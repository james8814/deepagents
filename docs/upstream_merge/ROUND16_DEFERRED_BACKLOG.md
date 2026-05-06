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

## 5. Phase 1c 新增 skip PR（2026-05-06 本日同步落档）

Phase 1c (实际 ~50 PR Evals/CI/Style/Test) 完成（41/~50 = ~82%）+ 9 个 skip PR 分组：

### Group A（追加，Phase 2b 后处理）

| PR | 主题 | Skip 根因 | 解锁时点 |
|---|---|---|---|
| #2978 | refactor(sdk,evals): migrate deprecations to `langchain_core` helpers | SDK 主线 — `protocol.py` + `filesystem.py` 冲突，与 fork `_convert_document_sync` 路径关联 | Phase 2c filesystem 簇后 |
| #2992 | chore(sdk): inline file permission logic | 与 fork `_PermissionMiddleware` 关联（permissions.py 内联化重构） | Phase 2c 后 |
| #3067 | chore(sdk): return `ToolMessage` with status from all filesystem tools | filesystem.py 主线，与 fork `_convert_document_sync` 关联 | Phase 2c 后 |
| #3078 | docs(sdk): document removing the task tool | graph.py + harness 路径迁移（profiles 重构相关） | Phase 2b 后 |

### Group B（追加，fork 架构分歧 — CLI UI）

| PR | 主题 | Skip 根因 | Fork 端状态 |
|---|---|---|---|
| #3142 | style(cli): clarify onboarding name persistence | 依赖 fork 已删除的 `launch_init.py`（与 #3102 同根因） | Fork 已删除依赖 |
| #3113 | style(cli): hint API-key setup above `/model` | `model_selector.py` + `test_model_selector.py` 冲突（与 #3111 关联） | Fork model_selector 分歧 |
| #3125 | style(cli): hide "credentials set" indicator in `/model` header | `model_selector.py` 二次冲突 | 同 #3113 |

### Group C（新增，release / version mgmt — 低优先级）

| PR | 主题 | Skip 根因 | 处置 |
|---|---|---|---|
| #2528 | ci(runloop): set up release-please | `.release-please-manifest.json` + `release-please-config.json` 冲突（fork 自管理 release config） | 永久 skip — fork 不发版 |
| #2729 | chore(cli): bump deepagents version | `libs/cli/pyproject.toml` 冲突（fork 维持 0.5.0） | 永久 skip — fork 不发版 |

### Phase 1c 累计 skip 后置 SLA

- Group A 4 PR：CTO 责任 — Phase 2c 完成后立即评估（5-7~5-8）
- Group B 3 PR：项目负责人 + CTO 联合决策 — 桶 7 阶段或桶 2.6 NEW post-cutover（5-15~5-17）
- Group C 2 PR：永久 skip（fork 不发版语境）

---

## 6. Phase 1c Take Theirs 副作用（A15 落档）

### 6.1 #3026 覆盖 #3037 的 `TestModifiedBackspaceDeleteWordLeft` 测试 class

**事实**：

- Phase 1b 接受 #3037（`fix(cli): support modified backspace word deletion`）→ test_chat_input.py 增加两个 class：`TestChatTextAreaKeybindings` + `TestModifiedBackspaceDeleteWordLeft`
- Phase 1c 接受 #3026（`test(cli): guard chat input against ctrl+m shadowing`）→ test_chat_input.py 二次冲突，take theirs 后**覆盖了 #3037 引入的 `TestModifiedBackspaceDeleteWordLeft` class**
- ast.parse 实证：当前 class 数 37（vs Phase 1b 完成后 38）

**功能影响**：

- ✅ `TestChatTextAreaKeybindings` 仍存在（含 `test_modified_backspace_deletes_word_left` method）
- ❌ `TestModifiedBackspaceDeleteWordLeft` class 丢失（独立详细测试）
- ✅ #3037 source 改动（`d271f688`）仍在 — 功能未丢失，仅细粒度测试覆盖丢失

**严重度**：🟡 中（功能完整 + 部分测试覆盖丢失）

**修复路径**：

| Option | 描述 | 成本 | 推荐 |
|---|---|---|---|
| a | revert Phase 1c #3026 + 重新 take theirs 时手动 merge fork & upstream 测试 | 高复杂度（影响 commit chain） | ❌ |
| b | Gate 1 启动前补回 `TestModifiedBackspaceDeleteWordLeft` class（fork-side patch，不修改 cherry-pick 历史） | ~10 min | ✅ |
| c | Document + Phase 6 E2E 兜底测试覆盖 | 长尾保障 | 🟡 备选 |

**CTO 决策**：Option b（fork-side patch in Gate 1 阶段）+ Option c（备选保障）。

### 6.3 A16 RED — SDK test_models.py ImportError (Gate 1 baseline)

**触发**：Network 恢复事件 → Layer 1 Gate 1 完整单测基线（2026-05-06 EOD continued）。

**5 维度（立规 §2.4 v2）**：

1. **发现内容**：`tests/unit_tests/test_models.py:19` import `GeneralPurposeSubagentProfile from deepagents.profiles` 失败。fork 在 Phase 2b #2892 profile API 重构前**不含此 class**，但 Phase 1c #3071 `test(sdk): silence expected UserWarnings` take theirs 引入 upstream 测试期望。
2. **修复方式**：Gate 1 baseline 时 `--ignore=tests/unit_tests/test_models.py`（17 个测试 skipped）。**Phase 2b cherry-pick #2892 后此 class 自动在 fork 中可用，A16 自动恢复**。无需 fork-side patch。
3. **来源轨道**：Track A Forward-driven（Gate 1 baseline 实跑发现）。
4. **审计可追溯**：error trace `ImportError: cannot import name 'GeneralPurposeSubagentProfile' from 'deepagents.profiles'`。落档于本文件 + Phase 2b 后置 Group A 处理时一并 unskip。
5. **严重度判定**：🔴 RED → Phase 2b 后自动恢复（无 fork patch 需要）。Gate 1.5 audit 时此 17 个 test 仍 skip，Gate 1.5 audit report 需 inline `--ignore` 决策（按 §5A multi-source method consistency）。

### 6.4 A17 AMBER → ✅ CLOSED（项目负责人 §2 4 项评估完成）

**触发**：项目负责人 EOD A17 风险评估要求（≤10 min inline）。

**4 项评估答复**：

- Q1 同源根因：✅ 同源（8 errors 全部 `fixture 'mocker' not found`）
- Q2 真实行为变化 vs 机械过期：✅ **测试基础设施问题**（pytest-mock + responses package 未装入 venv）
- Q3 Phase 1c regression：❌ **NOT regression**（pyproject.toml 含 dependency，是 Layer 1 venv 重建 `uv sync --all-extras` 未含 test group dep）
- Q4 涉及 PR：❌ 不涉及任何 PR — 是 venv 配置 issue

**分流决议**：🟢 安全 → 立即修复（不 deferred Gate 1.5）

**修复**：`uv pip install pytest-mock responses`
**实测**：CLI baseline `3835 PASS + 8 errors + 1 fail` → `3848 PASS + 0 errors + 1 fail`

**来源轨道**：Track A Forward-driven。
**严重度**：🟡 AMBER → ✅ **CLOSED**

### 6.4-bis A18 NEW AMBER — CLI test_chat_input.py 1 fail (独立 issue)

**5 维度（立规 §2.4 v2）**：

1. **发现内容**：`test_chat_input.py::TestSlashCompletionCursorMapping::test_click_completion_at_end_updates_hint_without_extra_frame` — 1 个独立 fail，与 A17 (`mocker` fixture) 不同源。
2. **修复方式**：Gate 1.5 阶段深入分析 — 涉及 `TestSlashCompletionCursorMapping` 测试类（slash completion + cursor mapping），可能与 Phase 1b #3037 modified backspace + #3068 textual themes + Phase 1c #3026 ctrl+m shadowing 之一关联。
3. **来源轨道**：Track A Forward-driven（A17 修复后 baseline 浮现）。
4. **审计可追溯**：pytest output `FAILED tests/unit_tests/test_chat_input.py::TestSlashCompletionCursorMapping::test_click_completion_at_end_updates_hint_without_extra_frame`。
5. **严重度判定**：🟡 AMBER（1 fail / 3848 PASS = 0.026% fail rate；不阻塞 Phase 2，Gate 1.5 audit 必须解决）。

### 6.5 立规 §2.4 Comparative-driven 触发记录

A15 是立规 §2.4（自 2026-05-06 项目负责人裁决生效）的**首次触发实证**：

- Forward-driven Phase 1c 41 cherry-picks 全部 GREEN
- Comparative-driven 对比 Phase 1b vs 1c 同文件 take theirs 副作用 → 发现 class 数差异 → A15 暴露
- 验证项目负责人立规价值：comparative gap 在 forward-driven 视角不可见

---

## 7. Phase 2 + 后续 Phase 新增 skip PR（占位）

Phase 2a-2f 完成时，如有新增 skip PR：
- 加入本文档 §1/§5 对应 Group
- 走 §2 决策树

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
