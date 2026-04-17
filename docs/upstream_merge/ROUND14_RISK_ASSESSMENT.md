# Round 14 上游合并风险评估

**日期**: 2026-04-17
**上游**: `langchain-ai/deepagents` main
**范围锚定**: `a9e6e4f7..51f15324` (Round 13 end → upstream head)
**上游新增**: **55 commits** (3 upstream releases 0.5.3 / 0.0.38 + 52 functional/deps)

---

## 总体风险等级: 🟢 低

**原因**: 本轮与 Round 13（114 commits, 3 新子系统）相比，变更量减半，无架构级重构。核心变更集中在 SubAgent 结构化输出（新能力）、CLI user scoped memory（部署增强）、`model=None` 废弃预告（仅 warning）、依赖升级（langsmith 0.6→0.7.31）。中间件栈不变（仍 14 层），graph.py 改动面小（+12 行）。

**对比**:

| 维度 | Round 13 | Round 14 |
| --- | --- | --- |
| Commits | 114 | 55 |
| 新子系统 | 3 (Permissions, HarnessProfiles, Deploy) | 0 |
| graph.py diff | +414 行 | +12 行 |
| 高风险项 | 3 | 0 |
| 新 middleware | +3 层 (11→14) | 0 (14 层不变) |
| Release commits | 10 | 3 |

---

## 逐 Commit 风险评估

### Phase A: SDK 核心变更 (4 commits) — 🟡 中风险

| # | SHA | 描述 | 风险 | 文件 | 分析 |
| --- | --- | --- | --- | --- | --- |
| A1 | `149df415` | **deprecate `model=None` in `create_deep_agent`** | 🟡 中 | graph.py +12, pyproject.toml +3, test_graph.py +39 | 新增 `warnings.warn()` 当 `model=None`。本地 graph.py 已有大量定制（14 层栈 / state_schema / skills_expose_dynamic_tools），**需手动在 L415 附近插入 warning** |
| A2 | `6e57731f` | **add static structured output to subagent response** | 🟡 中 | subagents.py +57 | SubAgent TypedDict 新增 `response_format: NotRequired[...]` 字段。本地已有 `skills_allowlist` + `permissions` 字段，**扩展时需保持字段顺序** |
| A3 | `badc4d39` | **skill loading should default to 1000 lines** | 🟡 中 | skills.py +5 | **预期冲突** — 本地 V2 skills.py (1197 行) 与上游 (~834 行) 差异巨大。修改在 L574-594 的 skill usage 指南 prompt，本地同位置 (L651-652) 也有相同文本 |
| A4 | `48696454` | xfail langsmith sandbox integration tests | 🟢 低 | test markers | 对本地已跳过的测试无影响 |

### Phase B: CLI 变更 (8 commits, 其中 1 个跳过) — 🟢 低风险

| # | SHA | 描述 | 风险 | 分析 |
| --- | --- | --- | --- | --- |
| B1 | `23bfca6e` | **feat(cli): user scoped memory** | 🟡 中 | +534/-75, 仅 deploy/ 子包 + examples |
| B2 | `d39fd5d3` | perf(cli): O(1) MessageStore lookups | 🟢 低 | widgets/message_store.py (本地无改动) |
| B3 | `6b58e06b` | feat(cli): inline argument hints for slash commands | 🟢 低 | 命令 UI 增强 |
| B4 | `ba31294b` | fix(cli): throttle update notification | 🟢 低 | 小修复 |
| B5 | `15288779` | fix(cli): compact/resume polling replace xfail | 🟢 低 | 之前 Round 11 的 xfail 修复 |
| B6 | `51f15324` | chore(cli): track deploy usage | 🟢 低 | deploy/commands.py +5 |
| B7 | `ead1d09c` | docs(cli): clarify api key name | 🟢 低 | config 文档 |
| B8 | `482f3810` | chore(cli): bump deepagents version | 🟢 低 | 版本依赖更新 (升到 0.5.3，**跳过，保持本地 0.5.0 pin 不变**) |

### Phase C: REPL 变更 (3 commits) — 🟢 低

| # | SHA | 描述 | 风险 |
| --- | --- | --- | --- |
| C1 | `44ae33a3` | feat(repl): tool runtime support for sync funcs | 🟢 低 |
| C2 | `b00e16c8` | feat(repl): foreign object interface + `+/-` | 🟢 低 (+336 行，纯新增) |
| C3 | `64ecf141` | chore(repl): add benchmark | 🟢 低 |

### Phase D: Evals / ACP / Deepagents (4 commits) — 🟢 低

| # | SHA | 描述 | 风险 |
| --- | --- | --- | --- |
| D1 | `09db2753` | ci(evals): descriptive run-name for harbor workflow | 🟢 |
| D2 | `e10ca2bf` | feat(evals): more complex tool usage tasks | 🟢 |
| D3 | `02ff02f5` | fix(acp): upper bound ACP | 🟢 依赖 bound |
| D4 | `6653197b` | fix(deepagents): remove old integration tests | 🟢 |

### Phase E: Release commits (3) — 特殊处理

| # | SHA | 描述 | 处理 |
| --- | --- | --- | --- |
| E1 | `c9cfbe5a` | release(deepagents): 0.5.3 | **不 cherry-pick** — 保留本地 0.5.0 |
| E2 | `855ef82b` | release(deepagents-cli): 0.0.38 | **不 cherry-pick** — 保留本地 0.0.34 |
| E3 | (无 deepagents-cli 0.0.37 变更) | — | — |

### Phase F: 依赖更新 (24 commits) — 🟡 中风险

**原因**: langsmith `0.6.x/0.7.x → 0.7.31` 跨多个 minor，影响面覆盖 sandbox client / CLI / deploy 相关路径。虽然多数为 lockfile 机械更新，但需要增加 smoke 验证来降低“运行时才暴雷”的风险。

**langsmith 0.6.x/0.7.x → 0.7.31** (11 个子包):

- `95238fcc` evals, `388460bf` cli, `489b5a92` text-to-sql, `02906ca0` content-builder, `43da6622` deep_research, `33f1e7fe` acp, `ae3ba284` daytona, `23f0f4fb` runloop, `3c4c2758` modal, `cb4dc3fc` nvidia, `778f5ee6` deepagents, `a33fa01d` quickjs

**pytest 8.4.2/9.0.2 → 9.0.3** (7 个子包):

- `6ee89b09` evals, `103fbcbc` cli, `2d972d90` quickjs, `434eadf2` runloop, `1f3e18e9` modal, `e04a2aa0` acp, `1db1d333` deepagents, `596e564d` daytona

**pillow 12.1.1 → 12.2.0** (3 个):

- `f4d452aa` content-builder, `f9888c2e` cli, `c1f9e20e` evals

**python-multipart 0.0.22 → 0.0.26** (2 个):

- `ac38fb1c` cli, `65785a13` evals

**其他** (1 个):

- `caeecdac` uv group bump
- `a1161279` uv group bump
- `e9a3dec3` langchain-tests min version

### Phase G: CI / 基础设施 (6 commits) — 🟢 低

| # | SHA | 描述 |
| --- | --- | --- |
| G1 | `4b2ac867` | ci(infra): add integration test workflow |
| G2 | `5a6d6cff` | hotfix(infra): fix integration test workflow failures |
| G3 | `880a1abb` | chore(sdk): suppress pytest-benchmark warnings |
| G4 | `b3e36baf` | chore(ci): disable integration tests on release |
| G5 | `caae0bd7` | ci(infra): add `deps-dev` commit scope to pr linter |
| G6 | `5b027730` | ci(infra): validate issue checkboxes |

---

## 关键冲突预判

### 冲突 1: `badc4d39` skill prompt 更新 (🟡 最高风险)

**上游改动**: `skills.py` L574-594 修改 skill 使用指南 prompt。

**本地状态**: 本地 V2 skills.py 有 1197 行（vs 上游 ~834 行），**相同 prompt 文本在本地 L651-652**。冲突是可预期的，但内容是纯 prompt 文本更新（添加 `limit=1000` 指南）。

**解决方案**: 条件化合并（避免本地 V2 的 `load_skill` 与上游 `read_file(limit=1000)` 形成双通道指令冲突）:

- 当 `skills_expose_dynamic_tools=False`（V1/fallback 模式）：接受上游 “读 SKILL.md 时使用 `limit=1000`” 的指令
- 当 `skills_expose_dynamic_tools=True`（本地 V2 primary 模式）：保留并优先引导使用 `load_skill(name)`（减少 prompt 指令与工具路径分叉）

### 冲突 2: `149df415` `model=None` 废弃 (🟡)

**上游改动**: graph.py L415 附近插入 `warnings.warn()`。

**本地状态**: 本地 graph.py 已经从 L114 开始大量定制（helper 函数、harness profile 集成、permissions）。`_model_spec` 行应该位置一致，但**需要验证**。

**解决方案**:

- 手动在正确位置插入 `warnings.warn()` 块（仅 warning，不改行为）
- `pyproject.toml` 的 `filterwarnings` 必须与 graph.py 的 warning 同步合入（否则可能引入测试/CI 的 warning 污染或严格告警失败）

### 冲突 3: `6e57731f` SubAgent `response_format` (🟡)

**上游改动**: subagents.py 新增 `response_format` 字段 + JSON 序列化逻辑。

**本地状态**: 本地 SubAgent TypedDict 已有 `skills_allowlist` + `permissions`，**需保持字段声明顺序**。

**解决方案**: 按上游同位置插入 `response_format`，确保与本地字段不冲突。

### 冲突 4: 依赖 bump 的 lockfile (🟢)

**上游**: 24 个 deps bump 会更新多个 uv.lock。

**解决方案**: 接受上游 (`git checkout --theirs`)，与 Round 13 策略一致。

---

## 合并方案

### 策略: 3 Phase + Gate 1（Phase 1 后统一验收）

**原因**: Round 14 无高风险 SDK 架构变更，适合线性推进；但 Phase 1 引入大规模依赖升级（langsmith 跨多个 minor）与跨包 lockfile 变更，需要增加一个“可量化 Gate”来保证落地质量。

```text
Phase 1a: Deps bump 批量（24 commits，纯机械）
  - Phase F: 所有 deps 相关（langsmith/pytest/pillow/python-multipart/uv）
  - 冲突策略: `git checkout --theirs .`（与 Round 13 一致）
  → checkpoint-round14-phase1a-deps-done

Phase 1b: CLI/REPL 功能（11 commits）
  - Phase B: CLI（含 `23bfca6e` user scoped memory；跳过 `482f3810`）
  - Phase C: REPL
  → checkpoint-round14-phase1b-cli-done

Phase 1c: Evals/ACP/CI（其余低风险 commits）
  - Phase D: Evals/ACP/Deepagents
  - Phase G: CI/基础设施
  → checkpoint-round14-phase1c-infra-done

Gate 1: 全量测试 + langsmith sandbox smoke + 跨包 relock 检查
  → checkpoint-round14-gate1-done

Phase 2: SDK 核心变更 (4 commits) — 手动处理冲突
  - A1: deprecate model=None（graph.py 小插入）
  - A2: subagent response_format（subagents.py TypedDict 扩展）
  - A4: xfail langsmith sandbox（如 Phase 1 已修复相关失败，可跳过此 commit）
  - A3: skill prompt 条件化合并（最后处理，避免冲突扩大）
  → checkpoint-round14-phase2-done

Phase 3: 验证 + 文档
  - 全量测试（SDK / CLI / Evals / ACP / REPL）
  - 新功能 smoke / 集成测试补强（response_format 三策略、user memory 隔离、model=None warning）
  - 更新 CLAUDE.md (SubAgent.response_format, user scoped memory)
  - 更新 MEMORY.md (Round 14 状态)
  - 编写 SDK_UPGRADE_NOTICE_ROUND14.md（外部团队升级说明）
```

### Gate 1 退出条件（Phase 1a/1b/1c 后统一验收）

```bash
cd libs/deepagents && UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/ -q
cd libs/cli && uv run --group test pytest tests/unit_tests/ --disable-socket --allow-unix-socket -q --timeout 30
cd libs/evals && uv run --group test pytest tests/unit_tests/ -q --timeout 30
cd libs/acp && uv run --group test pytest tests/ -q --timeout 30
cd libs/repl && uv run --group test pytest tests/ -q --timeout 30

python -c "from langsmith.sandbox import Sandbox, SandboxClient; print('OK')"

cd libs/cli && uv lock --check
```

**期望**:

- SDK: 1251 passed (可能 +0, deps bump 不新增测试)
- CLI: 2959 passed (可能 +0)
- Evals: 239 passed (可能 +2, tool usage tasks)
- ACP: 76 passed (可能 +0)
- REPL: 59 passed (可能 +0)
- langsmith sandbox import smoke: 打印 `OK`
- `uv lock --check` 通过（CLI 仍能解析并 pin 到本地 SDK 0.5.0）
- 无新增 fail

### Phase 2 退出条件

```bash
# 本地特性 8 项全检
cd libs/deepagents
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/test_graph_skills_flag_wiring.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/middleware/test_subagent_logging.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/middleware/test_subagent_stream_writer.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/middleware/test_summarization_factory.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/middleware/converters/ -v

# 新增上游特性验证
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/test_subagents.py -v  # structured output
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/test_graph.py -v -k "model_none or deprecat"  # model=None deprecation

UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/test_graph.py -v -W error::DeprecationWarning -k "model_none or deprecat"
```

**期望**:

- SDK: 1251 + ~40 passed (test_subagents.py 新增 ~30 + test_graph.py +10)
- 本地 8 特性全部通过

### 中风险项验收清单（架构师关心的“正确性边界”）

- SubAgent `response_format`：父代理能稳定收到结构化 JSON（无论 tool/provider/auto 策略），并且不破坏既有 `permissions` / `skills_allowlist` 字段语义
- skill prompt 更新：采用条件化合并策略，V2 agent 优先引导 `load_skill(name)`，仅在 fallback（`skills_expose_dynamic_tools=False`）路径引导 `read_file(limit=1000)`；避免双通道指令冲突
- `model=None`：仅新增 `DeprecationWarning`，不改变默认 model 推断与 provider profile 绑定行为；且 `pyproject.toml` 的 `filterwarnings` 已生效（`-W error::DeprecationWarning` 不应失败）
- CLI user scoped memory：确认每用户 memory 隔离（`/memories/user/AGENTS.md`）不会跨用户串写，且不会把用户内容写入 seed（仍应只把 `AGENTS.md` / `skills/` 作为 seed）。另外需在 Round 14 升级说明中明确 `/memories/user/` 与 `FilesystemPermission` 的交互（权限规则可能导致写入被拒绝）

### Phase 3 退出条件

- 所有 5 个包测试全绿
- CLAUDE.md 更新：Middleware Stack 部分保持 14 层（本轮不变）；SubAgent 章节新增 `response_format` 字段文档；CLI 章节新增 user scoped memory
- 新功能 smoke / 集成测试覆盖：
  - SubAgent response_format 三策略（ToolStrategy / ProviderStrategy / AutoStrategy）最小链路验证
  - user memory 命名空间隔离验证（deploy bundler 单测或最小集成链路）
  - model=None 仅 warning 不 fail
- 外部团队升级说明（Round 14）交付（包含 opt-in 条件、与 permissions 的交互警告、迁移示例）

---

## 时间估算

| 阶段 | 时间 | 风险 |
| --- | --- | --- |
| Phase 1a/1b/1c 拆分执行 | 45-60 min | 🟡 |
| Gate 1 验证 | 10-15 min | 🟡 |
| Phase 2 SDK 手动冲突解决 | 45-60 min | 🟡 |
| Phase 3 全量测试 + 文档 | 60-75 min | 🟢 |
| **总计** | **2.5-3.5 h** | 🟡 |

对比 Round 13 (7-9 h), 本轮时间降低 70%。

---

## 回滚策略

```bash
# Gate 1 前失败 → 回滚到最近 sub-checkpoint
git reset --hard checkpoint-round14-phase1a-deps-done
git reset --hard checkpoint-round14-phase1b-cli-done
git reset --hard checkpoint-round14-phase1c-infra-done

# Phase 2 失败 → 回滚到 Gate 1 完成点
git reset --hard checkpoint-round14-gate1-done

# Phase 1 失败 → 回滚到 Round 13 完成点
git reset --hard a9694a77

# 最终回滚 → 备份分支
git branch backup-pre-round14 master
```

---

## 跳过 commits 清单（release）

```text
c9cfbe5a  # release(deepagents): 0.5.3
855ef82b  # release(deepagents-cli): 0.0.38
482f3810  # chore(cli): bump deepagents version (0.5.0 → 0.5.3，本地保持 0.5.0)
```

共 3 个 commits 跳过，其中 `482f3810` 虽不是 release 但内容是跟 release 配套的版本 bump，**保持本地 pin 不变**。

---

## 本地优越特性保护清单

Phase 2 后必须验证以下本地特性未被破坏：

| # | 特性 | 验证方法 |
| --- | --- | --- |
| 1 | state_schema | `inspect.signature(create_deep_agent).parameters` 包含 |
| 2 | skills_expose_dynamic_tools | 同上 |
| 3 | skills_allowlist | `test_graph_skills_flag_wiring.py` 6 tests |
| 4 | create_summarization_middleware | `test_summarization_factory.py` 3 tests |
| 5 | Overwrite guard | `isinstance(messages, Overwrite)` in summarization.py |
| 6 | SubAgent stream_writer | `test_subagent_stream_writer.py` 8 tests |
| 7 | SubAgent logging | `test_subagent_logging.py` 20 tests |
| 8 | Converters | `middleware/converters/` 23 tests |

**额外**（Round 13 新增，Round 14 须继续保护）:

- permissions 参数 + `_PermissionMiddleware` 在栈末尾
- `_HarnessProfile` 正确加载
- `_ToolExclusionMiddleware` 在 user middleware 之后

---

## 风险统计

| 等级 | 数量 | 代表 |
| --- | --- | --- |
| 🔴 高 | 0 | — |
| 🟡 中 | 5 | skill prompt 冲突, model=None 警告, SubAgent response_format, user scoped memory, langsmith 跨 minor deps bump |
| 🟢 低 | 47 | CLI fixes, REPL, CI, docs 等 |

---

## 最终建议

**架构师意见**: 可按方案推进。本轮变更温和，无需 Go/No-Go Gate 系统。

**研发主管意见**: 建议分配 3 小时连续时间块，避免 Phase 2 中断。

**预期交付**:

- 累计合并 ~986 commits (Round 0-14)
- 新增外部可用能力: `SubAgent.response_format`（结构化输出）、CLI user scoped memory、REPL foreign object interface
- 本地版本保持: SDK 0.5.0 / CLI 0.0.34
