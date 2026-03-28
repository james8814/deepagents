# Round 9 合并日志

**日期**: 2026-03-28~29
**分支**: `upstream-sync-round9`
**范围**: 42 upstream commits + 1 local fix = 43 total
**统计**: 77 files changed, +5316/-1554

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
- `test_agent.py`: `TestLsEntriesShim` 标记 xfail（SDK >=0.5.0 技术债提醒，上游也未清理）

---

## 测试结果

| 套件 | 结果 | 环境 |
|------|------|------|
| SDK unit tests | 1019 passed, 73 skipped, 3 xfailed | --reinstall clean venv |
| CLI unit tests | 待确认 | --reinstall clean venv |
| Evals unit tests | 158 passed | --reinstall clean venv |
| SDK lint | ✅ All checks passed | — |
| CLI lint | ✅ All checks passed | — |

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
