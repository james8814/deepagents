# Round 13 上游合并风险评估

**日期**: 2026-04-12

## 范围锚定

| 端点 | SHA |
|------|-----|
| Round 12 最后上游 | `39b43cf8` |
| upstream/main tip | `a9e6e4f7` |
| **新增** | **114 commits** (78 功能性 + 24 deps + 12 CI) |

---

## 总体风险等级: 🔴 高

**原因**: 本轮包含 3 项 SDK 核心架构变更（permissions 系统、harness profiles 重构、namespace 改进）+ 2 个 release 版本升级（0.5.1→0.5.2）+ 10 个 release commits。graph.py 有 414 行 diff，_models.py 有 142 行 diff。这是 Round 11 级别的大规模变更。

---

## 逐 Commit 风险评估

### Phase A: SDK 核心变更 (9 commits) — 🔴 最高风险

| # | SHA | 描述 | 风险 | 文件 | 分析 |
|---|-----|------|------|------|------|
| 1 | `66c57e1e` | **namespace improvements** | 🔴 高 | 12 files, +441/-257 | BackendContext deprecated，namespace factory 签名变更。store.py + 多个测试文件 |
| 2 | `41dc7597` | **add permissions system** | 🔴 高 | 11 files, +1755/-100 | **新增 permissions.py**（348 行），graph.py 新增 `permissions` 参数。本地 state_schema 在同一区域 |
| 3 | `6dd61223` | **scope permissions to routes** | 🟡 中 | 2 files, +246 | permissions.py 扩展 + E2E 测试 |
| 4 | `723d27dc` | **permission path validation** | 🟢 低 | 2 files, +31 | 小修复 |
| 5 | `57983451` | **implement upload_files for StateBackend** | 🟡 中 | 3 files, +50 | **与本地 upload_adapter 直接相关** — 上游实现了 StateBackend.upload_files()，可能解决我们的 xfail 问题 |
| 6 | `d6fa568e` | **harness profiles for provider/model** | 🔴 高 | 9 files, +1595/-106 | graph.py +356 行 diff。新增 `_harness_profiles.py`, `_openrouter.py`, `_tool_exclusion.py`。**graph.py 本地特性全面冲突** |
| 7 | `a83f1bcf` | **move profiles to subpackage** | 🟡 中 | 10 files, +221/-181 | 紧接 #6 的重构 |
| 8 | `6fcfd25f` | hotfix: relax xfail strictness | 🟢 低 | 1 file |
| 9 | `b843dd3a` | log non-default api key source | 🟢 低 | CLI 日志改进 |

### Phase B: CLI 变更 (12 commits)

| # | SHA | 描述 | 风险 | 分析 |
|---|-----|------|------|------|
| 10 | `0469d142` | harden deploy config parsing | 🟢 | +1124 行（含测试+CONTRIBUTING.md） |
| 11 | `82990916` | load .env before deploy validation | 🟢 | 9 行 |
| 12 | `9052be98` | AGENTS.md in system prompt twice | 🟢 | Bug fix |
| 13 | `5d93b736` | add permissions to deploy | 🟡 | deploy 模板变更 |
| 14 | `b710a69b` | add missing provider deps to deploy | 🟢 | 13 行 |
| 15 | `01564ea2` | add basic MCP example | 🟢 | 新 example 目录 |
| 16 | `ea41d838` | hotfix: remove xfail | 🟢 | |
| 17 | `3a67ef5f` | hotfix: unblock 0.0.36 release | 🟢 | |
| 18 | `a9e6e4f7` | neutral "what's new" heading | 🟢 | |
| 19-21 | 其他 CLI fixes | | 🟢 | 小修复 |

### Phase C: Evals 变更 (8 commits)

| # | SHA | 描述 | 风险 |
|---|-----|------|------|
| 22-29 | harbor/langsmith sandbox/logger | 🟢 低 | 新 evals 环境 + 日志改进 |

### Phase D: Release commits (10) — 特殊处理

| # | SHA | 描述 | 处理 |
|---|-----|------|------|
| 30 | `2320d467` | release: deepagents 0.5.0 | **不 cherry-pick** — 保留本地 0.5.0 |
| 31 | `f316d166` | release: deepagents 0.5.1 | **不 cherry-pick** |
| 32 | `de0823e6` | release: deepagents 0.5.2 | **不 cherry-pick** — 手动提取依赖变更 |
| 33 | `6cd8e16f` | release: CLI 0.0.35 | **不 cherry-pick** |
| 34 | `d36c2433` | release: CLI 0.0.36 | **不 cherry-pick** |
| 35 | `4b25e4a8` | release: CLI 0.0.37 | **不 cherry-pick** |
| 36-39 | partner releases | **不 cherry-pick** |

### Phase E: Deps + CI + Docs (24+12+6 = 42 commits)

| 类型 | 数量 | 风险 |
|------|------|------|
| deps bump | 24 | 🟢 批量 |
| CI workflows | 12 | 🟢 |
| docs | 6 | 🟢 |

---

## 关键冲突预判

### 冲突 1: `d6fa568e` harness profiles (🔴 最高风险)

**graph.py +356 行 diff**。上游引入 harness profiles 系统（provider/model 配置），重构了 `create_deep_agent` 的 model 解析逻辑。新增 `_harness_profiles.py`, `_openrouter.py`, `_tool_exclusion.py`。

**本地冲突面**: graph.py 有 state_schema, skills_expose_dynamic_tools, create_summarization_middleware, skills_allowlist — **全部在 `create_deep_agent` 函数中**。

### 冲突 2: `41dc7597` permissions system (🔴)

**graph.py 新增 `permissions` 参数**。permissions.py 是全新文件（无冲突），但 graph.py 的参数列表和 middleware 堆栈在本地有大量修改。

### 冲突 3: `66c57e1e` namespace improvements (🔴)

**store.py + 测试文件大改**。BackendContext deprecated，namespace factory 签名变更。

### 冲突 4: `57983451` StateBackend upload_files (🟡)

上游实现了 `StateBackend.upload_files()`。本地有 `upload_adapter.py`（V5）。两者可能互补也可能冲突。

---

## 合并方案

### 策略: 5 Phase + 两段合入

**Phase A 分两段**（SDK 高风险最关键）：

```
段 1: 低风险先行
  Phase B: CLI (12 commits)
  Phase C: Evals (8 commits)  
  Phase E: deps/CI/docs (42 commits)
  → checkpoint-round13-segment1-done

段 2: SDK 高风险（3 道 Go/No-Go 闸门，按依赖序）

  Gate A: Namespace improvements（地基）
    66c57e1e
    → checkpoint-round13-gate-a

  Gate B: Harness profiles（装配语义）
    d6fa568e + a83f1bcf
    → checkpoint-round13-gate-b

  Gate C: Permissions system（安全边界）
    41dc7597 + 6dd61223 + 723d27dc
    → checkpoint-round13-gate-c

  Benefit D: StateBackend upload_files（收益收割，非闸门）
    57983451 + 其他小修复
    → checkpoint-round13-segment2-done

Phase D: Release commits → 不 cherry-pick，手动提取依赖变更
  注意: 检查 release commit 是否夹带 deploy 模板中的 deepagents==... pin
```

### Gate 退出条件（硬判定标准：Fail 就退，不模糊）

**Gate A（Namespace）退出条件**:

```bash
cd libs/deepagents && make lint && make test  # 0 failures
```

- namespace 工厂在 runtime 缺失时不抛异常（允许退化到默认 namespace）
- DeprecationWarning 允许存在，但不能导致测试 fail
- 确认警告不来自本地新增代码路径

**Gate B（Profiles）退出条件**:

```bash
cd libs/deepagents && make lint && make test  # 0 failures
```

本地优越特性 8 项全检（在 `libs/deepagents/` 目录下执行）:

```bash
# 1-5: 测试文件验证（已确认存在于仓库）
uv run --group test pytest tests/unit_tests/test_graph_skills_flag_wiring.py -v  # skills_allowlist
uv run --group test pytest tests/unit_tests/middleware/test_subagent_logging.py -v  # logging
uv run --group test pytest tests/unit_tests/middleware/test_subagent_stream_writer.py -v  # stream_writer
uv run --group test pytest tests/unit_tests/middleware/test_summarization_factory.py -v  # summarization factory
uv run --group test pytest tests/unit_tests/middleware/converters/ -v  # Converters

# 6-8: 符号存在性验证（可判定的 Python 检查，非 grep）
uv run python -c "from deepagents.graph import create_deep_agent; import inspect; sig = inspect.signature(create_deep_agent); assert 'state_schema' in sig.parameters, 'state_schema missing'; print('✅ state_schema')"
uv run python -c "from deepagents.graph import create_deep_agent; import inspect; sig = inspect.signature(create_deep_agent); assert 'skills_expose_dynamic_tools' in sig.parameters, 'skills_expose_dynamic_tools missing'; print('✅ skills_expose_dynamic_tools')"
uv run python -c "from deepagents.middleware.summarization import SummarizationMiddleware; import inspect; src = inspect.getsource(SummarizationMiddleware); assert 'isinstance' in src and 'Overwrite' in src, 'Overwrite guard missing'; print('✅ Overwrite guard')"
```

工具集合最终态验证:

```bash
uv run --group test pytest tests/unit_tests/test_graph.py -v -k "tool"
uv run --group test pytest tests/unit_tests/test_end_to_end.py -v -k "subagent or skill"
```

**Gate C（Permissions）退出条件**:

```bash
cd libs/deepagents && make lint && make test  # 0 failures
```

- pre-check 拦截: write/edit/read 对 deny path → error ToolMessage
- post-filter: ls/glob/grep 结果中 deny path 被过滤不泄露
- CompositeBackend + sandbox: 规则 scoped 到 routes → 允许; 非 scoped → 硬失败
- permissions 与 skills_allowlist 不冲突（两者都过滤，互不干扰）

```bash
uv run --group test uv run --group test pytest tests/unit_tests/test_permissions.py -v
uv run --group test uv run --group test pytest tests/unit_tests/test_end_to_end.py -v -k "permission"
```

**Benefit D（upload_files）**:

- 合并后跑 `uv run --group test pytest tests/unit_tests/test_upload_adapter.py -v`
- **用结果驱动是否移除 xfail**（不预先去掉 xfail，避免引入 flaky）
- 记录哪些 xfail 变为 xpassed/passed，再决定是否调整

### Segment 1 门禁

| Segment | 门禁 |
|---------|------|
| Segment 1 (B+C+E) | `cd libs/cli && make lint && make test` + `cd libs/evals && make lint && make test` + lockfile 一致性 |

### 回滚

**防误操作约束**: 所有 checkpoint 必须是集成分支上的本地标签。**不得在已推送到远端的分支上执行 `reset --hard`**。如需回滚远端，改用 `revert` 或从 checkpoint 创建新分支。

```bash
# 闸门 C 回归 → 回滚 permissions，保留 profiles
git reset --hard checkpoint-round13-gate-B

# 闸门 B 回归 → 回滚 profiles，保留 namespace
git reset --hard checkpoint-round13-gate-A

# 段 2 全部回归 → 保留段 1
git reset --hard checkpoint-round13-segment1-done

# 段 1 回归 → 回滚全部
git reset --hard backup-pre-round13
```

---

## 必测点（架构师要求）

### 1. 中间件顺序与工具集合最终态

**风险**: _ToolExclusionMiddleware 按类型去重可能吞掉"同类型不同配置"的中间件实例。skills_expose_dynamic_tools / skills_allowlist 与工具排除机制的交互可能导致工具"时有时无"。

**必测**:
- 同一工具在不同子代理/不同 provider 下是否一致可用
- UI/日志中工具描述与实际可调用集合是否一致
- 系统 prompt 拼装路径是否保留本地 skills 注入

```bash
cd libs/deepagents
uv run --group test pytest tests/unit_tests/test_graph.py -v -k "tool"
uv run --group test pytest tests/unit_tests/test_end_to_end.py -v -k "subagent or skill"
```

### 2. Permissions 边界条件

**验证 permissions 中间件位置**: 必须在 tool-call 链路最后（上游设计为 "always last"，L303）

**必测**:
- first-match-wins 顺序语义（第一条匹配规则生效）
- 默认 allow 策略（无匹配则允许）
- permissions 与 CompositeBackend + sandbox default 的交互
- permissions 与 skills_allowlist 的交互（两者都过滤，不应冲突）

```bash
uv run --group test pytest tests/unit_tests/test_permissions.py -v
uv run --group test pytest tests/unit_tests/test_end_to_end.py -v -k "permission"
```

### 3. StateBackend.upload_files xfail 映射清单

上游 `57983451` 实现了 `StateBackend.upload_files()`。以下 xfail 预期可移除：

| # | 测试 | xfail 原因 | 预期 |
|---|------|-----------|------|
| 1-6 | `TestUploadToState` (class-level xfail) | StateBackend 需要 graph context | 可能仍需 graph context |
| 7 | `test_upload_with_state_backend` | 同上 | 取决于新 upload_files 实现 |
| 8 | `test_upload_with_factory_function` | 同上 | factory 仍 deprecated |
| 9 | `test_backend_read_returns_string_p0_fix` | 同上 | 待验证 |
| 10 | `test_previous_size_in_bytes_p1_fix` | 同上 | 待验证 |

**验证策略**: 合并 `57983451` 后立即跑 `pytest tests/unit_tests/test_upload_adapter.py -v`，记录哪些 xfail 变为 xpassed 或 passed。

---

## 风险统计

| 等级 | 数量 | 代表 |
|------|------|------|
| 🔴 高 | 3 | harness profiles (graph.py 356行), permissions system (+1755), namespace improvements |
| 🟡 中 | 4 | permissions scoping, profiles refactor, StateBackend upload_files, deploy permissions |
| 🟢 低 | ~97 | CLI fixes, evals, deps, CI, docs, examples |

## 时间估算

**注意**: Phase 仅用于风险分类，不用于执行。执行按 Segment + Gate 体系。

| 执行阶段 | 时间 | 风险 |
|----------|------|------|
| Segment 1 (CLI+Evals+deps) | 1-1.5 h | 🟢 |
| Gate A (namespace) | 1 h | 🔴 |
| Gate B (harness profiles) | **2-3 h** | 🔴 |
| Gate C (permissions) | 1 h | 🔴 |
| Benefit D (upload_files + misc) | 30 min | 🟡 |
| Release extraction (手动) | 20 min | 🟡 |
| 最终测试 | 30 min | — |
| **总计** | **7-9 h** | 🔴 |
