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
| Phase 1b: CLI feat/fix | ⏸️ 待启动（下次会话） | 20 | est 2h | — |
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

## 下一步

| 选项 | 描述 |
|---|---|
| α | 立即启动 Phase 1b（20 CLI feat/fix，est 2h） |
| β | 暂停于 Phase 1a 完成，下次会话恢复 |

**推荐 β** — 单会话执行 9.5-11h Stage B 不现实；当前 Phase 1a 完成已是清洁里程碑（commit 链：`3f28d796` startup → `778f3f0d` Phase 1a 收尾），可作为下次会话恢复的稳定 checkpoint。

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
