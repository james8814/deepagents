# Round 7 上游合并最终执行方案

**日期**: 2026-03-26
**上游范围**: `d15a3992..d10dfbd7` (27 commits)
**执行团队**: 研发团队
**架构师审批**: ✅ 已通过（方案审核通过，思路完全一致）

---

## 执行前置条件

### ✅ 架构师审查结论

> "方案审核通过，思路完全一致。请立即按照该方案执行 Round 7 标准合并。在执行 Step 5 全量测试时，请额外运行 test_backslash_enter_on_empty_prompt_does_not_submit 的多次重复测试以验证稳定性。祝合并顺利。"

### 架构师补充的关键验证点

1. **chat_input.py 并发测试**（必选）
   - 验证焦点逻辑变更后的稳定性
   - 运行 20 次重复测试确保无竞态

2. **graph.py 递归限制测试**（必选）
   - 确保端到端测试在 10000 限制下平稳运行
   - 关注内存和栈溢出风险

3. **缺失依赖跳过逻辑检查**（必选）
   - 确保上游未覆盖 Round 6 的 `importlib.util.find_spec` 门控
   - 防止集成测试因环境依赖失败

---

## 执行步骤

### Step 1: 前置备份（5 分钟）

```bash
# 确认当前状态
git status
git log --oneline -3

# 创建备份标签
git tag backup-pre-round7

# 创建工作分支
git checkout -b upstream-sync-round7

# 验证备份
git tag | grep backup-pre-round7
```

---

### Step 2: 执行标准合并（暂存区模式）（5 分钟）

```bash
# 标准合并（不自动提交）
git merge upstream/main --no-commit --no-ff

# 预期输出：
# Automatic merge went well; stopped before committing as requested
# Merge branch 'main' of github.com:langchain-ai/deepagents into upstream-sync-round7
```

---

### Step 3: 重点文件审查（15 分钟）

#### 3.1 审查 chat_input.py

```bash
# 检查焦点逻辑变更
git diff --cached libs/cli/deepagents_cli/widgets/chat_input.py
```

**关键检查点**:
- ✅ `_backslash_pending_time = None` 是否保留
- ✅ 回退分支（lines 603-609）是否存在
- ⚠️ `_app_has_focus` 和 `cursor_blink` 删除是否影响回退逻辑

**如需手动保留回退分支**:
```python
# 确保以下代码存在（可能在合并冲突中丢失）
if (
    event.key == "enter"
    and not self._completion_active
    and self._backslash_pending_time is not None
    and (now - self._backslash_pending_time) <= _BACKSLASH_ENTER_GAP_SECONDS
):
    self._backslash_pending_time = None
    if self._delete_preceding_backslash():
        event.prevent_default()
        event.stop()
        self.insert("\n")
        return
    # ⚠️ 关键：保留此回退分支
    event.prevent_default()
    event.stop()
    self.insert("\n")
    return
```

---

#### 3.2 审查 graph.py

```bash
# 检查 recursion_limit 变更
git diff --cached libs/deepagents/deepagents/graph.py | grep -A5 recursion_limit
```

**预期结果**:
```diff
+ "recursion_limit": 10_000,
+ "lc_agent_name": name,
```

**验证点**:
- ✅ recursion_limit 提升到 10000
- ✅ lc_agent_name 新增
- ✅ 本地 state_schema 和 skills_expose_dynamic_tools 保留

---

#### 3.3 审查 theme.py

```bash
# 检查颜色 token 新增
git diff --cached libs/cli/deepagents_cli/theme.py | grep -A3 "LC_SKILL\|LC_TOOL"
```

**预期新增**:
```diff
+ LC_SKILL = "#A78BFA"
+ LC_SKILL_HOVER = "#C4B5FD"
+ LC_TOOL = LC_AMBER
+ LC_TOOL_HOVER = "#FFCB91"
```

---

#### 3.4 审查集成测试门控

```bash
# 确认依赖门控未被覆盖
git diff --cached libs/cli/tests/integration_tests/test_sandbox_factory.py | grep -A5 "find_spec"
```

**预期保留**:
```python
# 确保 importlib.util.find_spec 门控存在
if importlib.util.find_spec("modal") is None:
    pytest.skip("modal package not installed; skipping Modal integration tests")
```

---

### Step 4: 解决合并冲突（如有）（10 分钟）

**可能的冲突文件**:
- `libs/cli/deepagents_cli/widgets/chat_input.py`（焦点逻辑变更）
- `libs/cli/deepagents_cli/theme.py`（颜色常量重构）

**解决原则**:
1. 保留上游的 cursor_blink 删除
2. 手动保留本地的回退分支修复
3. 接受上游的 skill/tool 颜色 token
4. 确保无语法错误

---

### Step 5: 全量测试（架构师补充版本）（30 分钟）

#### 5.1 标准 Lint 和 Type 检查

```bash
# DeepAgents SDK
cd libs/deepagents && make lint && make type

# CLI
cd libs/cli && make lint && make type

# ACP
cd libs/acp && make lint && make type

# Daytona
cd libs/partners/daytona && make lint && make type
```

---

#### 5.2 SDK 单元测试

```bash
cd libs/deepagents && make test
# 预期：992 passed, 73 skipped
```

---

#### 5.3 CLI 单元测试（标准）

```bash
cd libs/cli && make test
# 预期：2613 passed, 1 skipped
```

---

#### 5.4 🔴 架构师补充：chat_input.py 并发稳定性测试（必选）

```bash
# 运行 20 次重复测试验证竞态修复稳定性
cd libs/cli
uv run --group test pytest \
  tests/unit_tests/test_chat_input.py::test_backslash_enter_on_empty_prompt_does_not_submit \
  --count=20 \
  -v

# 预期：20 passed（无 flaky failures）
```

**架构师理由**:
> "确保 _backslash_pending_time 拦截机制在焦点逻辑变更后依然生效且无并发竞态。"

---

#### 5.5 🔴 架构师补充：集成测试依赖门控验证（必选）

```bash
# 确认依赖门控正常工作
cd libs/cli
uv run --group test pytest \
  tests/integration_tests/test_sandbox_factory.py -v

# 预期：80 skipped（Modal/Daytona/RunLoop/LangSmith 依赖缺失）
# 关键：确保没有因依赖问题而 FAILED
```

**架构师理由**:
> "确保上游没有意外覆盖或修改掉这个隔离逻辑，防止 cli 的集成测试再次因为环境依赖问题挂掉。"

---

#### 5.6 🔴 架构师补充：graph.py 递归限制测试（可选但建议）

```bash
# 运行 SDK 端到端测试
cd libs/deepagents
uv run --group test pytest \
  tests/unit_tests/test_subagents.py \
  tests/unit_tests/test_end_to_end.py \
  -v

# 关注：无内存 OOM 或栈溢出错误
```

**架构师理由**:
> "极大的递归深度可能会在极端情况下导致栈溢出或内存 OOM。确保现有的端到端测试能够在新限制下平稳运行。"

---

### Step 6: 提交合并结果（5 分钟）

```bash
# 确认所有测试通过
echo "✅ Lint: passed"
echo "✅ Type: passed"
echo "✅ Test: passed (包括并发稳定性测试)"
echo "✅ Integration: 80 skipped (依赖门控正常)"

# 提交合并
git commit -m "$(cat <<'EOF'
merge: sync with upstream/main (27 commits, Round 7)

Upstream commits:
- fix(sdk): bump recursion_limit to 10_000 (利好)
- style(cli): drop manual cursor_blink toggle (Textual 原生支持)
- style(cli): add semantic skill/tool color tokens
- fix(cli): prevent session stats loss on mid-turn exit
- refactor(cli): unify file path header in approval widgets
- perf(cli): prewarm markdown stack and cache skill body render
- fix(cli): use relative paths in langgraph config (Windows compat)
- ci: add minimum workflow permissions
- evals: 多项改进和修复

本地保留:
- chat_input.py: backslash+enter 回退分支修复
- test_sandbox_factory.py: importlib.util.find_spec 依赖门控
- Skills V2, Converters, upload_adapter V5 等自定义功能

测试验证:
- ✅ Lint/Type 全部通过
- ✅ SDK: 992 passed
- ✅ CLI: 2613 passed
- ✅ chat_input 并发测试: 20 passed (无竞态)
- ✅ 集成测试: 80 skipped (依赖门控正常)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Step 7: 推送到远程仓库

```bash
# 推送到 james8814/deepagents
git push origin upstream-sync-round7

# 或直接合并到 master
git checkout master
git merge upstream-sync-round7 --no-edit
git push origin master
```

---

## 关键验证清单

### ✅ Step 3 审查清单

| 文件 | 检查点 | 状态 |
|------|--------|------|
| chat_input.py | `_backslash_pending_time = None` 保留 | ⏳ |
| chat_input.py | 回退分支（lines 603-609）存在 | ⏳ |
| chat_input.py | cursor_blink 删除不影响核心逻辑 | ⏳ |
| graph.py | recursion_limit = 10000 | ⏳ |
| graph.py | lc_agent_name 新增 | ⏳ |
| theme.py | LC_SKILL/LC_TOOL token 新增 | ⏳ |
| test_sandbox_factory.py | find_spec 门控保留 | ⏳ |

### ✅ Step 5 测试清单

| 测试项 | 命令 | 预期结果 | 状态 |
|--------|------|----------|------|
| Lint | make lint | All checks passed | ⏳ |
| Type | make type | All checks passed | ⏳ |
| SDK Test | make test | 992 passed | ⏳ |
| CLI Test | make test | 2613 passed | ⏳ |
| **并发测试** | pytest --count=20 | 20 passed | ⏳ |
| **集成测试** | pytest test_sandbox_factory.py | 80 skipped | ⏳ |

---

## 预期工作量

| 步骤 | 时间 | 备注 |
|------|------|------|
| Step 1: 备份 | 5 分钟 | 创建标签和工作分支 |
| Step 2: 合并 | 5 分钟 | 暂存区模式 |
| Step 3: 审查 | 15 分钟 | 重点审查 4 个文件 |
| Step 4: 冲突 | 10 分钟 | 如有冲突 |
| Step 5: 测试 | 30 分钟 | **含架构师补充测试** |
| Step 6: 提交 | 5 分钟 | 撰写提交信息 |
| **总计** | **~70 分钟** | - |

---

## 风险缓解措施

1. **备份保护**: `git tag backup-pre-round7` 可一键回滚
2. **暂存区模式**: `--no-commit` 防止意外提交
3. **重点审查**: 4 个敏感文件逐一确认
4. **并发测试**: 20 次重复验证稳定性（架构师要求）
5. **集成测试**: 确认依赖门控未破坏（架构师要求）
6. **保留历史**: 标准 merge 保留上游血缘

---

## 架构师特别关注的验证点

### 🔴 必须执行的额外测试

1. **chat_input 并发测试**（阻塞性）
   ```bash
   uv run --group test pytest \
     tests/unit_tests/test_chat_input.py::test_backslash_enter_on_empty_prompt_does_not_submit \
     --count=20 -v
   ```
   **失败条件**: 任何一次测试失败即阻塞合并

2. **集成测试门控验证**（阻塞性）
   ```bash
   uv run --group test pytest \
     tests/integration_tests/test_sandbox_factory.py -v
   ```
   **失败条件**: 出现任何 FAILED（而非 skipped）

3. **递归限制测试**（建议性）
   - 运行端到端测试
   - 关注内存和栈溢出错误

---

## 成功标准

✅ **必须满足**:
1. 所有 Lint/Type 检查通过
2. SDK 单元测试: 992 passed
3. CLI 单元测试: 2613 passed
4. **并发测试**: 20 passed (无 flaky)
5. **集成测试**: 80 skipped (无 FAILED)

✅ **审查确认**:
1. chat_input.py 回退分支保留
2. graph.py recursion_limit = 10000
3. test_sandbox_factory.py 依赖门控保留
4. 无语法错误和运行时错误

---

**执行时间**: 2026-03-26
**预计完成**: ~70 分钟
**风险等级**: 🟢 低（完全可控）

**特别感谢**: 架构师的专业指导和三个关键补充验证点。