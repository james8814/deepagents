# Round 15 上游合并风险评估

**日期**: 2026-04-27
**上游**: `langchain-ai/deepagents` main
**范围锚定**: `51f15324..95f845d2` (Round 14 end → upstream head)
**上游新增**: **83 commits** (4 release + 79 functional/deps)

---

## 总体风险等级: 🟡 中

**原因**: 本轮 commits 数量介于 Round 13 (114) 和 Round 14 (55) 之间，无新架构子系统，但有 2 个潜在中-高风险点：

1. `eb9fab96` graph.py 参数重排 — 与本地 19 参数定制有交叉
2. `f7e37721` SkillsMiddleware labelled sources — 本地 V2 (1197 行) 与上游差异已大，新特性需评估

中间件栈不变（仍 14 层）。

**对比**:

| 维度 | Round 13 | Round 14 | Round 15 |
| --- | --- | --- | --- |
| Commits | 114 | 55 | 83 |
| 新子系统 | 3 | 0 | 0 |
| graph.py diff | +414 行 | +12 行 | +20/-20 (重排) |
| skills.py diff | +5 行 (prompt) | +5 行 (prompt) | **+141 行** (labelled sources) |
| 高风险项 | 3 | 0 | 1-2 |
| Release commits | 10 | 3 | 4 |

---

## 逐 Commit 风险评估

### Phase A: SDK 核心变更 (8 commits) — 🟡 中风险

> **架构师修正 (2026-04-27)**: 通过事实核查发现两个"变更簇"。`1699f3ae` 实际触及 graph.py +10 行，`e1c1d502` 实际触及 skills.py +127 行（commit message 仅说"Windows 路径修复"但同时重写了 `_list_skills`/`_alist_skills`/`_format_skills_locations`）。**所有触及 graph.py 或 skills.py 的 commits 必须聚簇统一处理**，避免同一文件被多次手工冲突。

**变更簇映射**:

| 文件 | 触及 commits | 累计行数 |
| --- | --- | --- |
| `graph.py` | `eb9fab96` + `1699f3ae` | +30 行 |
| `skills.py` | `f7e37721` + `e1c1d502` | +268 行 |
| `subagents.py` | `3bcc51a9` + `bd6ec6bc` | +69/-26 行 |

| # | SHA | 描述 | 风险 | 文件 | 分析 |
| --- | --- | --- | --- | --- | --- |
| A1 | `eb9fab96` | **refactor(sdk): reorder `create_deep_agent` params by category** | 🔴 高 | graph.py +20/-20 | **graph.py 簇** — 上游把 `backend`/`interrupt_on` 提前到 `response_format` 之前。本地有 `state_schema`/`skills_expose_dynamic_tools` 额外参数 |
| A2 | `f7e37721` | **feat(sdk,cli): labelled skill sources** | 🔴 高 | skills.py +141, agent.py +41, local_context.py +28 | **skills.py 簇** — 引入 `SkillSource = str \| tuple[str, str]` 类型别名 |
| A3 | `1699f3ae` | perf(sdk): add cache breakpoint to MemoryMiddleware | 🟡 中 | **graph.py +10**, memory.py +37, tests +114 | **graph.py 簇** — 触及 graph.py（架构师修正：原标注"低风险仅 memory.py"错误） |
| A4 | `3bcc51a9` | feat(sdk): `ls_agent_type` configurable tag on subagent runs | 🟡 中 | subagents.py +31 | subagents.py 簇 |
| A5 | `bd6ec6bc` | fix(sdk): subagent tagging via configurable instead of tracing context | 🟢 低 | subagents.py +38/-26 | subagents.py 簇 |
| A6 | `291aebe2` | fix(sdk): preserve CRLF line endings in sandbox edit | 🟢 低 | sandbox.py +44 | 独立文件 |
| A7 | `e1c1d502` | fix(sdk): normalize Windows backslash paths before PurePosixPath | 🟡 中 | **skills.py +127**, filesystem.py, protocol.py, utils.py | **skills.py 簇** — 触及 skills.py（架构师修正：原标注"低风险仅 utils.py"错误） |
| A8 | `87644b78` | chore(sdk): perf optimization for patching tool calls | 🟢 低 | patch_tool_calls.py +38 | 独立文件 |

### Phase B: CLI 变更 (28 commits) — 🟡 中风险

**新功能** (8 项):

| # | SHA | 描述 | 风险 |
| --- | --- | --- | --- |
| B1 | `3a2b7777` | **feat(cli): `/agents` switcher** | 🟡 新命令 + 多文件 |
| B2 | `417ddaab` | **feat(cli): custom auth via `[auth]`** | 🟡 deploy 增强 |
| B3 | `7dd5565e` | feat(cli): subagents for `deepagents deploy` | 🟡 deploy 模板增强 |
| B4 | `5fcd3680` | feat(cli): actionable notifications + update modal | 🟢 |
| B5 | `1ae053f3` | feat(cli): rework `/version` + release-age + editable-install guard | 🟢 |
| B6 | `8adcc2c2` | feat(cli): `--startup-cmd` flag | 🟢 |
| B7 | `567bcd8f` | feat(cli): `--max-turns` flag | 🟢 |
| B8 | `34e6614a` | feat(cli): shift+enter newline on kitty terminals | 🟢 |
| B9 | `7cffa16a` | feat(cli): hint Enter behavior in /model empty state | 🟢 |
| B10 | `ee4fddde` | feat(cli): refresh footer git branch after shell commands | 🟢 |

**LangSmith snapshots 迁移** (1 项):

| # | SHA | 描述 | 风险 |
| --- | --- | --- | --- |
| B11 | `a827cddf` | refactor(cli): use langsmith sandbox snapshots instead of templates | 🟡 中 |

**修复 + 测试** (~17 项): 全部 🟢 低风险

### Phase C: REPL 变更 (4 commits) — 🟢 低

| # | SHA | 描述 |
| --- | --- | --- |
| C1 | `86e459f4` | chore(repl): change representation |
| C2 | `730e0386` | chore(repl): rename task -> defer |
| C3 | `2163451e` | chore(evals): allow parameterizing with repls |
| C4 | `814918d9` | test(repl): fix snapshots |

### Phase D: ACP / Evals / Harbor (10 commits) — 🟡 中

| # | SHA | 描述 | 风险 |
| --- | --- | --- | --- |
| D1 | `bfb16a64` | feat(acp): Adds Opus 4.7 and Baseten to demo agent | 🟢 |
| D2 | `2f86825e` | fix(acp): support agent-client-protocol v0.9.0 schema changes | 🟡 中 (schema bump) |
| D3 | `63fb283f` | chore(acp): unbound ACP version | 🟢 |
| D4 | `29a351a8` | fix(acp): restore passing tests after acp v0.9 schema bump | 🟢 |
| D5 | `082b9008` | **feat(harbor,sdk): migrate LangSmith env from templates to snapshots** | 🟡 中 (+307/-166 行) |
| D6 | `b8c55136` | feat(evals): add openai:gpt-5.5 / gpt-5.5-pro | 🟢 |
| D7 | `bff92f1d` | chore(evals): add kimi models | 🟢 |
| D8 | `bb27e62e` | fix(evals): per-trial langsmith templates | 🟢 |
| D9 | `15e71633` | fix(evals): various eval fixes | 🟢 |
| D10 | `b7ad239c` | fix(evals): don't mask pytest exit 1 | 🟢 |

### Phase E: Release commits (4) — 跳过

| # | SHA | 描述 | 处理 |
| --- | --- | --- | --- |
| E1 | `cb8c9d71` | release(deepagents-cli): 0.0.39 | **不 cherry-pick** |
| E2 | `88c2b5cb` | release(deepagents-cli): 0.0.40 | **不 cherry-pick** |
| E3 | `2795a2c2` | release(deepagents-cli): 0.0.41 | **不 cherry-pick** |
| E4 | `70d39db4` | release(deepagents-acp): 0.0.6 | **不 cherry-pick** |

注意：本轮 **没有 deepagents SDK 的 release commit**，本地 SDK 仍保持 0.5.0 不变。

### Phase F: 依赖更新 (~10 commits) — 🟢 低

- langchain-openai 1.1.10/1.1.11/1.1.12 → 1.1.14 (5 个子包)
- langchain-text-splitters 1.1.0 → 1.1.2 (2 个)
- python-dotenv 1.2.1 → 1.2.2 (2 个)
- python-multipart 0.0.22 → 0.0.26 (1 个)
- nbconvert 7.17.0 → 7.17.1 (1 个)
- langsmith floor → 0.7.35 (1 个: `b5584963`)

### Phase G: CI / 基础设施 + 文档 (~25 commits) — 🟢 低

CI workflow 重构、文档更新、PR 模板等。机械合并。

---

## 关键冲突预判

### 冲突 1: `f7e37721` labelled skill sources (🟡 最高风险)

**上游改动**:

- 引入 `SkillSource = str | tuple[str, str]` 类型别名
- 新增 `_validate_tuple_source()`, `_source_path()`, `_derive_source_label()` 函数
- 修改 `_format_skills_locations()` 使用 label 而非 leaf path
- skills.py +141 行

**本地状态**: 本地 V2 SkillsMiddleware 1197 行（vs 上游 ~834 行），与 Round 14 修改的 `expose_dynamic_tools` 条件化逻辑共存。

**预期冲突**:

1. `sources` 参数类型在 `__init__` 中可能冲突（本地是 `list[str]`，上游改为 `list[SkillSource]`）
2. `_format_skills_locations` 函数可能与本地 V2 的实现冲突
3. 测试 `test_skills_middleware.py` 大量更新

**解决方案**:

- 接受上游 SkillSource 类型扩展（向后兼容：bare str 路径仍工作）
- 保留本地 V2 的所有 `load_skill`/`unload_skill`/`expose_dynamic_tools`/`allowed_skills` 逻辑
- 验证: 加 label 的 source 不影响 V2 的状态跟踪 (`skills_loaded`, `skill_resources`)

### 冲突 2: `eb9fab96` graph.py 参数重排 (🟡)

**上游改动**: `backend`/`interrupt_on` 从 `response_format` 之后移到之前。

**本地状态**: 19 个参数，本地额外有 `state_schema`、`skills_expose_dynamic_tools`，位置在中间。

**解决方案**: 接受上游新顺序，保留本地额外参数。建议位置：

```python
def create_deep_agent(
    model, tools, *,
    system_prompt, middleware, subagents,
    skills, skills_expose_dynamic_tools,  # 本地 V2 参数（紧邻 skills）
    memory, permissions,
    backend, interrupt_on,  # 上游新位置
    response_format,
    state_schema,  # 本地参数
    context_schema, checkpointer, store,
    debug, name, cache,
)
```

### 冲突 3: `3bcc51a9` + `bd6ec6bc` SubAgent tagging (🟡)

**上游改动**: 新增 `ls_agent_type` configurable tag，subagent tagging 改用 configurable 而非 tracing context。

**本地状态**: `_ENABLE_SUBAGENT_LOGGING` 环境变量门控 + `_extract_subagent_logs` + `_redact_sensitive_fields`。

**解决方案**: 上游与本地正交（上游是 LangSmith 追踪标签，本地是日志收集）。预期可干净合并，但需验证 tagging 不与本地 logging 路径冲突。

### 冲突 4: `082b9008` LangSmith snapshots migration (🟡)

**上游改动**: harbor LangSmith env 从 templates 迁移到 snapshots，`langsmith_environment.py` +307/-166 行。

**本地状态**: 我们已有 langsmith integration test xfail 标记。

**解决方案**: 接受上游迁移；验证 langsmith 0.7.35 floor + sandbox import smoke test 仍通过。

### 冲突 5: `291aebe2` CRLF preserve in sandbox edit (🟢)

**上游改动**: 沙盒 edit 保留 CRLF 行尾。

**本地状态**: Round 12 已有 `FilesystemBackend.edit()` 的 CRLF 规范化逻辑（`\r\n` → `\n`）。

**解决方案**: 上游针对 sandbox backend，本地针对 FilesystemBackend，可能不冲突。需验证两者职责分离。

---

## 合并方案

### 策略: 4 Phase + 2 Gates（与 Round 14 类似但 Phase 2 拆分）

**原因**: SDK 核心有 8 个 commits（vs Round 14 的 4 个），且 `f7e37721` 的 skills.py 改动较大。建议把 Phase 2 拆为 2a (低冲突) + 2b (高冲突) 以提高回滚粒度。

```text
Phase 1a: Deps bump 批量（~10 commits）
  - langchain-openai 1.1.14, langchain-text-splitters 1.1.2, python-dotenv 1.2.2
  - python-multipart, nbconvert, langsmith floor 0.7.35
  - 冲突策略: git checkout --theirs .
  → checkpoint-round15-phase1a-deps-done

Phase 1b: CLI/REPL 功能（~30 commits）
  - Phase B: CLI 新功能（/agents, [auth], --startup-cmd, --max-turns 等）
  - Phase C: REPL 变更
  - 跳过 4 个 release commits
  → checkpoint-round15-phase1b-cli-done

Phase 1c: ACP/Evals/CI（~30 commits）
  - Phase D 除 082b9008 外
  - Phase G: CI/docs/infra
  → checkpoint-round15-phase1c-infra-done

Gate 1: 全量测试 + langsmith 0.7.35 smoke + 跨包 relock
  → checkpoint-round15-gate1-done

Phase 2a: SDK 文件级低冲突（4 commits，不触及 graph.py/skills.py）
  - A4 (3bcc51a9) ls_agent_type configurable tag — subagents.py
  - A5 (bd6ec6bc) subagent tagging via configurable — subagents.py
  - A6 (291aebe2) CRLF preserve in sandbox — sandbox.py
  - A8 (87644b78) patch tool calls perf — patch_tool_calls.py
  → checkpoint-round15-phase2a-done

Phase 2b: graph.py + skills.py 变更簇（4 commits）+ harbor migration（架构师修正后顺序）
  顺序原则: 文件簇内按依赖关系排列，每个文件只 cherry-pick 一次冲突解决路径
  - A3 (1699f3ae) MemoryMiddleware cache breakpoint — graph.py +10
  - A1 (eb9fab96) graph.py 参数重排 — graph.py +20/-20（最后碰 graph.py）
  - A7 (e1c1d502) Windows backslash + skills _list_skills 重写 — skills.py +127
  - A2 (f7e37721) labelled skill sources — skills.py +141（最后碰 skills.py）
  - D5 (082b9008) LangSmith env snapshots — harbor only
  → checkpoint-round15-phase2b-done

Gate 2: 本地特性 11 项全检 + 新功能 smoke
  → checkpoint-round15-gate2-done

Phase 3: 验证 + 文档
  - 全量测试（5 个包）
  - 更新 CLAUDE.md（labelled skill sources, /agents 命令, model=None 已废弃但保留）
  - 更新 MEMORY.md（Round 15 状态）
  - 编写 SDK_UPGRADE_NOTICE_ROUND15.md（外部团队升级说明）
```

### Gate 1 退出条件

```bash
cd libs/deepagents && UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/ -q
cd libs/cli && uv run --group test pytest tests/unit_tests/ --disable-socket --allow-unix-socket -q --timeout 30
cd libs/evals && uv run --group test pytest tests/unit_tests/ -q --timeout 30
cd libs/acp && UV_LINK_MODE=copy uv run --group test pytest tests/ -q
cd libs/repl && UV_LINK_MODE=copy uv run --group test pytest tests/ -q

python -c "from langsmith.sandbox import Sandbox, SandboxClient; print('OK')"

cd libs/cli && uv lock --check
```

**期望**: SDK 1258p / CLI ~3070p (+5 from new tests) / Evals ~242p / ACP 76p / REPL ~70p

### Gate 2 退出条件

本地优越特性 11 项全检：

```bash
cd libs/deepagents
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/test_graph_skills_flag_wiring.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/middleware/test_subagent_logging.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/middleware/test_subagent_stream_writer.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/middleware/test_summarization_factory.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/middleware/converters/ -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/test_permissions.py -v
UV_LINK_MODE=copy uv run --group test pytest tests/unit_tests/test_subagents.py -v
```

新功能集成验证：

- `SkillsMiddleware(sources=[("/skills/user/", "User Claude")])` 正确生成 `**User Claude Skills**` header
- `/agents` 命令在 CLI 中可用
- `--startup-cmd` 和 `--max-turns` 标志生效

**CLI Help drift 检查**（架构师补充要求）:

```bash
# CLI 顶层 help 是手维护的（ui.py），新增命令/标志后需对照 command_registry
grep -E "/agents|--startup-cmd|--max-turns" libs/cli/deepagents_cli/ui.py
grep -E "/agents|--startup-cmd|--max-turns" libs/cli/deepagents_cli/command_registry.py
```

期望: ui.py 的 help 文本包含全部新增命令/标志，与 command_registry 一致。否则需手动更新 ui.py 避免 help screen drift。

---

## 时间估算

| 阶段 | 时间 | 风险 |
| --- | --- | --- |
| Phase 1a deps | 30-45 min | 🟢 |
| Phase 1b CLI/REPL | 45-60 min | 🟡 |
| Phase 1c infra | 30 min | 🟢 |
| Gate 1 | 10-15 min | 🟢 |
| Phase 2a SDK 低冲突 | 30-45 min | 🟡 |
| Phase 2b SDK 高冲突 | 60-90 min | 🟡 |
| Gate 2 | 15 min | 🟢 |
| Phase 3 测试+文档 | 60-75 min | 🟢 |
| **总计** | **4.5-6 h** | 🟡 |

---

## 回滚策略

```bash
# Gate 2 失败 → 回滚到 Phase 2a 完成点
git reset --hard checkpoint-round15-phase2a-done

# Phase 2b 失败 → 回滚到 Gate 1 完成点
git reset --hard checkpoint-round15-gate1-done

# Phase 1 失败 → 回滚到 Round 14 完成点
git reset --hard 5fe98f27

# 备份分支已建
git branch backup-pre-round15 master  # 在执行前
```

---

## 跳过 commits 清单

```text
cb8c9d71  # release(deepagents-cli): 0.0.39
88c2b5cb  # release(deepagents-cli): 0.0.40
2795a2c2  # release(deepagents-cli): 0.0.41
70d39db4  # release(deepagents-acp): 0.0.6
```

注意：

- 本轮**无 SDK release**（仍 0.5.0）
- 本地 CLI 保持 0.0.34，不跟随上游 0.0.41

---

## 本地优越特性保护清单

11 项必须验证：

| # | 特性 | 验证方法 |
| --- | --- | --- |
| 1 | state\_schema | inspect.signature(create_deep_agent).parameters |
| 2 | skills\_expose\_dynamic\_tools | 同上 |
| 3 | skills\_allowlist | test\_graph\_skills\_flag\_wiring.py |
| 4 | create\_summarization\_middleware | test\_summarization\_factory.py |
| 5 | Overwrite guard | summarization.py |
| 6 | SubAgent stream\_writer | test\_subagent\_stream\_writer.py |
| 7 | SubAgent logging | test\_subagent\_logging.py |
| 8 | Converters | middleware/converters/ |
| 9 | permissions + \_PermissionMiddleware 在栈末尾 | test\_permissions.py |
| 10 | \_HarnessProfile 加载 | test\_models.py |
| 11 | \_ToolExclusionMiddleware 在 user middleware 之后 | 中间件栈位置检查 |

---

## 风险统计（架构师修正后）

| 等级 | 数量 | 代表 |
| --- | --- | --- |
| 🔴 高 | **2** | `eb9fab96` graph.py 重排（变更簇 Go/No-Go）, `f7e37721` labelled skill sources（变更簇 Go/No-Go） |
| 🟡 中 | 6 | `1699f3ae` MemoryMiddleware (graph.py 簇), `e1c1d502` Windows path (skills.py 簇), `3bcc51a9`/`bd6ec6bc` SubAgent tagging, `082b9008` harbor snapshots, `2f86825e` ACP v0.9 schema, `a827cddf` CLI sandbox snapshots |
| 🟢 低 | 71 | 其他 |

---

## 最终建议

**架构师意见**: 可按 4 Phase + 2 Gate 推进。Phase 2b 的 `f7e37721` 是本轮最不确定项，需要先在分支上验证再决定是否继续。

**研发主管意见**: 建议预留 5-6 小时连续时间块。Phase 2b 失败概率约 20%，需有清晰的回滚到 Phase 2a 路径。

**预期交付**:

- 累计合并 ~1069 commits (Round 0-15)
- 新增外部可用能力: labelled skill sources, `/agents` switcher, custom auth, --startup-cmd, --max-turns
- 本地版本保持: SDK 0.5.0 / CLI 0.0.34
