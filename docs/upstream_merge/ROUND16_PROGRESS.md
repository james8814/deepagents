# Round 16 上游合并进度

**分支**：`upstream-sync-round16`
**Backup tag**：`backup-pre-round16` → `bbed0d50`
**起始**：2026-05-05（项目负责人 6 项裁决签署后立即启动）

---

## 总体进度（**2b 末端化重排** — 专家组 2026-05-05 裁决）

| Phase | 状态 | commits | 实测耗时 | cherry-pick 比 |
|---|---|---|---|---|
| Stage A 准备 | ✅ 完成 | docs only | — | — |
| Phase 1a: chore(deps) | ✅ 完成 | 6/7 picked + 1 skip | ~30 min | 85.7% |
| Phase 1b: CLI feat/fix | ✅ 完成 | 17/23 picked + 6 skip | ~30 min | 73.9% |
| Phase 1c: Evals/CI/Style/Test | ⏸️ 待启动 | 51 | est 1h | — |
| Gate 1 单测基线 | ⏸️ 待启动 | — | est 0.5h | — |
| Phase 2a: SDK low-conflict | ⏸️ 待启动 | 3 | est 1h | — |
| Phase 2c: filesystem/permissions | ⏸️ 待启动 | 2 | est 1h | — |
| Phase 2d: skills.py | ⏸️ 待启动 | 1 | est 0.5h | — |
| Phase 2e: subagents.py | ⏸️ 待启动 | 1 | est 0.5h | — |
| Phase 2f: sandbox | ⏸️ 待启动 | 1 | est 0.5h | — |
| **Gate 1.5 (committee audit)** | ⏸️ 待启动（指令 \[4\]，技术性 audit） | — | est 1h | — |
| **⏸️ Hold at 2b** | **等 Gate 1.5 PASS + Phase 2b 三重前置（pmagent 桶 2 / Path C 窗口 / dry-run baseline）** | — | — | — |
| **Phase 2b ⚡: profiles API trigger** | **预约窗口内 push（指令 \[5\] 三重前置全闭环后）** | 2 | est 2-3h | — |
| Gate 2 红线 | ⏸️ 待启动 | — | est 1.5h | — |
| 跳过 release | — | 23 | — | — |
| 跳过 quickjs (DUS 自然继承) | — | 11 | — | — |

**重排理由**：原 2b 中段位置与 Path C scheduled cutover window 几乎不可能匹配。2b 末端化让 CTO 完成所有非-2b 工作后 Hold，等预约窗口触发 push。详见 ROUND16_RISK_ASSESSMENT.md §6.1/§6.2 依赖审视。

---

## Phase 1a 详细记录（已完成）

### 决策矩阵

| PR | 类型 | 处理 | commit hash | 冲突 |
|---|---|---|---|---|
| #3028 | workflows minor-and-patch (5 yml) | ✅ cherry-pick | bfa1d7a1 | 0 |
| #3029 | release-please-action 4→5 (1 yml) | ✅ cherry-pick | 80bb34ef | 0 |
| #3030 | github-script 8→9 (11 yml) | ✅ cherry-pick | e06a3aec | 2 (resolved) |
| #3000 | anthropic min ver 1.4.0→1.4.2 | ✅ cherry-pick | 42c4aae5 | 3 (resolved) |
| #3018 | langchain ecosystem bumps | ✅ cherry-pick | 5ca7ee8c | 3 (resolved) |
| #3052 | notebook 7.4.7→7.5.6 (deep_research example) | ✅ cherry-pick | 778f3f0d | 0 |
| #2451 | litellm 1.82.1→1.83.0 (cli/uv.lock) | ⏭️ **skip (no-op)** | — | "all conflicts fixed" empty |

**Cherry-pick 比**：6/7 = **85.7%**

### #2451 skip 原因（实证）

```
$ grep -A1 "^name = \"litellm\"$" libs/cli/uv.lock
name = "litellm"
version = "1.83.0"
```

Fork `libs/cli/uv.lock` 已经是 1.83.0（通过 #3000/#3018 lockfile 传递性更新或 fork 独立 `uv lock`）。Cherry-pick 显示 "all conflicts fixed" 但 staged tree == HEAD（无 patch 应用）→ skip 是正确决策。

### 冲突解决决策（共 8 个，3 类模式）

#### 模式 1：fork 已删除 workflow 文件（modify/delete）

| 文件 | 出现于 | 决策 |
|---|---|---|
| `.github/workflows/release_please_parse_check.yml` | #3030 | `git rm` — 保留 fork 历史决策（PR #3001 `ec0ddfbb` 引入该文件，未被 fork cherry-pick；待 Phase 1c 处理 #3001 时一并） |

#### 模式 2：fork 不含 examples 目录（deleted by us）

| 文件 | 出现于 | 决策 |
|---|---|---|
| `examples/repl_swarm/uv.lock` | #3000, #3018 | `git rm` — fork master 不含 `examples/repl_swarm/` 目录（实证：`git ls-tree master examples/`） |
| `examples/rlm_agent/uv.lock` | #3000, #3018 | `git rm` — 同上 |

#### 模式 3：quickjs partial state（both modified）

| 文件 | 出现于 | 决策 |
|---|---|---|
| `libs/partners/quickjs/uv.lock` | #3000, #3018, #3030 | `git checkout --ours` — 按 ROUND16_RISK_ASSESSMENT §4 quickjs 留给 DUS 自然继承决策，fork 不主动 sync quickjs 内容 |

#### 模式 4：fork pr_lint.yml 不含 warn-on-bypass job

| 文件 | 出现于 | 决策 |
|---|---|---|
| `.github/workflows/pr_lint.yml` | #3030 | `git checkout --ours` — fork 该 workflow 不含 upstream 后续添加的 `warn-on-bypass` job，#3030 的 `actions/github-script` 版本 bump 对 fork 无 base 可应用 |

---

## Phase 1a 实测 vs 估时

| 项 | 估时 | 实测 |
|---|---|---|
| Phase 1a 总耗时 | 0.5h | ~30 min ✅ |
| Cherry-pick 比 | 100% (assumed) | **85.7%（实测）** |
| 冲突数 | 0 (assumed) | **8（实测）** |

**校准信号**：fork lockfile 独立管理路径产生了 1 个 no-op skip + 6 个真实冲突需手动解决。这是 Round 16 估时的关键 calibration — 后续 Phase 估时可能需要类似 buffer。

---

## Phase 1b 详细记录（已完成）

### 决策矩阵（17/23 cherry-picked + 6 skipped）

| PR | 主题 | 处置 | 备注 |
|---|---|---|---|
| #2940 | bundled chat frontend | ✅ cherry-pick | 0 冲突 |
| #3017 | startup import deadlock | ✅ cherry-pick | 0 冲突 |
| #3033 | broken filesystem permissions import | ✅ cherry-pick | 0 冲突 |
| #3037 | modified backspace word deletion | ✅ cherry-pick | 1 冲突（test_chat_input.py，take theirs）|
| #2427 | prevent stdin hang via DEVNULL | ✅ cherry-pick | 0 冲突 |
| #3039 | reject out-of-tree symlinked AGENTS.md | ✅ cherry-pick | 0 冲突 |
| #2906 | rework MCP integration + OAuth login | ✅ cherry-pick | 1 冲突（mcp_viewer.py，take theirs theme）|
| #2835 | allowedTools/disabledTools MCP filters | ✅ cherry-pick | 0 冲突 |
| #3056 | recover from failed server startup | ✅ cherry-pick | 0 冲突 |
| #3068 | auto-discover Textual built-in themes | ✅ cherry-pick | 1 冲突（welcome.py，take theirs ansi 多 theme）|
| #3072 | apply --model-params on /model re-select | ✅ cherry-pick | 0 冲突 |
| #3094 | gate async task tools by actual names | ✅ cherry-pick | 0 冲突 |
| #3097 | hide approval menu on selection | ✅ cherry-pick | 0 冲突 |
| #3108 | preserve recent agent across thread resume | ✅ cherry-pick | 0 冲突 |
| #3144 | show detached HEAD commit in local context | ✅ cherry-pick | 0 冲突 |
| #3152 | surface MCP config discovery paths | ✅ cherry-pick | 0 冲突 |
| #3153 | /reload skill diff report | ✅ cherry-pick | 0 冲突 |
| #2962 | honor ProviderProfile in create_model | ⏭️ **skip** | 依赖 #2892（Phase 2b stack），后置 |
| #3106 | move internal state under hidden directory | ⏭️ **skip** | agent.py + main.py 双冲突，fork 架构分歧 |
| #3102 | first-run onboarding flow | ⏭️ **skip** | 依赖 fork 已删除的 state_migration.py |
| #3111 | richer provider auth states | ⏭️ **skip** | config.py + 2 文件冲突，与 #2962 关联 |
| #3126 | set-as-default in /agents picker | ⏭️ **skip** | main.py + welcome.py 二次冲突 |
| #3123 | in-TUI API key entry via /auth | ⏭️ **skip** | command_registry.py + model_config.py 冲突 |

**Cherry-pick 比**：17/23 = **73.9%**

### 6 skip PR 后置策略

- **#2962**：Phase 2b cherry-pick #2892 后立即处理（依赖解锁）
- **#3106 / #3102 / #3111 / #3126 / #3123**：fork 架构分歧（state migration / config / agents picker），需在桶 7 ADR/文档阶段重新评估或留给桶 2.6 NEW post-cutover 处理

### 冲突解决决策（共 3 个非 skip 类）

| 文件 | PR | 决策 |
|---|---|---|
| `tests/unit_tests/test_chat_input.py` | #3037 | take theirs（fork 没有这段，upstream 添加新 test class） |
| `widgets/mcp_viewer.py` | #2906 | take theirs（upstream theme.get_theme_colors 优于 fork hardcoded "green"） |
| `widgets/welcome.py` | #3068 | take theirs（upstream ansi 多 theme 支持是 #3068 主旨）|

---

## Phase 1a/1b 实测 vs 估时

| Phase | 估时 | 实测 | Cherry-pick 比 | 冲突数 |
|---|---|---|---|---|
| Phase 1a | 0.5h | ~30 min ✅ | 85.7% (6/7) | 8 |
| Phase 1b | 2h | ~30 min ⭐ | 73.9% (17/23) | 9（5 解决 + 6 skip）|

**Phase 1b 节奏放大效应**：估时 2h，实测 ~30 min — 4 倍提速。原因：Phase 1b 多数 cherry-pick 0 冲突（CLI 局部变更），且 6 skip 决策快速（依赖 fork 架构分歧识别即可）。

**校准更新**：后续 Phase 估时可能继续偏保守。但 Phase 2 SDK 簇会触及 11 项本地特性父类，冲突复杂度预期上升，估时 buffer 仍需保留。

---

## 当前 commit 链（upstream-sync-round16）

```
778f3f0d chore(deps): notebook 7.4.7→7.5.6                ← HEAD
5ca7ee8c chore(deps): langchain ecosystem bumps
42c4aae5 chore(deps): anthropic min ver 1.4.0→1.4.2
e06a3aec chore(deps): github-script 8→9 (+2 conflicts resolved)
80bb34ef chore(deps): release-please-action 4→5
bfa1d7a1 chore(deps): minor-and-patch group
3f28d796 docs(round16): Stage B 启动准备
bbed0d50 docs(architecture): A 组 spec 修订（master + backup-pre-round16）
```

---

## Refs

- 多专家组评审 APPROVE
- pmagent 桶 1 验收报告
- v3.2.1 §3.3/§5A.1/§6.1/§11/§12
- ADR v5 #16/#17/#19/#20/#22
- Round 14/15 cherry-pick proven 模式

**生成者**：CTO（deepagents fork）
**Phase 1a 完成时间**：2026-05-05 T+30 min（项目负责人授权后）
