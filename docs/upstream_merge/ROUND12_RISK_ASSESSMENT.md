# Round 12 上游合并风险评估

**日期**: 2026-04-07

## 范围锚定

| 端点 | SHA |
|------|-----|
| Round 11 最后上游 | `26647a34` |
| upstream/main tip | `39b43cf8` |
| **新增** | **19 commits** |

---

## 总体风险等级: 🟢 低

本轮以 CLI 修复和新功能为主，无高风险 SDK 核心重构。`graph.py` 有 258 行 diff 但主要是文档/docstring 改进（`9c94c797`, `825147fe`），不是行为变更。

---

## 逐 Commit 风险评估

### SDK (5 commits)

| # | SHA | 描述 | 风险 | 分析 |
|---|-----|------|------|------|
| 1 | `c36a41cc` | fix closing tag in task tool prompt | 🟢 | subagents.py 快照 JSON 修正，6 files 各改 1-2 行 |
| 2 | `9c94c797` | docs for create_deep_agent | 🟡 | graph.py +88/-48，主要是 docstring 重写。**graph.py 有本地 state_schema 等特性** |
| 3 | `825147fe` | fill missing docstrings | 🟡 | graph.py +30, summarization.py +12。docstring 新增，不改逻辑 |
| 4 | `b88cb8d0` | replace old OAI model strings | 🟢 | 测试文件 + evals 中的模型名更新 |
| 5 | `dda01a13` | add minimal REPL | 🟢 | **新模块** `libs/repl/`（5238 行），独立目录。需确认：不被 SDK/CLI 引用、不影响 lockfile/CI、不被发布产物打包 |

### CLI (9 commits)

| # | SHA | 描述 | 风险 | 分析 |
|---|-----|------|------|------|
| 6 | `281899bf` | align headless todo guidance | 🟢 | agent.py +22, system_prompt.md -5 |
| 7 | `b6997d83` | resolve langsmith env var precedence | 🟡 **中风险** | **行为变更**: 同时设 canonical + prefixed 时从"各用各的"改为"统一用 prefixed"。需验收 env var 优先级矩阵 |
| 8 | `a3e1e936` | show server startup error | 🟢 | command_registry.py + test_app.py |
| 9 | `5f0f1d46` | --skill startup invocation | 🟡 **中风险** | **10 files, +741/-134**。CLI 启动热路径新入口。需验证：argparse↔help screen drift, 启动性能（无重依赖 import 到参数解析路径） |
| 10 | `02e46bc4` | dismiss autocomplete on space | 🟢 | autocomplete.py +5 |
| 11 | `01d3d864` | stop loading widget timer leak | 🟢 | loading.py +25, 新测试 |
| 12 | `c14a7483` | guard cursor/document desync crash | 🟢 | chat_input.py +33, 防崩溃修复 |
| 13 | `39b43cf8` | sort MCP tools deterministically | 🟢 | mcp_tools.py +5, 新测试 |
| 14 | `df3709cb` | update Makefile for examples lock | 🟢 | Makefile 改动 |

### CI/chore/docs (5 commits)

| # | SHA | 描述 | 风险 |
|---|-----|------|------|
| 15 | `b5fa0027` | quickjs README clarify internal | 🟢 |
| 16 | `7a64c194` | bump uv group deps | 🟢 |
| 17 | `46c745c9` | fix CI auto-labeler | 🟢 |
| 18 | `33891966` | update CODEOWNERS | 🟢 |
| 19 | `441781cb` | convert working-directory to dropdown | 🟢 |

---

## 冲突预判

| 文件 | 上游修改 | 本地修改 | 冲突概率 |
|------|---------|---------|----------|
| `graph.py` | docstring 重写 (+118/-50) | state_schema, create_summarization_middleware | 🟡 中 — docstring 区域可能重叠 |
| `config.py` | env var precedence fix | build_stream_config, ls_integration | 🟢 低 — 不同区域 |
| `subagents.py` | closing tag fix | stream_writer, logging | 🟢 低 — 快照文件，不是源码 |
| `command_registry.py` | server error command | /upload, /auto-update | 🟢 低 |
| `main.py` | --skill invocation | agents subcommand | 🟡 中 — main.py 多次修改 |

---

## 合并方案

**单阶段合并**（风险低，无需分 Phase）：

**两段合入**（架构师建议：低风险先行，🟡 段可独立回滚）：

```
# 段 1: 低风险（docs/ci/小修）— 先合，锁定收益
c36a41cc  fix closing tag in task prompt
9c94c797  docs for create_deep_agent
825147fe  fill missing docstrings
b88cb8d0  replace old OAI model strings
dda01a13  add minimal REPL
281899bf  align headless todo guidance
a3e1e936  show server startup error
02e46bc4  dismiss autocomplete on space
01d3d864  stop loading widget timer leak
c14a7483  guard cursor/document desync crash
39b43cf8  sort MCP tools deterministically
df3709cb  update Makefile for examples lock
b5fa0027  quickjs README
7a64c194  bump uv group deps
46c745c9  fix CI auto-labeler
33891966  update CODEOWNERS
441781cb  convert working-directory to dropdown

# 段 2: 🟡 中风险（env var + --skill）— 段 1 稳定后再合
b6997d83  resolve langsmith env var precedence
5f0f1d46  --skill startup invocation
```

### 门禁

```bash
# 段 1 完成后
cd libs/deepagents && make lint && make test
cd libs/cli && make lint && make test

# 段 2 完成后（额外验证）
cd libs/cli && make lint && make test
pytest tests/unit_tests/test_config.py -v -k "langsmith or prefix"
pytest tests/unit_tests/test_args.py -v  # drift test
time deepagents --help  # 启动性能采样
```

### 硬验收条款（架构师要求，v2）

#### 1. Env var precedence（`b6997d83`）

**规则表**:

| 场景 | 行为 |
|------|------|
| 仅 canonical `X` | 使用 `X` |
| 仅 prefixed `DEEPAGENTS_CLI_X` | 使用 prefixed |
| 两者同时设置，值相同 | 使用 prefixed（无警告） |
| 两者同时设置，值不同 | **使用 prefixed**，覆盖 canonical，打印 warning |
| prefixed 为空字符串 | 屏蔽 canonical（`resolve_env_var` 返回 `None`） |
| canonical 为空字符串 | 视为未设置，不会被 prefixed 覆盖 |
| `/reload` 后 | shell export 仍优先于 `.env`（`override=False`） |

**测试矩阵**（合并后验证）:
```bash
pytest tests/unit_tests/test_config.py -v -k "langsmith or env_var or prefix"
pytest tests/unit_tests/test_reload.py -v -k "prefix or override"
```

**用户告警策略**: 冲突检测时输出明确提示（不泄露值）：`"Both X and DEEPAGENTS_CLI_X are set with different values; using DEEPAGENTS_CLI_X. Unset X to silence this warning."`。这确保旧 canonical 配置不会在无提示情况下静默失效。

**验收一句话**: 遵循 prefixed 配置的用户行为稳定；旧 canonical 配置在有 prefixed 冲突时会被覆盖并打印 warning（不会静默失效）。

#### 2. --skill（`5f0f1d46`）

**行为型约束**（强约束）:

- `--help`、`-v`、参数解析阶段：不得触发技能扫描/加载
- `--skill` 必须是显式 opt-in：不传则默认行为完全不变

**失败模式**: 传 `--skill` 但 skill 不存在/加载失败时，必须友好错误 + 非 0 退出码（`SystemExit(1)`），不得降级忽略或触发 Textual markup 崩溃。需有测试覆盖。

**drift 检查范围**:
- argparse 定义（`main.py`）
- `ui.show_help()` 手维护 help 屏
- drift test: `pytest tests/unit_tests/test_args.py -v`

**性能验证**:
```bash
# 行为型：确认 --help 不触发 skill 加载
python -X importtime -m deepagents_cli --help 2>&1 | grep -i "skill"
# 采样型：与基线对比（不应显著变慢）
time deepagents --help
```

#### 3. libs/repl（`dda01a13`）

**引用边界**: CLI/SDK 入口不应 import libs/repl（含可选路径、type-check 导入）
```bash
grep -rn "repl\|deepagents_repl" libs/deepagents/ libs/cli/ --include="*.py" --include="*.toml"
```

**依赖边界**: repl 的 uv.lock 不应影响其他包的 lockfile
```bash
# repl 有独立的 uv.lock，不在 libs/Makefile 的 lock-check 范围内
ls libs/repl/uv.lock
```

**发布边界**: repl 不应被 CLI/SDK 的安装 extra 或默认依赖"顺带装进去"
```bash
grep "repl" libs/deepagents/pyproject.toml libs/cli/pyproject.toml  # 应返回空
```

### 额外关注点（架构师提醒）

- **model_config.py / env var 工具函数**: 与 `b6997d83` 变更相关，注意 `resolve_env_var` 的行为是否一致
- **CI 门禁**: `check_lockfiles`, `check_versions`, `check_sdk_pin` 对新包/新入口敏感
- **--skill 可发现性**: 如需同步提示/示例，在文档更新阶段处理

### 回滚（分段）

```bash
# 段 2 回归 → 只回滚 🟡 段，保留段 1 收益
git reset --hard checkpoint-round12-segment1-done

# 段 1 回归 → 回滚全部
git reset --hard backup-pre-round12
```

---

## 时间估算

| 阶段 | 时间 |
|------|------|
| cherry-pick 19 commits | 30-45 min |
| 冲突解决（graph.py docstring） | 15 min |
| 测试验证 | 15 min |
| **总计** | **1-1.5 h** |

## 风险统计

| 等级 | 数量 |
|------|------|
| 🟡 中 | 3 (graph.py docs, config.py env, --skill invocation) |
| 🟢 低 | 16 |
