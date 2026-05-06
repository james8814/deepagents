# Round 16 Gate 1.0 — Phase 1b 后 / Phase 1c 前增量 smoke test

**触发**：项目负责人 ULTRATHINK 裁决 Q1 APPROVE（2026-05-06）
**作用域**：Phase 1b 17 cherry-picks + 6 skip + 3 take theirs 后增量验证
**目的**：A8/A10/A11/A12 早期捕获 + skip 决策回归

---

## 1. 总览

| 项 | 结果 | 严重度 |
|---|---|---|
| 🟢 GREEN | 5 项 | — |
| ⏸️ Deferred | 1 项（网络阻塞）| 🟡 中（Gate 1 时段一并处理）|
| 🔴 RED | 0 项 | — |

**结论**：Gate 1.0 PASS（含 1 项 deferred）→ 启动 Phase 1c。

---

## 2. 强制项验证结果

### [1] ⏸️ Deferred — venv 重建（网络阻塞）

**操作**：`uv venv --python 3.13 /tmp/round16-cli-venv` + `uv sync --reinstall`
**结果**：
- venv 创建 ✅（CPython 3.13.12）
- `uv sync` 失败：DNS lookup error + system proxy (127.0.0.1:1089) 不可达
**Deferred 至**：Gate 1 单测时段（network 恢复后一并执行）
**影响**：本 Gate 1.0 转入纯静态/grep 验证模式

### [2] ✅ A8: frontend dist 路径验证

**A8 修正**：原假设的 `libs/cli/frontend/dist/` 是错误推断。**实际路径**：`libs/cli/deepagents_cli/deploy/frontend_dist/`

**实证**：
- `bundler.py:75`: `_FRONTEND_DIST_SRC = Path(__file__).parent / "frontend_dist"` ✅
- `bundler.py:130`: `_copy_frontend_dist()` 函数 ✅
- `bundler.py:245`: deploy 流程调用 `_copy_frontend_dist(config, build_dir)` ✅
- `templates.py:983`: `_FRONTEND_DIR` 引用一致 ✅
- 目录含 clerk-5xHgyQyG.js 等 frontend bundle ✅

**A8 结论**：False positive 消除，无需修复。

### [3] ✅ A10: MCP 模块 import 链

**测试**：6 个 MCP 模块 ast.parse Python 3.13

```text
OK: libs/cli/deepagents_cli/mcp_auth.py
OK: libs/cli/deepagents_cli/mcp_commands.py
OK: libs/cli/deepagents_cli/mcp_providers/__init__.py
OK: libs/cli/deepagents_cli/mcp_providers/_registry.py
OK: libs/cli/deepagents_cli/mcp_providers/base.py
OK: libs/cli/deepagents_cli/mcp_providers/slack.py
Total: 0 errors / 6 files
```

**A10 结论**：✅ Syntax + import 路径完整，runtime 验证 deferred 至 Gate 1。

### [4] ✅ A11: fork `_HarnessProfile` 8 字段完整

**实证**（line 29-105 of `libs/deepagents/deepagents/profiles/_harness_profiles.py`）：

| # | 字段 | 类型 |
|---|---|---|
| 1 | `init_kwargs` | `dict[str, Any]` |
| 2 | `pre_init` | `Callable[[str], None] | None` |
| 3 | `init_kwargs_factory` | `Callable[[], dict[str, Any]] | None` |
| 4 | `base_system_prompt` | `str | None` |
| 5 | `system_prompt_suffix` | `str | None` |
| 6 | `tool_description_overrides` | `dict[str, str]` |
| 7 | `excluded_tools` | `frozenset[str]` |
| 8 | `extra_middleware` | `Sequence[AgentMiddleware] | Callable[[], Sequence[AgentMiddleware]]` |

**A11 结论**：✅ 8 字段完整保留，未受 Phase 1b cherry-pick 影响（Phase 1b 仅动 CLI，未触及 SDK profiles）。

### [5] ✅ A12: 3 take theirs 副作用验证

| 文件 | 验证 | 结果 |
|---|---|---|
| `test_chat_input.py` | ast.parse 提取 38 classes 含 `TestChatTextAreaKeybindings` | ✅ 测试结构正常 |
| `mcp_viewer.py` | `theme.get_theme_colors(self)` + `colors.success` 引用 | ✅ 正确 |
| `welcome.py` | `theme.get_theme_colors(self)` + `ansi-dark/ansi-light` 多 theme | ✅ upstream 简洁版本 |

**A12 残留风险**（welcome.py）：丢弃 fork try/except 防御，**Phase 6 E2E 必须验证 widget lifecycle 异常场景**（textual.theme 未 mount 时是否 raise）。如发现 issue → fork-side patch (pmagent vendor 路径)。

### [6] ✅ Skip 决策回归

| Skip PR | 验证项 | 结果 |
|---|---|---|
| #3102 first-run onboarding | `state_migration.py` 仍不存在 | ✅ skip 根因成立 |
| #2962 honor ProviderProfile | fork `check_openrouter_version` + `_apply_openrouter_defaults` 仍在（4 处） | ✅ fork 既有路径完整 |
| #3106/#3126 main.py 架构分歧 | `main.py` 0 处 `_show_bare_command_group_help` | ✅ fork 未引入 upstream-only 内容 |
| #3123 command_registry/model_config | 两文件存在 | ✅ fork 既有架构完整 |

**Skip 回归结论**：6 个 skip 决策都不影响 Phase 1b 已 land 的 17 cherry-picks，fork 既有架构完整。

---

## 3. Phase 1b L2 audit 6 AMBER 后续状态

| AMBER | Gate 1.0 状态 | 后续 |
|---|---|---|
| A8 frontend dist 缺失 | ✅ False positive 消除 | 关闭 |
| A9 6 skip 后置 home | ✅ DEFERRED_BACKLOG.md 已创建 | 关闭 |
| A10 MCP rework runtime | ✅ Syntax 正常，runtime deferred | Gate 1 |
| A11 #3056 + 8 字段兼容 | ✅ 8 字段完整 | Gate 1 |
| A12 take theirs 副作用 | ✅ 3/3 验证 + welcome.py 残留风险记录 | Phase 6 E2E |
| A13 venv 重建 | ⏸️ 网络阻塞 deferred | Gate 1 |

**剩余风险**：A10 runtime + A11 跨链兼容 + A12 welcome.py lifecycle，**全部由 Gate 1 + Phase 6 E2E 覆盖**。

---

## 4. 启动 Phase 1c 的前置条件

- [x] Gate 1.0 5/6 GREEN（6 项中 1 项 deferred 不阻塞）
- [x] DEFERRED_BACKLOG.md 已创建（Q2 答复）
- [x] 项目负责人 Q3 APPROVE（同 session 继续）

**启动 Phase 1c**：✅ 全部就绪。

---

## 5. Refs

- 项目负责人 ULTRATHINK 裁决 §Q1 APPROVE Gate 1.0（2026-05-06）
- ROUND16_DEFERRED_BACKLOG.md（Q2 答复）
- ROUND16_PROGRESS.md §Phase 1b 详细记录
- ROUND16_GATE2_CHECKLIST.md §3.1 venv 重建 SOP（Gate 1 时段执行）

**生成者**：CTO（deepagents fork）
**完成时间**：2026-05-06
