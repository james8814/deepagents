# Round 11 上游合并风险评估

**日期**: 2026-04-04
**修订**: v2（采纳技术总监审查）

## 范围锚定

```bash
# 以上游原始 SHA 为准（cherry-pick SHA 不同但内容已在 master 中）
git rev-list --count 8be4a2ee..upstream/main  # = 39 (实际新内容)
git rev-list --count master..upstream/main     # = 124+ (含 Round 8/9/10 的 cherry-pick 差异)
```

| 端点 | SHA | 说明 |
|------|-----|------|
| Round 10 最后上游 commit | `8be4a2ee` | fix(sdk): fix TypeError in async sub-agents |
| upstream/main tip | `26647a34` | chore(deps): bump litellm (evals) |
| **实际新增** | **39** | 以上游 SHA 链为准（架构师修正：38→39） |

**anchor 选择判据**: `8be4a2ee` 是 Round 10 风险评估中列出的最后一个上游 commit，也是 Round 10 cherry-pick 的终点。Round 8/9/10 的 85 个 commits 已在 master 中（cherry-pick 方式，SHA 不同但 commit message 完全一致）。

**口径说明**: `master..upstream/main` 显示 124+ 是因为 cherry-pick 产生不同 SHA，git 将它们视为不同 commits。实际新内容只有 39 个。

---

## 总体风险等级: 🔴 高

**核心风险**: `56bbfd3a` 删除本地仍在使用的 `_get_subagents_legacy` 函数 + `acad9bb6` 重构 graph.py subagent 创建逻辑。两者组合影响本地 4 项优越特性。

---

## 关键争议点裁决（采纳技术总监建议）

### 裁决 1: `56bbfd3a` remove legacy subagents API

**技术总监建议**: "除非能证明外部与内部调用已全部迁移，否则不能直接进主干。"

**裁决**: **合入**（路线 B），但必须同步完成迁移。理由：
- 与上游在 subagents API 上对齐，减少未来 round 的结构性冲突成本
- 本地调用点明确（`subagents.py:L869`），迁移范围可控
- **主要工作量不在改调用点，而在解决 subagents.py 的结构性冲突并保留本地增强语义**（日志、stream 诊断、state key 排除等）

**迁移完成证明**（行为证明，不只是 grep）：

- 必要条件：`grep -rn "SubAgentMiddleware(default_model" libs/` 返回 0 结果
- 充分条件：8 项本地特性在以下验收用例中保持一致

| # | 特性 | 测试文件 | 失败暴露形式 |
|---|------|---------|-------------|
| 1 | `skills_allowlist` | `test_graph_skills_flag_wiring.py::test_subagent_skills_allowlist_is_wired` | AssertionError: SkillsMiddleware.allowed_skills 未收到 allowlist |
| 2 | SubAgent logging | `test_subagent_logging.py`（全文件） | AssertionError: `_extract_subagent_logs` 返回空 |
| 3 | `stream_writer` | **需新增测试**（Phase A-3 阻塞项）: 在 `test_subagents.py` 中新增用例验证 SubAgent 通过 stream_writer 发送进度事件 | AssertionError: stream events 不包含 subagent step_type/tool_name |
| 4 | `_EXCLUDED_STATE_KEYS` | `test_subagents.py`（含 "excluded" 断言） | AssertionError: parent state 包含 todos/messages 等 excluded keys |
| 5 | `create_summarization_middleware` | `test_summarization_factory.py`（全文件） | ImportError 或 TypeError（函数签名变更） |
| 6 | `state_schema` | `tests/utils.py` 中 `ResearchState`/`SampleState` 使用 | E2E 测试失败：state 类型不匹配 |
| 7 | Overwrite guard | `test_middleware.py::test_*overwrite*` | AssertionError: state_update 不是 Overwrite 实例 |
| 8 | Converters | `tests/unit_tests/middleware/converters/` (23 tests) | 转换失败或 ImportError |

验证命令（在 `libs/deepagents/` 目录下）：
```bash
pytest tests/unit_tests/test_graph_skills_flag_wiring.py -v
pytest tests/unit_tests/middleware/test_subagent_logging.py -v
pytest tests/unit_tests/test_subagents.py -v -k "excluded"
pytest tests/unit_tests/middleware/test_summarization_factory.py -v
pytest tests/unit_tests/test_middleware.py -v -k "overwrite"
pytest tests/unit_tests/middleware/converters/ -v
```

### 裁决 2: `acad9bb6` inherit parent interrupt_on

**技术总监建议**: "建议合入，但要做灰度/开关策略。"

**裁决**: **合入**。不做单独开关，但提供清晰的 opt-out 路径。

**opt-out 机制**（上游实现：`spec.get("interrupt_on", interrupt_on)`）：SubAgent 显式设置 `interrupt_on: {}` 即可不继承 parent。

**⚠️ 合并时必须代码核对**（架构师要求）：本地 graph.py / subagents.py 已有较多定制，merge 冲突时最容易"语义丢失但编译通过"。合并后必须在最终代码中 grep 确认 `spec.get("interrupt_on", interrupt_on)` 这一行存在且语义正确。

**必须补的回归测试**（架构师要求）：

- 继承行为：parent 设 `interrupt_on={"edit_file": True}`，未配置的 declarative SubAgent 确实继承
- opt-out 行为：SubAgent 显式设 `interrupt_on: {}`，确认不触发 HITL
- CompiledSubAgent 不继承：预编译 subagent 不受 parent interrupt_on 影响
- AsyncSubAgent 不继承：远程 subagent 不受影响

**迁移指南**（给调用方的操作性文档）：
> 如果你的 SubAgent 之前依赖"静默执行不弹审批"的行为，在升级后需要显式添加 `interrupt_on: {}` 到该 SubAgent 的配置中。

### 裁决 3: `5a451490`/`378b84e2` release commits

**技术总监建议**: "不建议把 release commit 当作普通上游 sync 直接合。版本号由你们自己按内部发布节奏决定。"

**裁决**: **采纳**。
- 功能性 commit 先合
- 版本号保留我们的 `0.5.0`（不跟上游 `0.5.0a3`/`0.5.0a4`）
- lockfile 在最后单独处理

### 裁决 4: `b1670136` ACP 安全修复

**技术总监建议**: "建议立即 cherry-pick 进入安全补丁线。"

**裁决**: **采纳**。排在 Phase A-1 最前面。

---

## 逐 Commit 风险评估

### Phase A-1: 安全 + SDK 安全变更 (4 commits)

| # | SHA | 描述 | 风险 |
|---|-----|------|------|
| 1 | `b1670136` | **block dangerous shell patterns in ACP** | 🟢 安全优先 |
| 2 | `ebf43401` | delete unused base_prompt.md | 🟢 |
| 3 | `914eb9ec` | failing test for callback propagation | 🟢 |
| 4 | `4a37a469` | improve sandbox.write/read | 🟡 |

### Phase A-2: SDK 协议/类型 (2 commits)

| # | SHA | 描述 | 风险 |
|---|-----|------|------|
| 5 | `d3af2aed` | update unset logic (protocol.py) | 🟡 |
| 6 | `6c28e22c` | plumb through generics (graph.py) | 🟡 类型签名，`make lint` (含 ty) 必须 0 新增错误 |

### Phase A-3: SDK subagents 重构 (2 commits) — 🔴 最高风险

| # | SHA | 描述 | 风险 |
|---|-----|------|------|
| 7 | `acad9bb6` | inherit parent interrupt_on | 🔴 graph.py +185/-8，subagent 创建逻辑重构 |
| 8 | `56bbfd3a` | **remove legacy subagents API** | 🔴 subagents.py -388 行，本地 `_get_subagents_legacy` 调用必须迁移 |

### Phase B: Evals/CI (14 commits) — 🟢

| # | SHA | 描述 |
|---|-----|------|
| 9-22 | 各种 | CI 改进、evals 链接、catalog、model groups 等 |

### Phase C: ACP/examples/docs (4 commits) — 🟢

| # | SHA | 描述 |
|---|-----|------|
| 23 | `303c424a` | async subagent example |
| 24 | `5bd164c9` | ACP demo fix |
| 25 | `3423205b` | update async subagent docs |
| 26 | `6d63b318` | bump lock files |

### Phase D: 依赖 bump (7 commits) — 🟢

| # | SHA | 描述 |
|---|-----|------|
| 27-33 | deps | aiohttp, anthropic, litellm, lockfiles |

### Phase E: 版本号 + lockfile (2 commits) — 特殊处理

**策略**（架构师修正）：完全不 cherry-pick release commits。依赖声明与 lockfile 由我们在固定 uv 版本下统一重算，避免"只合一半"导致依赖声明与锁文件错配。

具体操作：

- 从 `378b84e2` 中**手动提取** `langchain>=1.2.15` 依赖下限变更到我们的 `pyproject.toml`
- 版本号保留 `0.5.0`（不跟上游 `0.5.0a3`/`0.5.0a4`）
- 运行 `uv lock` 在我们的固定环境重算所有 lockfile
- **硬门禁**（架构师要求）：提取后必须在同一套 lockfile 下通过以下全部检查（**在 `libs/` 目录执行**，仓库根目录无 Makefile），否则 lockfile 只是形式一致，运行时仍可能漂移：

  ```bash
  make -C libs lock-check                        # lockfile 一致性
  make -C libs/deepagents lint && make -C libs/deepagents test  # SDK
  make -C libs/cli lint && make -C libs/cli test                # CLI
  make -C libs/evals lint && make -C libs/evals test            # Evals
  ```

| # | SHA | 描述 | 处理方式 |
|---|-----|------|---------|
| 34 | `5a451490` | release 0.5.0a3 | **不 cherry-pick，手动提取必要依赖变更** |
| 35 | `378b84e2` | release 0.5.0a4 | **不 cherry-pick，手动提取 langchain>=1.2.15** |

### Phase F: 其余 CI/build (3 commits) — 🟢

| # | SHA | 描述 |
|---|-----|------|
| 36-38 | CI | eval catalog auto-regen, release permissions, issue link |

---

## Phase A-3 SubAgent 迁移计划

### 迁移目标

将本地对 `_get_subagents_legacy` 的调用迁移到上游新 API `_get_subagents`。

### 需要迁移的本地特性

| 特性 | 当前实现位置 | 迁移策略 |
|------|------------|---------|
| `skills_allowlist` | graph.py SubAgent 创建路径 | 适配新 `_get_subagents` 的参数传递 |
| SubAgent logging | subagents.py `_ENABLE_SUBAGENT_LOGGING` | 在新 API 路径中保留环境变量检查 |
| `stream_writer` progress | subagents.py `stream_writer` 使用 | 确认新 API 是否支持 stream_writer |
| `create_summarization_middleware` | graph.py | 不受 subagent API 变更影响（在 middleware 层） |

### 迁移前必须验证

```bash
# 在 libs/deepagents/ 目录下执行
# 1. 协议/后向兼容
pytest tests/unit_tests/backends/test_protocol.py -v
# 2. SubAgent 完整测试
pytest tests/unit_tests/test_subagents.py -v
# 3. E2E 测试
pytest tests/unit_tests/test_end_to_end.py -v -k "subagent"
# 4. 本地优越特性 8 项全检
```

---

## 每 Phase 门禁

| Phase | 门禁 | 额外要求 |
|-------|------|----------|
| A-1 | SDK+ACP: `make lint && make test` | ACP 安全测试 |
| A-2 | SDK: `make lint && make test` | ty 0 新增错误 |
| A-3 | SDK: `make lint && make test` | **干净 venv `--reinstall`** + 本地优越特性 8 项全检 + SubAgent 迁移验证 |
| B | Evals: `make lint && make test` | — |
| C-D | 全包: `make test` | — |
| E | SDK: `make test` | 版本号保留 0.5.0 |
| F | — | CI 配置，不影响测试 |

## 每 Phase 回滚策略

| Phase | 回滚 |
|-------|------|
| A-1 | `git reset --hard` 到 Phase 起点 |
| A-2 | `git reset --hard` 到 A-1 检查点 |
| A-3 | `git reset --hard` 到 A-2 检查点（**最可能需要回滚**） |
| B-F | 各自 Phase 起点 |

---

## 风险等级统计

| 等级 | 数量 | 代表 |
|------|------|------|
| 🔴 高 | 2 | remove legacy subagents API, inherit interrupt_on |
| 🟡 中 | 3 | generics, unset logic, sandbox improvements |
| 🟢 低 | 33 | 安全修复/测试/evals/CI/deps/examples |

## 时间估算

| Phase | 预计时间 | 风险 |
|-------|---------|------|
| Phase A-1 | 30 min | 🟢 |
| Phase A-2 | 45 min | 🟡 |
| Phase A-3 | **3-5 h** | 🔴 |
| Phase B | 30 min | 🟢 |
| Phase C-D | 30 min | 🟢 |
| Phase E | 20 min | 🟡 |
| Phase F | 10 min | 🟢 |
| 测试验证 | 1 h | — |
| **总计** | **7-9 h** | 🔴 |

---

## 建议采纳记录

### 技术总监建议 (v1)

| 建议 | 采纳 | 修正内容 |
|------|------|----------|
| `56bbfd3a` 需迁移证明 | ✅ | Phase A-3 增加迁移计划和验证清单 |
| `acad9bb6` 需灰度/说明 | ✅ 部分 | 不做开关，但明确记录行为变化 |
| `b1670136` 安全优先 | ✅ | 排在 Phase A-1 第一位 |
| release commits 特殊处理 | ✅ | 版本号保留 0.5.0 |
| lockfile 单独治理 | ✅ | lockfile 统一处理 |
| 两条线并行 | ❌ | 简化为单一集成线 |
| 类型变更走 ty 门槛 | ✅ | Phase A-2 `make lint`(含 ty) 0 新增错误 |

### 架构师审查修正 (v2)

| 修正项 | 内容 |
|--------|------|
| commit 数量 38→39 | 修正为当前可复现值，并补充 anchor 选择判据 |
| `56bbfd3a` 依赖论证 | 删除错误的"后续 commit 依赖它"论述，改为"与上游对齐减少未来结构性冲突" |
| `56bbfd3a` 迁移证明 | 从 grep 提升为行为证明（8 项验收用例） |
| `acad9bb6` opt-out 路径 | 增加具体实现（`interrupt_on: {}`）+ 4 项回归测试 + 迁移指南 |
| Phase E release commits | 从"只合一半"改为"完全不 cherry-pick，手动提取 + uv lock 重算" |
| A-1 安全先行 checkpoint | 强制在进入 A-3 前将 A-1 合并到可回退点 |
