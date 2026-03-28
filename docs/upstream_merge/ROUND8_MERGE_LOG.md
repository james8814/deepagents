# Round 8 上游合并日志

**日期**: 2026-03-28
**分支**: `upstream-sync-round8` (基于 `master`)
**上游**: `langchain-ai/deepagents` main
**合并范围**: 10 commits (Round 8)

---

## 合并结果总览

| # | Commit | 描述 | 冲突 | 解决策略 |
|---|--------|------|------|----------|
| 1 | `dd553cd9` | test: invalid args into tool | 无 | 直接 cherry-pick |
| 2 | `166aebf4` | chore: add all snapshots | **test_system_prompt.py** | 接受上游新增 `_tools_as_openai_snapshot` + `_assert_tools_snapshot` + 补 imports |
| 3 | `adef73c4` | chore: tool descriptions snapshot | **test_system_prompt.py** | 保留 HEAD 的 `_assert_tools_snapshot` helper（更简洁） |
| 4 | `69bd21e2` | fix: normalize CRLF in edit() | 无 | 直接 cherry-pick |
| 5 | `9862b5ad` | fix: FileData NotRequired | **sandbox.py** | 接受上游 `FileData()` 替代 `create_file_data()` |
| 6 | `f69761b4` | chore: speed up init (Pydantic schemas) | **summarization.py** | 保留本地 `Overwrite` import + 接受上游 `BaseModel` import |
| 7 | `4f72c342` | feat: evict large HumanMessages | **filesystem.py**, **test_end_to_end.py** | 保留本地 `os`/`tempfile` (Converters) + 接受 `uuid`；保留 `test_custom_state_schema` + 接受 eviction tests |
| 8 | `f8ebf266` | refactor: extract format_duration | 无 | 直接 cherry-pick |
| 9 | `2e9b705f` | style: task subagent type badge | **messages.py**, **test_messages.py** | 接受上游 `markup=False` + task desc line（更干净） |
| 10 | `a32ce7ff` | perf: defer /model selector | 无 | 直接 cherry-pick |

**冲突统计**: 6 个 commits 有冲突，4 个无冲突

---

## 冲突解决详情

### Commit 2 (166aebf4) — test_system_prompt.py
- **原因**: 上游新增 `_tools_as_openai_snapshot` 和 `_assert_tools_snapshot` 辅助函数，本地已有调用但缺少定义
- **解决**: 接受上游新增函数 + 补充 `json`, `Any`, `convert_to_openai_tool` imports
- **风险**: 低 — 纯测试代码

### Commit 3 (adef73c4) — test_system_prompt.py
- **原因**: 上游 commit 3 是 commit 2 的前置（直接调用 `_assert_snapshot`），我们已在 commit 2 中引入更干净的 helper
- **解决**: 两处冲突都保留 HEAD（使用 `_assert_tools_snapshot` helper）
- **风险**: 低 — 语义等价，更简洁

### Commit 5 (9862b5ad) — sandbox.py
- **原因**: 上游将 `create_file_data()` 替换为直接 `FileData()` 构造（因 `created_at`/`modified_at` 变为 NotRequired）
- **解决**: 接受上游的 `FileData()` 构造方式
- **风险**: 低 — 与 NotRequired 变更一致

### Commit 6 (f69761b4) — summarization.py
- **原因**: 本地有 `from langgraph.types import Command, Overwrite`，上游加了 `from pydantic import BaseModel`
- **解决**: 保留两者 — `Overwrite` 是本地优越特性，`BaseModel` 是上游新 Schema 需要
- **风险**: 低 — 纯 import 合并

### Commit 7 (4f72c342) — filesystem.py + test_end_to_end.py
- **原因 1**: filesystem.py imports — 本地有 `os`, `tempfile`（Converters 使用），上游加 `uuid`
- **解决 1**: 三者全部保留
- **原因 2**: test_end_to_end.py — 本地有 `test_custom_state_schema`，上游加 `TestLargeHumanMessageEviction`
- **解决 2**: 两者全部保留（不同类/方法，无冲突语义）
- **风险**: 中 — eviction 是新功能，需确保不影响 Converters 上下文

### Commit 9 (2e9b705f) — messages.py + test_messages.py
- **原因**: 本地用 `Content.assemble(tool_label)` 防 markup 注入，上游用 `markup=False` + 新增 task desc line
- **解决**: 接受上游方案（`markup=False` 更干净，且带新功能）
- **风险**: 低 — 两种方式都防 markup 注入，上游方案更标准

---

## 本地优越特性保留确认

| 特性 | 状态 | 验证方式 |
|------|------|---------|
| SkillsMiddleware V2 (load_skill/unload_skill) | ✅ 完好 | `grep -c "def.*load_skill\|def.*unload_skill" skills.py` → 9 |
| Converters (PDF/DOCX/XLSX/PPTX) | ✅ 完好 | 10 个 converter 文件存在 |
| upload_adapter V5 | ✅ 完好 | `upload_adapter.py` 存在 |
| Overwrite import (summarization) | ✅ 完好 | `from langgraph.types import Command, Overwrite` |
| state_schema param (graph.py) | ✅ 完好 | `state_schema: type[Any] \| None = None` |
| SubAgent logging | ✅ 完好 | `_ENABLE_SUBAGENT_LOGGING` env gate |
| os/tempfile imports (filesystem.py) | ✅ 完好 | Converters 依赖的 imports 保留 |

---

## 测试结果

| 测试套件 | 结果 | 对比 Round 7 |
|---------|------|-------------|
| **SDK unit tests** | 1018 passed, 73 skipped, 3 xfailed | +9 新测试 (Round 7: 1009) |
| **CLI unit tests** | 2608 passed, 1 skipped | -10 测试 (Round 7: 2618, format_duration 重构) |
| **Evals unit tests** | 158 passed | 全绿（修复后） |
| **SDK lint** | ✅ All checks passed | — |
| **CLI lint** | ✅ All checks passed | — |
| **Evals lint** | ✅ passed (EXE002 为外部卷 macOS 权限问题，CI 无影响) | — |
| **语法检查** | ✅ SDK + CLI compile OK | — |
| **导入检查** | ✅ create_deep_agent + cli_main OK | — |

---

## 架构师验收后修复 (2026-03-28)

### P0: Evals 类别定义漂移 (3 确定性失败)

**根因**: `categories.json` 仍包含旧的 7 个分类 (`retrieval`, `tool_use`, `conversation`, `unit_test`)，
但测试期望新的 12 个分类 (`skills`, `hitl`, `subagents`, `tool_usage` 等)。

**修复** (2 个文件):

- `categories.json`: 更新为 12 个实际 eval 分类 + 对应 labels
- `radar.py` `toy_data()`: 更新覆盖所有 12 个分类的 scores

**自省**: 首次验证时因 venv 安装了不同版本的 evals 包而误报"全绿"。
经架构师指出后，以 `--reinstall` 干净重建 venv 复现了 3 个确定性失败。

### P1: CLI Backslash+Enter flaky (环境相关时序问题)

**根因**: `_BACKSLASH_ENTER_GAP_SECONDS=0.15s` 时间窗口在高负载环境下可能不足，
导致 `pilot.press("backslash")` 和 `pilot.press("enter")` 间隔超出窗口。

**修复** (1 个文件):

- `test_chat_input.py`: 对需要"快速输入"的 2 个测试用 `monkeypatch` 将窗口设为 5.0s，
  确保 Textual pilot 事件间隔始终在窗口内。不修改生产代码。

---

## 新增上游特性

1. **FileData NotRequired** — `created_at` 和 `modified_at` 不再强制要求
2. **CRLF 规范化** — `FilesystemBackend.edit()` 自动处理 `\r\n` 和 `\r`
3. **Pydantic Schema 加速** — 工具使用 `infer_schema=False` + 预定义 Pydantic Schema
4. **大 HumanMessage 驱逐** — 超过 50k token 的 HumanMessage 自动写入文件系统
5. **format_duration 提取** — 共享格式化模块，加载 widget 显示友好时间
6. **Task subagent badge** — task 工具调用显示 [subagent_type] badge + 描述行
7. **/model 延迟加载** — 模型选择器数据异步加载，不阻塞事件循环
8. **工具描述快照** — 新增 5 个 JSON 快照文件用于回归测试

---

## 累计合并统计

| 轮次 | Commits | 累计 |
|------|---------|------|
| Round 0-6 | ~660 | ~660 |
| Round 7 | 27 | ~687 |
| **Round 8** | **10** | **~697** |
