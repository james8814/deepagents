# Round 9 合并日志

**日期**: 2026-03-28~29
**分支**: `upstream-sync-round9`
**范围**: 42 upstream commits + 2 local fixes = 44 total
**统计**: 78 files changed, +5442/-1554

---

## 合并概览

| Phase | Commits | 冲突 | 状态 |
|-------|---------|------|------|
| A: SDK | 3 | 0 | ✅ |
| B: CLI small | 12 | 3 (config.py, app.py, command_registry.py) | ✅ |
| C: CLI large | 3 | 2 (thread_selector.py, commands.py) | ✅ |
| D: env var prefix | 1 | 2 (config.py, test_textual_adapter.py) | ✅ |
| E: trace fragmentation | 1 | 2 (agent.py, test_agent.py) | ✅ |
| F: deps bump | 22 | 0 | ✅ |
| **fix commit** | 1 | - | ✅ |

---

## 冲突解决记录

### config.py (commits 5, 19) — 热点文件
- **Commit 5**: 上游重构 `config` 变量格式 + 加 `_get_git_branch` + `build_stream_config`。本地已有这些函数（Round 7 迁移）。
  - 解决：保留本地函数位置，接受 `config` 格式化 + `ls_integration` 添加
- **Commit 19**: 上游 env var prefix 大改。config.py 无冲突标记（auto-merge），但需验证功能完整性。
  - 解决：确认 `_env_vars.py`, `resolve_env_var`, LANGSMITH 传播全部到位

### command_registry.py (commits 8, 13)
- **Commit 8**: `/upload`（本地）+ `/auto-update`（上游）合并。
  - 解决：两者都保留，加 `/changelog`
- **Commit 13**: `/trace` bypass_tier 从 QUEUED → SIDE_EFFECT_FREE。
  - 解决：接受上游新 tier，删除旧重复项

### app.py (commit 8)
- `/upload` 和 `/auto-update` 都需要在 help body 中。
  - 解决：合并为一行，分行避免 E501

### commands.py (commit 18)
- 上游用 `theme.MUTED` 替代 `COLORS["dim"]`。
  - 解决：接受上游主题化 + 接受 `SystemExit(1)` 替代 `return`

### agent.py (commit 20)
- 上游加 `AgentMiddleware`, `theme`, `_ShellAllowAll` imports。本地有 `COLORS`。
  - 解决：全部保留

### test_agent.py (commit 20)
- 上游加大量新测试（~500行）。
  - 解决：全部接受

---

## 修复记录（合并后）

### Lint 修复
- `commands.py`, `ui.py`: 添加缺失的 `from deepagents_cli import theme` import
- `app.py`: E501 行太长 → 拆行
- `config.py`: E303 多余空行 → ruff --fix
- `thread_selector.py`: F401 未使用的 theme import → ruff --fix

### 测试修复
- `test_command_registry.py`: 正则从 `/[a-z]+` → `/[a-z][-a-z]*`（匹配 `/auto-update`）
- `test_command_registry.py`: 删除重复的 `/changelog`，`/auto-update` 移至字母序正确位置
- `test_env_vars.py`: 添加 UTF-8 decode error handling（macOS 外部卷 resource fork）
- `test_model_config.py`: `test_explicit_models_list_skips_auto_discovery` 用 `my_custom_provider` 替代 `baseten`（baseten 在 langchain-core 1.2.22 中被加入 registry，破坏了原有假设）
- `test_agent.py`: 删除 `TestLsEntriesShim` 整个 class（`_ls_entries` shim 已不存在，提醒测试使命完成）

---

## 测试结果

| 套件 | 结果 | 环境 |
|------|------|------|
| SDK unit tests | 1019 passed, 73 skipped, 3 xfailed | --reinstall clean venv |
| CLI unit tests | 2744 passed, 1 skipped | --reinstall clean venv |
| Evals unit tests | 158 passed | --reinstall clean venv |
| SDK lint | ✅ All checks passed | — |
| CLI lint | ✅ All checks passed | — |

---

## SHA 映射表（方案 → 实际）

Cherry-pick 会产生新 SHA。以下映射确保方案中的 commit 引用可追溯到实际分支历史。

| 方案 SHA (upstream) | 实际 SHA (cherry-pick) | 描述 |
|---|---|---|
| `fd91a30b` | `28c3a860` | fix(sdk): update recursion limit |
| `5e23d6d9` | `1ec84532` | chore(sdk): declare schema for remaining tools |
| `34cb7aab` | `15ab488e` | chore(sdk): compaction test + schema revert |
| `e859077f` | `b5bc23e2` | fix(cli): exit on ctrl+d empty thread |
| `5dd80983` | `adce7872` | feat(cli): ls_integration metadata |
| `8f718650` | `d53e8c2d` | feat(cli): color overrides on themes |
| `a3b61e5d` | `41c29a1d` | fix(cli): warn filesystem inaccessible |
| `ad70bde0` | `f671da43` | feat(cli): /auto-update toggle |
| `15867bfa` | `dd88eaa4` | fix(cli): disable markup blocked-link |
| `7178b872` | `5aa35d9e` | feat(cli): default langsmith project |
| `28a32b7d` | `4e04530b` | fix(cli): enforce approval with -y |
| `7f5c3de9` | `aab98145` | perf(cli): reduce health poll interval |
| `b4520324` | `40bd7500` | fix(cli): open trace immediately |
| `42bccca0` | `0eb7b400` | fix(cli): escape exception markup |
| `744b81b3` | `0e3a2f76` | chore: sync lockfiles |
| `0a410b4a` | `d606551a` | perf(cli): defer imports |
| `5a21d0ad` | `bc463816` | feat(cli): global dotenv |
| `386438f6` | `c73fb55a` | feat(cli): agent-friendly UX |
| `29647bb4` | `f339ab3a` | feat(cli): DEEPAGENTS_CLI_ prefix |
| `9bddc52b` | `ea91cf6d` | fix(cli): trace fragmentation |

（22 个 deps bump commits 略，commit message 完全一致可直接 `git log --grep` 查找）

---

## 本地优越特性保留确认

| 特性 | 状态 |
|------|------|
| SkillsMiddleware V2 (load_skill/unload_skill) | ✅ |
| Converters (PDF/DOCX/XLSX/PPTX) | ✅ |
| upload_adapter V5 | ✅ |
| Overwrite import (summarization) | ✅ |
| state_schema param (graph.py) | ✅ |
| SubAgent logging | ✅ |
| /upload command | ✅ |
| build_stream_config 本地位置 | ✅ |

---

## 新增上游特性 (Round 9)

### SDK
1. **recursion_limit**: 10000 → 10001
2. **Pydantic Schema for subagents**: TaskToolSchema, async subagent schema
3. **Compaction E2E test** + summarization schema 回退

### CLI
4. **DEEPAGENTS_CLI_ env var prefix**: 支持带前缀的 env var 覆盖
5. **Global dotenv**: `~/.deepagents/.env` 全局配置
6. **Agent-friendly UX**: --dry-run, agents 子命令, --stdin, SystemExit codes
7. **Trace fragmentation fix**: ShellAllowListMiddleware, 非交互模式 trace 连贯
8. **Color overrides on themes**: 主题颜色可自定义
9. **/auto-update toggle**: 控制自动更新
10. **Defer pydantic/adapter imports**: 启动热路径优化
11. **Health poll interval**: 本地 dev server 轮询优化
12. **LangSmith trace improvements**: ls_integration metadata, 立即打开 trace
13. **Rich markup escape**: 异常文本转义防止 markup 注入
14. **ctrl+d exit**: 空线程列表时 ctrl+d 退出

### Dependencies
15. **cryptography**: 46.0.5 → 46.0.6 (10 packages)
16. **langchain-core**: → 1.2.22 (12 packages)
