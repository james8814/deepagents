# Round 16 Risk Assessment

**生成**：2026-05-05
**触发**：项目负责人 6 项裁决签署 + Stage A 准备完成
**作用域**：master..upstream/main 真实差异（128 PR PR# 去重后）

---

## 1. 范围概要

| 指标 | 数字 |
|---|---|
| `master..upstream/main` 表面 commits | 502 |
| upstream unique PRs | 503 |
| 已 cherry-pick 进 master 的 PR | 375 |
| **真实待 sync PR** | **128** |
| 时间跨度 | 2026-03-26 → 2026-05-04 |

**Round 14 / 15 用 cherry-pick 模式 → hash 不同但内容相同**，导致表面 502 vs 真实 128 的 -75% 工作量降幅。

---

## 2. 128 PR 分类

| 类别 | 数量 | 处理 |
|---|---|---|
| `release(*)` | 23 | 跳过（fork 不发版） |
| `chore(deps)` | 7 | 自动接受 |
| `feat/fix(cli)` | 20 | 中风险 |
| `feat/fix(sdk)` | 10 | **🔴 高风险** |
| `feat/fix(quickjs)` | 11 | **决策：留给 DUS 自然继承（项目负责人 #4 签署）** |
| `feat/fix(evals)` | 6 | 低风险 |
| ci/style/test/其他 | 51 | 低风险 |

---

## 3. 🔴 高风险 SDK PR（10 个）

| PR | 标题 | 影响文件 | 与 fork 冲突点 |
|---|---|---|---|
| #2892 | feat(sdk): profiles API | `profiles/` | **fork `_HarnessProfile` 8 fields → upstream `HarnessProfile` 7 fields 重构** |
| #3082 | feat(sdk): GPT-5.5 harness profile | `profiles/_openai.py` | 依赖 #2892 |
| #3036 | fix(sdk): re-export filesystem permission | `permissions.py` + `__init__.py` | pmagent 31 处 import 必须不变 |
| #3035 | fix(sdk): harden FilesystemBackend symlink | `backends/filesystem.py` | filesystem.py 12 次修改之一 |
| #2976 | feat(sdk): optional module field in skill frontmatter | `middleware/skills.py` | fork V2 (1197 行) |
| #2991 | fix(sdk): read-your-writes in StateBackend | `backends/state.py` | pmagent 57 处用法行为审计 |
| #2980 | fix(sdk): boundary-truncated UTF-8 in read() | `backends/*.py` | read 路径 |
| #3031 | fix(sdk): EOF-newline mismatch in edit_file | `backends/*.py` | edit 路径 |
| #3045 | fix(sdk): propagate CompiledSubAgent name | `middleware/subagents.py` | fork `_ENABLE_SUBAGENT_LOGGING` |
| #2695 | fix(sdk): write preflight + native read langsmith sandbox | `backends/sandbox.py` | sandbox |

---

## 4. 🟢 quickjs 决策 — 留给 DUS 自然继承（已 sign-off）

**项目负责人 #4 签署**：留给 DUS 自然继承。

### 4.1 fork 当前状态：partial（24 git-tracked 文件）

```
libs/partners/quickjs/CHANGELOG.md
libs/partners/quickjs/LICENSE
libs/partners/quickjs/Makefile
libs/partners/quickjs/README.md
libs/partners/quickjs/pyproject.toml
libs/partners/quickjs/uv.lock
libs/partners/quickjs/langchain_quickjs/__init__.py
libs/partners/quickjs/langchain_quickjs/middleware.py
libs/partners/quickjs/langchain_quickjs/_foreign_function_docs.py    ← deprecated（upstream removed）
libs/partners/quickjs/langchain_quickjs/_foreign_functions.py        ← deprecated
libs/partners/quickjs/langchain_quickjs/_version.py                  ← deprecated
libs/partners/quickjs/tests/__init__.py
libs/partners/quickjs/tests/unit_tests/__init__.py
libs/partners/quickjs/tests/unit_tests/chat_model.py                 ← deprecated
libs/partners/quickjs/tests/unit_tests/smoke_tests/__init__.py
libs/partners/quickjs/tests/unit_tests/smoke_tests/conftest.py
libs/partners/quickjs/tests/unit_tests/smoke_tests/snapshots/quickjs_system_prompt_mixed_foreign_functions.md
libs/partners/quickjs/tests/unit_tests/smoke_tests/snapshots/quickjs_system_prompt_no_tools.md
libs/partners/quickjs/tests/unit_tests/smoke_tests/test_system_prompt.py
libs/partners/quickjs/tests/unit_tests/test_end_to_end.py
libs/partners/quickjs/tests/unit_tests/test_end_to_end_async.py
libs/partners/quickjs/tests/unit_tests/test_foreign_function_docs.py ← deprecated
libs/partners/quickjs/tests/unit_tests/test_import.py                ← deprecated
libs/partners/quickjs/tests/unit_tests/test_system_prompt.py         ← deprecated
```

### 4.2 7 个 deprecated 文件 cutover 覆盖声明（残留风险 #3 闭环）

以下 7 个文件在 fork master 存在，但已被 upstream refactor/移除：

```
libs/partners/quickjs/langchain_quickjs/_foreign_function_docs.py
libs/partners/quickjs/langchain_quickjs/_foreign_functions.py
libs/partners/quickjs/langchain_quickjs/_version.py
libs/partners/quickjs/tests/unit_tests/chat_model.py
libs/partners/quickjs/tests/unit_tests/test_foreign_function_docs.py
libs/partners/quickjs/tests/unit_tests/test_import.py
libs/partners/quickjs/tests/unit_tests/test_system_prompt.py
```

**声明**：DUS 切换后，pmagent submodule 直接指向 upstream/main，这 7 个文件**不会被携带**。这是预期行为（upstream 已 deprecate / refactor），**不视作丢失**。

**Round 16 sync 不主动删除**这 7 个文件（避免 fork master 与 sync 分支 diff 噪声），保持 partial state 直至 Phase 2 fork 归档。

### 4.3 16 upstream-only 文件（不纳入 Round 16）

```
langchain_quickjs/_format.py / _prompt.py / _ptc.py / _repl.py / _skills.py / py.typed
tests/benchmarks/{_common, test_quickjs_memory, test_quickjs_throughput}.py
tests/integration_tests/{__init__, test_rlm}.py
tests/unit_tests/{test_ptc, test_repl_middleware, test_skills, test_skills_integration, test_snapshot_persistence}.py
```

**Round 16 不引入**这 16 文件 — pmagent 0 quickjs 业务依赖（grep 实证）。DUS 切换时直接由 upstream 携带。

---

## 5. 11 项本地优越特性受影响频次

| 文件 | upstream 修改频次 | 风险评级 |
|---|---|---|
| `graph.py` | **19** | 🔴 最高 |
| `filesystem.py` | 12 | 🟡 |
| `subagents.py` | 10 | 🟡 |
| `summarization.py` | 10 | 🟡 |
| `permissions.py` | 6 | 🟡 |
| `skills.py` | 6 | 🟡 |
| `profiles/*` | 5 | 🔴 含 #2892 重构 |
| `memory.py` | 1 | 🟢（v3.2.1 桶 0 已 skip） |
| `converters/*` | **0** | 🟢 fork-only 安全 |
| `upload_adapter.py` | **0** | 🟢 fork-only 安全 |

---

## 6. Phase 划分（4 Phase + 2 Gate，**2b 末端化重排**）

> **专家组裁决（2026-05-05）**：原顺序 2a→2b→2c→2d→2e→2f 在 Phase 2b 出现于 Stage B 中段（~T+5h），与 Path C scheduled cutover window 几乎不可能匹配。**采用 2b 末端化重排**：将 #2892 profile API 移到 Phase 2 末尾，之前所有 SDK 簇先完成 → Hold at 2b → 等预约窗口 → push。

| Phase | 内容 | commits | 估时 | 风险 |
|---|---|---|---|---|
| 1a | chore(deps) bumps | 7 | 0.5h | 🟢 ✅ 完成 |
| 1b | CLI feat/fix（与 SDK 解耦） | 20 | 2h | 🟢 |
| 1c | Evals/CI/Style/Test | 51 | 1h | 🟢 |
| **Gate 1** | 单测基线 | — | 0.5h | — |
| 2a | SDK low-conflict (#2991/#2980/#3031) | 3 | 1h | 🟡 ⚠️ filesystem.py |
| 2c | filesystem/permissions 簇 (#3035/#3036) | 2 | 1h | 🟡 ⚠️ filesystem.py |
| 2d | skills.py 簇 (#2976) | 1 | 0.5h | 🟡 ⚠️ empty commit 预案 |
| 2e | subagents.py 簇 (#3045) | 1 | 0.5h | 🟡 |
| 2f | sandbox (#2695) | 1 | 0.5h | 🟡 |
| **Gate 1.5** | 委员会 audit（指令 \[4\]：11 项保护 + read-your-writes + permission re-export） | — | 1h | — |
| **⏸️ Hold at 2b** | **等 Gate 1.5 PASS + Phase 2b 三重前置（指令 \[5\]） + Path C 预约窗口确认** | — | — | — |
| **2b ⚡** | **profiles API 簇 (#2892 + #3082) atomic cutover trigger** ← **预约窗口内 push** | 2 | 2-3h | 🔴 |
| **Gate 2** | 11 + 3 红线（含专家组追加） | — | 1.5h | — |
| 跳过 | release commits | 23 | — | — |
| 跳过（DUS 自然继承） | quickjs 11 PR | 11 | — | — |

**总估时**：12-14h（含 25% buffer）≈ 1.5-2 d，**+ 预约窗口等待时间**（视 Path C 窗口安排）。

### 6.1 重排理由

| 旧顺序问题 | 新顺序优势 |
|---|---|
| 2b 在中段，CTO 工作进度难精确对齐预约窗口 | 2b 末端化，CTO 完成所有非-2b 工作后 Hold，等预约窗口触发 |
| Phase 2c-2f 依赖 2b 重构（profile API → public） | 验证：2c-2f 5 个 SDK 簇是否确实依赖 #2892？逐项审视下方 §6.2 |
| atomic cutover 触发与工作进度耦合 | 解耦：cutover 触发 = 预约窗口 + pre-condition gate，工作进度 = CTO 自决 |

### 6.2 依赖审视（重排可行性）

| Phase | 是否依赖 #2892 (profile API) | 重排可行 |
| --- | --- | --- |
| 2a (#2991/#2980/#3031) | StateBackend / read 路径，与 profiles 无关 | ✅ |
| 2c (#3035/#3036) | filesystem/permissions，与 profiles 无关 | ✅ |
| 2d (#2976) | skills.py 加 module 字段，与 profiles 无关 | ✅ |
| 2e (#3045) | subagents.py CompiledSubAgent name，与 profiles 无关 | ✅ |
| 2f (#2695) | langsmith sandbox，与 profiles 无关 | ✅ |

**结论**：5 个 SDK 簇均与 #2892 解耦，重排不引入额外冲突。可在 Hold at 2b 之前完成全部 5 个 SDK 簇。

### 6.3 跨 Phase filesystem.py 修改 flag（深度审计 A4）

**事实**：Phase 2a 与 Phase 2c 都涉及 `libs/deepagents/deepagents/backends/filesystem.py`：

| Phase | PR | 改动行段 | 主题 |
| --- | --- | --- | --- |
| 2a | #3031 | line 13（imports）+ line 375（write 路径） | EOF-newline mismatch in edit_file |
| 2c | #3035 | line 1（imports）+ line 168/180（resolve 路径） | symlink 防御 (ELOOP) |

**风险评级**：🟡 中——两 PR 改不同行段，cherry-pick 顺序 2a → 2c **预期 auto-merge**。

**监控点**：

- Phase 2c cherry-pick #3035 时若出现 `filesystem.py` conflict → 说明 #3031 与 #3035 行段重叠（与本审计预测不符），需手动 review
- Gate 1 单测必须含 `tests/unit_tests/backends/test_filesystem_backend.py` 全套，验证 #3031 与 #3035 综合行为正确

### 6.4 #2976 empty commit 预案（深度审计 A5）

**事实**：`git diff 2a9cd44f^ 2a9cd44f --stat` 返回空，commit object 存在但无文件 diff（git 异常或 squash merge 副作用）。

**预案**：

- Phase 2d cherry-pick 出现"all conflicts fixed"无内容时，按 #2451 同模式 `git cherry-pick --skip`
- skip 决策记录到 ROUND16_PROGRESS.md Phase 2d 行

---

## 7. atomic cutover SLA（#5 签署）

**触发点**：Phase 2b push（包含 #2892 + #3082）

**SLA**：
1. CTO `git push` 包含 #2892
2. CTO ≤5 min 内通知 pmagent（HEAD hash + `git diff --stat` + breaking change 行号）
3. pmagent ≤30 min 内执行桶 4（11 处 import）+ 桶 5（8 处 `_resolve_extra_middleware`）切换
4. 业务停服窗口 ≤30 min

**前置确认**：CTO push #2892 前必须在协调群确认 pmagent 团队在岗（残留风险 #1）。

---

## 8. 回滚计划（per-phase）

```bash
# 任一 Phase 失败：
git checkout upstream-sync-round16
git revert <failing_commit>
# 或全 Phase 回退：
git reset --hard backup-pre-round16  # 仅在 sync 分支安全
```

**禁止**：在 master 上做 reset --hard。master 永远只接收 sync 分支的 fast-forward merge（Phase 全 GREEN 后）。

---

## 9. Refs

- 多专家组评审 APPROVE 报告
- pmagent 桶 1 验收报告 §6/§12
- v3.2.1 §3.3/§5A.1/§6.1/§11/§12
- ADR v5 #16/#17/#19/#20/#22

**生成者**：CTO（deepagents fork）
**状态**：Stage B Phase 1a 启动前评估完成
