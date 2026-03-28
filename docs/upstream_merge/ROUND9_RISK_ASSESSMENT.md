# Round 9 上游合并风险评估

**日期**: 2026-03-28
**修订**: v2（采纳架构师审查）

---

## 范围锚定（可复算）

```bash
# 复算命令
git rev-list --count <master-tip>..upstream/main
```

| 端点 | SHA | 说明 |
|------|-----|------|
| master tip | `a12d1dc5` | Round 8 merge commit |
| upstream/main tip | `9bddc52b` | fix(cli): eliminate trace fragmentation |
| `upstream/main --not master` | **52** | 含 Round 8 已 cherry-pick 的 10 个 |
| Round 8 已合并 | **10** | SHA 不同但 commit message 完全匹配（cherry-pick） |
| **实际新增** | **42** | 20 功能性 + 22 依赖 bump |

---

## 总体风险等级: 🟡 中等

大部分是 CLI 增强（不涉及 SDK 核心逻辑），依赖 bump 低风险。但有 3 个大型 CLI 重构（700-900 行）和 1 个配置/启动路径大改需要重点处理。

---

## 逐 Commit 风险评估

### Phase A: SDK 变更 (3 commits)

| # | SHA | 描述 | 风险 | 冲突文件 | 分析 |
|---|-----|------|------|----------|------|
| 1 | `fd91a30b` | update recursion limit (10000→10001) | 🟢 低 | graph.py | 单行改动。graph.py 有大量本地优越特性（state_schema, skills_expose_dynamic_tools），但此改动仅在 `with_config` 行，不会冲突 |
| 2 | `5e23d6d9` | declare schema up front for remaining tools | 🟡 中 | subagents.py, async_subagents.py | Pydantic Schema 替代 Annotated（与 Round 8 同模式）。**subagents.py 有本地 `skills_allowlist` 修改需保留** |
| 3 | `34cb7aab` | add end-to-end test for compaction tool | 🟡 中 | summarization.py, test_end_to_end.py | **双重变更**: 新增 compaction E2E 测试 + 注释掉 Round 8 刚加的 `infer_schema=False` / `args_schema=CompactConversationSchema`（上游在测试中发现 schema 声明导致问题后回退）。test_end_to_end.py 可能与本地 `test_custom_state_schema` 冲突 |

### Phase B: CLI 小改动 (12 commits)

| # | SHA | 描述 | 风险 | 冲突文件 | 分析 |
|---|-----|------|------|----------|------|
| 4 | `e859077f` | exit app on ctrl+d when thread list empty | 🟢 低 | thread_selector.py | 7 行，独立功能 |
| 5 | `5dd80983` | add ls_integration metadata to traces | 🟢 低 | config.py | 11 行，config.py 不同区域 |
| 6 | `8f718650` | allow color overrides on themes | 🟢 低 | theme.py | 独立文件，无本地修改 |
| 7 | `a3b61e5d` | warn agent filesystem inaccessible in sandbox | 🟢 低 | agent.py | agent.py sandbox 分支 |
| 8 | `ad70bde0` | /auto-update toggle | 🟢 低 | update_check.py, welcome.py | 新功能，独立 |
| 9 | `15867bfa` | disable markup for blocked-link notifications | 🟢 低 | _links.py | 小改动 |
| 10 | `7178b872` | default langsmith project to 'deepagents-cli' | 🟢 低 | config.py | 4 行 |
| 11 | `28a32b7d` | enforce approval toggle with -y | 🟢 低 | main.py | 7 行 |
| 12 | `7f5c3de9` | reduce health poll interval | 🟢 低 | server.py | 独立文件 |
| 13 | `b4520324` | open trace in browser immediately | 🟡 中 | app.py | app.py 有 Round 8 变更（/model defer），49 行 |
| 14 | `42bccca0` | escape exception text in rich markup | 🟢 低 | main.py | 15 行 |
| 15 | `744b81b3` | sync lockfiles | 🟢 低 | uv.lock 文件 | 仅 lockfile |

### Phase C: CLI 大型重构 (3 commits) — 重点关注

| # | SHA | 描述 | 风险 | 变更量 | 分析 |
|---|-----|------|------|--------|------|
| 16 | `0a410b4a` | defer pydantic/adapter imports | 🟡 中 | +197/-95 (6 files) | textual_adapter.py 有 Round 8 `format_duration` 重构。延迟导入改动可能与本地代码结构冲突 |
| 17 | `5a21d0ad` | load ~/.deepagents/.env as global dotenv | 🟡 中 | +257/-13 (2 files) | config.py dotenv 加载区域重构。**是 commit 20 (env prefix) 的前置依赖** |
| 18 | `386438f6` | agent-friendly UX for scripted workflows | 🟠 中高 | +911/-61 (9 files) | 大量 CLI 参数重构（--dry-run, agents 子命令, --stdin）。main.py 被多次修改 |

### Phase D: env var prefix — 最高风险

| # | SHA | 描述 | 风险 | 变更量 | 分析 |
|---|-----|------|------|--------|------|
| 19 | `29647bb4` | DEEPAGENTS_CLI_ env var prefix + dotenv fix | 🔴 高 | +778/-132 (18 files) | 见下方专项分析 |

### Phase E: trace fragmentation

| # | SHA | 描述 | 风险 | 变更量 | 分析 |
|---|-----|------|------|--------|------|
| 20 | `9bddc52b` | eliminate trace fragmentation | 🟠 中高 | +822/-89 (16 files) | 新增 ShellAllowListMiddleware，修改非交互模式架构 |

### Phase F: 依赖 bump (22 commits)

#### F1: cryptography 46.0.5 → 46.0.6 (🟡 中风险，平台 wheel/ABI/SSL 行为)

| SHA | 包 |
|-----|-----|
| `025c20e2` | libs/cli |
| `dd287d5c` | libs/deepagents |
| `1d728308` | libs/evals |
| `afddf4e0` | libs/acp |
| `4c875e54` | libs/partners/runloop |
| `1006ec44` | libs/partners/quickjs |
| `f74df494` | libs/partners/modal |
| `d893a17e` | libs/partners/daytona |
| `5f1d76f6` | examples/nvidia_deep_agent |
| `5a990d19` | examples/deep_research |

**门禁**: 批量 cherry-pick 后，`uv sync --reinstall` 验证所有核心包安装成功。

#### F2: langchain-core → 1.2.22 (🟡 中风险，API/行为细变动)

先合库侧（SDK/CLI），再合 examples，避免示例 lockfile 影响主线判断。

| SHA | 包 | 优先级 |
|-----|-----|--------|
| `a1579775` | libs/deepagents | 先合 |
| `b33a35c4` | libs/cli | 先合 |
| `7acff549` | libs/evals | 先合 |
| `a4349fc3` | libs/acp | 先合 |
| `27c9cd15` | libs/partners/runloop | 后合 |
| `03d07e8c` | libs/partners/quickjs | 后合 |
| `0d73ed9b` | libs/partners/modal | 后合 |
| `8f78c0f0` | libs/partners/daytona | 后合 |
| `7fc3631e` | examples/text-to-sql-agent | 最后 |
| `2d43a1e3` | examples/nvidia_deep_agent | 最后 |
| `3cff6816` | examples/deep_research | 最后 |
| `77b4dc90` | examples/content-builder-agent | 最后 |

---

## 专项分析: `29647bb4` env var prefix 兼容性

### 变更本质

引入 `DEEPAGENTS_CLI_` 前缀机制：`DEEPAGENTS_CLI_OPENAI_API_KEY` 覆盖 `OPENAI_API_KEY`。

### env var 优先级（合并后）

```text
DEEPAGENTS_CLI_{NAME}  >  shell export {NAME}  >  project .env  >  ~/.deepagents/.env
```

### 兼容性策略

- **旧 env var 保留**: `OPENAI_API_KEY` 等不带前缀的变量仍然有效（`resolve_env_var` 先查前缀，查不到回退到原名）
- **dotenv override 行为变更**: `/reload` 不再覆盖 shell export（`override=False`），这是行为变更
- **新增 `_env_vars.py`**: 集中管理 `DEEPAGENTS_CLI_*` 常量，有 drift-detection 测试

### 回归验证重点

```bash
# 1. 无前缀 env var 仍然工作
OPENAI_API_KEY=sk-test deepagents --model openai:gpt-4.1  # 应正常启动

# 2. 前缀优先于非前缀
OPENAI_API_KEY=sk-old DEEPAGENTS_CLI_OPENAI_API_KEY=sk-new deepagents  # 应用 sk-new

# 3. /reload 不覆盖 shell export
export OPENAI_API_KEY=sk-shell  # 然后在 .env 中写不同值
deepagents → /reload  # OPENAI_API_KEY 应仍为 sk-shell

# 4. 启动热路径无重依赖导入
time deepagents --help  # 应 <1s
```

### 兼容性断言

| 断言 | 预期 |
|------|------|
| 旧 env var（如 `OPENAI_API_KEY`）仍被识别 | ✅ 是，`resolve_env_var` 先查前缀、查不到回退原名 |
| 旧 env var 何时废弃 | 无废弃计划，前缀是**可选增强**而非替代 |
| 是否打印 deprecation 提示 | 否（不影响启动热路径，不产生额外日志噪声） |
| 前缀与非前缀同时存在时行为 | 前缀优先，非前缀作为回退。同时存在但值不同时，LangSmith 相关变量会打印 warning |

---

## 冲突热点文件

| 文件 | 被修改次数 | 本地有改动 | 冲突概率 |
|------|-----------|-----------|----------|
| `config.py` | 4 | ✅ (build_stream_config) | 🔴 高 |
| `main.py` | 5 | ✅ (Round 7) | 🟡 中 |
| `app.py` | 4 | ✅ (Round 8 /model defer) | 🟡 中 |
| `agent.py` | 4 | ✅ (Round 8 task badge) | 🟡 中 |
| `summarization.py` | 2 | ✅ (Overwrite + Round 8 schema) | 🟡 中 |
| `graph.py` | 1 | ✅ (大量本地优越) | 🟢 低（仅 1 行） |
| `subagents.py` | 1 | ✅ (skills_allowlist) | 🟡 中 |

---

## 合并方案

### 合并顺序（按依赖关系 + 风险递增）

```
Phase A: SDK (3 commits)              → 为后续 CLI 提供稳定基础
Phase B: CLI 小改动 (12 commits)       → 大部分 🟢 自动合并
Phase C: CLI 大重构 (3 commits)        → 逐个审查，注意 config.py 按序
Phase D: env var prefix (1 commit)     → 🔴 最后处理，依赖 Phase C 的 dotenv
Phase E: trace fragmentation (1 commit)→ 🟠 独立于 D，同样大
Phase F1: cryptography bump (10)       → 批量，干净 venv 验证
Phase F2: langchain-core bump (12)     → 先库侧后 examples
```

### 每个 Phase 的门禁

| Phase | 门禁 | 额外要求 |
|-------|------|----------|
| A | SDK: `make lint && make test` | — |
| B | CLI: `make lint && make test` | — |
| C | CLI: `make lint && make test` | config.py 变更后额外验证 `--help` 启动时间 |
| D | CLI: `make lint && make test` | **干净 venv `--reinstall`** + env var 优先级 4 项回归 |
| E | CLI: `make lint && make test` | 非交互模式 trace 连贯性验证 |
| F1 | 全包: `uv sync --reinstall` | cryptography wheel 安装成功 |
| F2 | SDK+CLI+evals: `make test` | langchain-core API 兼容性 |

### 每 Phase 回滚策略

| Phase | 回滚方式 |
|-------|----------|
| A | `git reset --hard checkpoint-round9-phaseA-start` (SDK 变更少，直接回退) |
| B | `git revert --no-commit HEAD~N..HEAD` 回退该批次，或 `git reset --hard checkpoint-round9-phaseB-start` |
| C | `git reset --hard checkpoint-round9-phaseC-start`（config.py 逐步改动，部分回退不可行，只能整批） |
| D | `git revert HEAD`（单 commit，直接 revert） |
| E | `git revert HEAD`（单 commit，直接 revert） |
| F | `git reset --hard checkpoint-round9-phaseF-start`（lockfile 批量改动，整批回退） |

### 关键冲突预案

**`34cb7aab` 拆分评审**（虽然是单 commit，但包含两块独立变更，必须分开审）:

- **变更 A: E2E 测试增加** (test_end_to_end.py +78 行)
  - 风险维度: 测试执行时长、稳定性（是否依赖外部状态）
  - 审查重点: 新测试是否与本地 `test_custom_state_schema` 冲突
  - 策略: 两者都保留（不同 class / 不同方法）

- **变更 B: summarization schema 回退** (summarization.py -2 行)
  - 风险维度: 行为变更 — Round 8 加的 `infer_schema=False` + `args_schema` 被注释掉
  - 审查重点: 为什么上游回退？是 schema 导致 compaction tool 参数解析异常
  - 策略: 接受上游回退（他们在 E2E 测试中验证了回退后行为正确）。同时保留本地 `Overwrite` import

**subagents.py (commit 2)**:
- 上游用 `TaskToolSchema` (Pydantic) 替代 `Annotated` 参数
- 本地有 `skills_allowlist` 在 SubAgent TypedDict
- **策略**: 接受 Schema 替换，保留 skills_allowlist（不同代码区域）

**config.py (commits 5, 10, 17, 19)**:
- 4 个 commit 逐步修改，最终重构 env var 处理
- 本地有 `build_stream_config` 迁移
- **策略**: 严格按时间序逐个合并，每个冲突点保留 build_stream_config

**graph.py (commit 1)**:
- 仅 `recursion_limit: 10000 → 10001`
- **策略**: 应自动合并

---

## CLI 三大重构回归重点

| Commit | 回归重点 |
|--------|----------|
| `386438f6` headless/scripted UX | 非 TTY、管道输入、退出码、`ctrl+d`、无线程场景 |
| `9bddc52b` trace fragmentation | 非交互模式下 trace 连贯性、输出格式不破坏现有解析 |
| `29647bb4` env/dotenv | `--help`/`-v` 启动热路径不引入重依赖、env var 优先级 4 项 |

---

## 时间估算

| Phase | 预计时间 | 风险 |
|-------|---------|------|
| Phase A: SDK | 30 min | 🟡 |
| Phase B: CLI 小改动 | 45 min | 🟢 |
| Phase C: CLI 重构 | 1.5-2 h | 🟡 |
| Phase D: env var prefix | 1-1.5 h | 🔴 |
| Phase E: trace fragmentation | 1 h | 🟠 |
| Phase F: 依赖 bump | 30 min | 🟡 |
| 测试验证 | 1 h | — |
| **总计** | **5-7 h** | 🟡 |

---

## 架构师审查修正记录

| 问题 | 修正 |
|------|------|
| commit 范围口径无锚定 | 增加"范围锚定"节，含 master/upstream tip SHA + 可复算命令 |
| `34cb7aab` 描述不精确 | 修正为"双重变更：新增 compaction E2E 测试 + 注释掉 schema 声明"，以实际 diff 为准 |
| `29647bb4` 缺兼容性策略 | 新增"专项分析"节，含 env var 优先级链 + 4 项回归验证 |
| 依赖 bump 未分类 | 拆分为 F1(cryptography) + F2(langchain-core)，先库侧后 examples |
| 缺干净 venv 门禁 | Phase D/F1 增加 `--reinstall` 强制要求 |
| 缺 CLI 大重构回归重点 | 新增"CLI 三大重构回归重点"节 |
