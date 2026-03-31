# Round 10 上游合并风险评估

**日期**: 2026-03-31

## 范围锚定

```bash
git rev-list --count 9bddc52b..upstream/main
```

| 端点 | SHA | 说明 |
|------|-----|------|
| Round 9 最后上游 commit | `9bddc52b` | fix(cli): eliminate trace fragmentation |
| upstream/main tip | `8be4a2ee` | fix(sdk): fix TypeError in async sub-agents |
| 新增 commits | **33** | 23 功能/修复/重构 + 5 deps bump + 4 CI + 1 docs |

---

## 总体风险等级: 🟠 中高

**原因**: `cb79d515` (deprecate backend factories) 是一次**大规模架构重构**（40 files, +2357/-2970），直接影响 SDK 核心的 backend factory 机制和 graph.py。同时 `845cdf52` 修复 deprecated protocol return types，涉及 protocol.py 和 filesystem.py 的类型签名变更。这两个 commit 对本地优越特性（Converters, upload_adapter, state_schema）有潜在冲突风险。

---

## 逐 Commit 风险评估

### Phase A: SDK 核心变更 (8 commits) — 重点关注

| # | SHA | 描述 | 风险 | 文件 | 分析 |
|---|-----|------|------|------|------|
| 1 | `92f55075` | fix offloading for state backend | 🟡 中 | summarization.py, test_compact_tool.py, test_end_to_end.py | `_offload_to_backend` 返回类型从 `str|None` 变为 `tuple[str|None, dict|None]`。**summarization.py 有本地 Overwrite guard 需保留** |
| 2 | `24146c06` | assert default toolruntime config in E2E test | 🟢 低 | graph.py, test_end_to_end.py | graph.py 仅改 1 行默认值传递，test 新增断言 |
| 3 | `9783fe43` | catch UnicodeDecodeError in FilesystemBackend.read | 🟢 低 | filesystem.py, test_filesystem_backend.py | 小改动，增加异常处理 |
| 4 | `beb4dbb6` | add new line after HEREDOC for edit inline sandbox | 🟢 低 | sandbox.py, test_sandbox_backend.py | 小改动 |
| 5 | `845cdf52` | **restore deprecated protocol return types** | 🟡 中偏高 | protocol.py, filesystem.py, test_protocol.py | 协议返回类型恢复本身降低外部自定义 backend 的升级摩擦；风险主要来自与本地 Converters/返回类型策略的冲突，需要按顺序合并并用专项用例验证 |
| 6 | `cb79d515` | **deprecate backend factories** | 🔴 高 | **40 files**, graph.py, state.py, store.py, composite.py, filesystem middleware 等 | **最大风险**: 协议/状态更新语义收敛导致行为路径改写（尤其 files/state 更新链路），而不是单纯“callable factory 能不能用”。graph.py 有本地优越特性。**+2357/-2970 行变更** |
| 7 | `8e1a2d67` | last_updated_at field for async task status | 🟢 低 | async_subagents.py, test_async_subagents.py | 小字段更新 |
| 8 | `8be4a2ee` | **fix TypeError in async sub-agents** | 🟡 中 | async_subagents.py, test_end_to_end.py (+568 行测试) | 移除 `from __future__ import annotations` + TYPE_CHECKING 延迟导入改为直接导入。大量新 E2E 测试 |

### Phase B: CLI 变更 (9 commits) + 工具链配置 (1 commit)

| # | SHA | 描述 | 风险 | 文件 | 分析 |
|---|-----|------|------|------|------|
| 9 | `f43e4108` | hide redundant exit code 0 from tool output | 🟢 低 | messages.py, test_messages.py | 小 UI 改动 |
| 10 | `cb9a0c7a` | mark token count as approximate after interrupted generation | 🟡 中 | textual_adapter.py, status.py, token_tracker.py + 3 test files | 重构 token tracking，多文件变更 |
| 11 | `c52f27a3` | defer mode glyph and popup updates atomically | 🟡 中 | app.tcss, chat_input.py, model_selector.py | chat_input.py 有 Round 8 Backslash+Enter 修改 |
| 12 | `5fbb14a4` | render ask-user questions as markdown | 🟢 低 | app.tcss, ask_user.py, test_ask_user.py | 独立组件 |
| 13 | `2b2d9100` | **remove http_request tool** | 🟡 中 | 10 files, -151 行 | 移除功能，可能影响本地 agent.py |
| 14 | `5be352d8` | **persist token count across sessions** | 🟡 中 | 9 files, +569/-252 | textual_adapter.py 重构，thread_selector.py 变更 |
| 15 | `f618acc6` | support root/MDM installs | 🟢 低 | install.sh | 独立脚本 |
| 16 | `95620e79` | surface unsupported input modalities in system prompt | 🟡 中 | 8 files, +310 | config.py 变更（热点文件） |
| 17 | `82a378e1` | pass --benchmark-disable in Makefile | 🟢 低 | Makefile, pyproject.toml | 配置调整 |
| 18 | `205e0be1` | disable benchmark when not running benchmarks | 🟢 低 | libs/deepagents/Makefile | SDK benchmark 开关行为调整，非 CLI 代码路径 |

### Phase C: Evals 变更 (5 commits)

| # | SHA | 描述 | 风险 | 分析 |
|---|-----|------|------|------|
| 19 | `b5114046` | add eval catalog with drift detection | 🟢 低 | 新功能，独立文件 |
| 20 | `240312c7` | show category keys in catalog headers | 🟢 低 | 小改动 |
| 21 | `d4447b74` | add section headings to model groups | 🟢 低 | 重构现有文件 |
| 22 | `04a4b394` | surface langsmith experiment URLs in reports | 🟢 低 | 新功能 |
| 23 | `6d8cfebb` | add file seeded retrieval to MemoryAgentBench | 🟢 低 | 测试扩展 |

### Phase D: 依赖 + CI + 文档 (10 commits)

| # | SHA | 描述 | 风险 | 分析 |
|---|-----|------|------|------|
| 24 | `be7d2640` | bump requests | 🟢 低 | lockfile |
| 25 | `3b749183` | bump requests in CLI | 🟢 低 | lockfile |
| 26 | `799d303c` | bump pygments to 2.20.0 (security) | 🟡 中 | 12 files lockfile, 安全修复 |
| 27-28 | `56135477`, `e7578dc0` | bump requests in examples | 🟢 低 | lockfile |
| 29 | `87ac1a25` | add threat model docs | 🟢 低 | 新文档 |
| 30 | `39b8053e` | auto-close issues bypassing template | 🟢 低 | GitHub Actions |
| 31 | `327706cb` | auto-reopen PRs on issue assignment | 🟢 低 | GitHub Actions |
| 32 | `35b1e4f8` | tighten release permissions | 🟢 低 | GitHub Actions |
| 33 | `cc6f5f26` | minimize stale enforcement comments | 🟢 低 | GitHub Actions |

---

## 关键冲突预判

### 冲突 1: `cb79d515` — 协议/状态更新语义收敛 (🔴 最高风险)

**变更本质**: 这不仅是"移除 backend factory callable"，而是一次**后端/协议/中间件行为收敛**的大改动。涉及：

- 初始化模式：`StateBackend(runtime)` → `StateBackend()`，runtime 由 middleware 注入
- 状态回写：`CompositeBackend` 移除了 `files_update` 的 best-effort state sync 代码
- filesystem 工具返回值形态：移除兼容层后工具直接依赖协议返回类型

**核心风险不是"callable 能不能用"，而是行为路径是否被改写（尤其是 files/state 更新链路）。**

**本地冲突面**:

| 本地特性 | 文件 | 冲突概率 |
|---------|------|----------|
| `state_schema` 参数 | graph.py | 🔴 高 — graph.py 有本地 `state_schema` 参数和 `create_summarization_middleware` factory |
| Converters | filesystem.py | 🟡 中 — filesystem.py 的 import 和常量区域可能冲突 |
| Overwrite guard | summarization.py | 🟡 中 — 同一文件被多个 commit 修改 |
| upload_adapter | upload_adapter.py | 🟢 低 — 独立文件 |

**策略**: 这是 40 files 的大型重构。建议**不要 cherry-pick**，而是先分析 graph.py 的 diff，确认本地优越特性的代码区域是否被触及，再逐文件解决。

### 冲突 2: `845cdf52` — 协议返回类型与本地 Converters 策略的冲突 (🟡 中偏高)

**变更本质**: 恢复 deprecated protocol 方法的原始返回类型（`list[FileInfo]` 而非 `LsResult`），降低外部自定义 backend 的升级摩擦。同时移除 filesystem.py 中的 `isinstance` 兼容层。

**真实风险**: 不在于"去兼容层"本身，而在于**与本地 Converters / Round 9 返回类型扩展的语义拉扯**。容易出现"你合了 A 又被 B 改回去"的反复，需要按顺序和验证点控制。

**本地冲突面**: filesystem.py 有本地 Converters 代码（`IMAGE_EXTENSIONS`, `BINARY_DOC_EXTENSIONS`, `_convert_document_sync/async`），import 行会冲突。

**策略**: 接受上游简化，保留 Converters 代码。合并后重点验证 Converters 的 read_file 路径是否仍正常工作。

### 冲突 3: `92f55075` — fix offloading for state backend

**变更本质**: `_offload_to_backend` 返回值从 `str|None` 变为 `tuple[str|None, dict|None]`，需要 `files_update` 传递给 state channel。

**本地冲突面**: summarization.py 有本地 `Overwrite` guard。

**策略**: 接受上游返回值变更，保留 Overwrite guard。

---

## 合并方案

### 策略: 5 个 Phase，高风险最后处理

```
Phase A-1: SDK 小改动                 → 🟢 先落地安全变更
Phase A-2: SDK 大型重构               → 🔴 逐个处理，graph.py 最关键
Phase B: CLI 变更                     → 🟡 中等风险
Phase C: Evals 变更                   → 🟢 批量
Phase D: deps / CI / docs              → 🟢 批量
```

### 建议合并顺序

```
# Phase A-1: SDK 安全变更
1. 9783fe43  catch UnicodeDecodeError in read          🟢
2. beb4dbb6  HEREDOC newline for sandbox edit          🟢
3. 24146c06  assert default toolruntime config         🟢
4. 8e1a2d67  last_updated_at for async tasks           🟢

# Phase A-2: SDK 大型重构（逐个处理，最高风险）
5. 92f55075  fix offloading for state backend          🟡 (summarization.py)
6. 845cdf52  restore deprecated protocol return types  🟡 中偏高 (protocol.py + filesystem.py)
7. cb79d515  deprecate backend factories               🔴 (40 files, graph.py 关键)
8. 8be4a2ee  fix TypeError in async sub-agents         🟡 (async_subagents.py)

# Phase B: CLI 变更
9-18. 按 commit 时间序逐个 cherry-pick

# Phase C: Evals (批量)
19-23. 批量 cherry-pick

# Phase D: deps + CI + docs (批量)
24-33. 批量 cherry-pick
```

### 每 Phase 回滚策略

| Phase | 回滚方式 |
|-------|----------|
| A-1 | `git reset --hard checkpoint-round10-phaseA1-start` |
| A-2 | `git reset --hard checkpoint-round10-phaseA2-start`（graph.py 不可部分回退） |
| B | `git revert --no-commit HEAD~N..HEAD` 或 reset |
| C | `git reset --hard checkpoint-round10-phaseC-start` |
| D | `git reset --hard checkpoint-round10-phaseD-start` |

### 每 Phase 门禁

| Phase | 门禁 | 额外要求 |
|-------|------|----------|
| A-1 | SDK: `make lint && make test` | — |
| A-2 | SDK: `make lint && make test` | **干净 venv `--reinstall`** + 本地优越特性 8 项全检 + SDK 强耦合必测项 |
| B | CLI: `make lint && make test` | config.py 变更后验证 `--help` 启动时间 |
| C | evals: `make lint && make test` | evals `--reinstall` |
| D | 全包: `make test` | — |

### Phase A-2 SDK 强耦合必测项（架构师要求）

这 3 个强耦合点必须被显式验证，否则 Phase 虽然分了但风险没被真正隔离：

（以下 `pytest` 命令均在 `libs/deepagents/` 目录内执行）

1. **后端协议 deprecated 方法返回** (protocol.py):
   - `pytest tests/unit_tests/backends/test_protocol.py -v`
2. **offload / files_update / state 回写链路** (summarization + filesystem + state):
   - `pytest tests/unit_tests/middleware/test_summarization_middleware.py tests/unit_tests/middleware/test_compact_tool.py -v`
   - `pytest tests/unit_tests/test_end_to_end.py -v -k "offload or state or compact"`
3. **async subagents 调度与类型** (async_subagents.py):
   - `pytest tests/unit_tests/test_async_subagents.py -v`
   - `pytest tests/unit_tests/test_end_to_end.py -v -k "async"`

---

## 风险等级统计

**高风险判定标准**: 是否改变协议/状态更新/初始化语义（不只是 diff 规模）。

| 等级 | 数量 | 代表 |
|------|------|------|
| 🔴 高 | 1 | cb79d515: 协议/状态更新语义收敛（40 files, 改变 files/state 更新链路） |
| 🟡 中偏高 | 1 | 845cdf52: 协议返回类型恢复（与本地 Converters/返回类型策略冲突） |
| 🟡 中 | 7 | state backend offloading, async sub-agents, token tracking, http_request removal, chat_input, config.py, pygments security |
| 🟢 低 | 24 | 小改动 + 依赖 bump + CI + 文档 |

## 时间估算

| Phase | 预计时间 | 风险 |
|-------|---------|------|
| Phase A-1: SDK 安全 | 20 min | 🟢 |
| Phase A-2: SDK 重构 | **3-4 h** | 🔴 |
| Phase B: CLI | 1.5-2 h | 🟡 |
| Phase C: Evals | 30 min | 🟢 |
| Phase D: deps + CI + docs | 20 min | 🟢 |
| 测试验证 | 1 h | — |
| **总计** | **6-8 h** | 🟠 |
