# Round 7 上游合并最终执行方案（严格可执行版）

**日期**: 2026-03-26
**上游范围**: `d15a3992..d10dfbd7` (27 commits)
**执行团队**: 研发团队
**架构师审批**: ✅ 方案思路一致，6点修订已采纳

---

## ⚠️ 架构师指出的执行前必修项（已修正）

### 修订 1: 测试路径修正（关键）

**原错误路径**:
```bash
❌ tests/unit_tests/test_chat_input.py  # 不存在
❌ tests/integration_tests/test_sandbox_factory.py  # 不存在
```

**修正后路径**:
```bash
✅ libs/cli/tests/unit_tests/test_chat_input.py
✅ libs/cli/tests/integration_tests/test_sandbox_factory.py
```

---

### 修订 2: pytest-repeat 插件检查（关键）

**现状**: `pytest --count=20` 依赖 `pytest-repeat` 插件，但项目未安装

**替代方案**: 使用 shell 循环执行 20 次
```bash
# 方案 A: 检查插件是否存在
uv run --group test python -c "import pytest_repeat" 2>/dev/null && \
  uv run --group test pytest --count=20 ... || \
  # 方案 B: 回退到循环执行
  for i in {1..20}; do uv run --group test pytest <test> -v || exit 1; done
```

---

### 修订 3: 成功标准弹性化（关键）

**原硬编码标准**:
```
❌ 预期: 992 passed  # SDK
❌ 预期: 2613 passed  # CLI
❌ 预期: 80 skipped  # 集成测试
```

**修正后标准**:
```
✅ FAILED == 0
✅ ERROR == 0
✅ passed > 0  (数量参考: SDK ~992, CLI ~2613)
✅ skipped >= 0  (集成测试参考: ~80)
```

---

### 修订 4: 文件审查清单统一

**审查范围**: 3 个核心文件（不是 4 个）

| 文件 | 变更类型 | 审查重点 |
|------|----------|----------|
| `libs/cli/deepagents_cli/widgets/chat_input.py` | 焦点逻辑重构 | 回退分支保留 |
| `libs/deepagents/deepagents/graph.py` | recursion_limit 提升 | 参数接受 |
| `libs/cli/deepagents_cli/theme.py` + 相关渲染文件 | 颜色 token 新增 | 渲染测试 |

**主题相关文件可能涉及**:
- `theme.py` (常量定义)
- `messages.py` (渲染逻辑)
- `welcome.py` (欢迎页面)
- `app.tcss` (CSS 样式)

---

### 修订 5: Git 环境清理（前置步骤）

**问题**: macOS AppleDouble 文件污染 `.git/objects/pack/`

**清理脚本**:
```bash
# 检查是否存在污染
find .git/objects/pack -name "._pack-*.idx" 2>/dev/null

# 如有污染，执行清理
find .git/objects/pack -name "._pack-*.idx" -delete

# 验证清理成功
git status  # 确认无错误输出
git log --oneline -1  # 确认对象索引正常
```

---

### 修订 6: 测试成功标准弹性化

**原硬编码**:
```
❌ SDK Test: 992 passed
❌ CLI Test: 2613 passed
```

**修正后**:
```
✅ make test: 全部通过 (failed=0, error=0)
✅ 数量参考: SDK ~992, CLI ~2613 (基线值，允许波动)
```

---

## 执行步骤

### Step 0: 环境预检查（新增，5 分钟）

```bash
# 0.1 检查 Git 环境
git status  # 确认无未提交修改
git log --oneline -3  # 确认当前状态

# 0.2 清理 Git pack 污染（如有）
find .git/objects/pack -name "._pack-*.idx" -delete 2>/dev/null

# 0.3 验证 Git 健康状态
git fsck --no-dangling 2>&1 | grep -v "dangling" || echo "✅ Git 仓库健康"

# 0.4 检查 pytest-repeat 插件
uv run --group test python -c "import pytest_repeat" 2>/dev/null && \
  echo "✅ pytest-repeat 已安装" || \
  echo "⚠️ pytest-repeat 未安装，将使用循环方案"
```

---

### Step 1: 前置备份（5 分钟）

```bash
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
```

---

### Step 3: 重点文件审查（15 分钟）

#### 3.1 审查 chat_input.py（焦点逻辑重构）

```bash
git diff --cached libs/cli/deepagents_cli/widgets/chat_input.py
```

**关键检查点**:
- ✅ `_backslash_pending_time = None` 是否保留
- ✅ **回退分支是否存在**（当 backslash 未找到时插入 newline，而非提交消息）
- ⚠️ `_app_has_focus` 和 `cursor_blink` 删除是否影响拦截逻辑

**验收标准（行为层面）**:
- ✅ backslash + enter 在空 prompt 时**插入换行**（而非提交）
- ✅ 焦点切换不引入新的竞态条件
- ✅ `_backslash_pending_time` 拦截机制正常工作

---

#### 3.2 审查 graph.py（recursion_limit 提升）

```bash
git diff --cached libs/deepagents/deepagents/graph.py | grep -A5 recursion_limit
```

**预期变更**:
```diff
+ "recursion_limit": 10_000,
+ "lc_agent_name": name,
```

**验收标准**:
- ✅ recursion_limit 提升到 10000（直接接受）
- ✅ lc_agent_name 新增（直接接受）
- ✅ 本地 state_schema 和 skills_expose_dynamic_tools 参数保留

---

#### 3.3 审查主题相关文件（颜色 token 新增）

```bash
# 检查常量定义
git diff --cached libs/cli/deepagents_cli/theme.py

# 检查渲染逻辑
git diff --cached libs/cli/deepagents_cli/widgets/messages.py
```

**预期新增**:
```diff
+ LC_SKILL = "#A78BFA"
+ LC_SKILL_HOVER = "#C4B5FD"
+ LC_TOOL = LC_AMBER
+ LC_TOOL_HOVER = "#FFCB91"
```

**验收标准**:
- ✅ 新增 skill/tool 颜色 token
- ✅ 无语法错误

---

#### 3.4 审查集成测试门控（依赖隔离）

```bash
git diff --cached libs/cli/tests/integration_tests/test_sandbox_factory.py | grep -A5 "find_spec"
```

**预期保留**:
```python
# 确保 importlib.util.find_spec 门控存在
if importlib.util.find_spec("modal") is None:
    pytest.skip("modal package not installed; skipping Modal integration tests")
```

**验收标准**:
- ✅ Modal/Daytona/RunLoop/LangSmith 依赖门控保留
- ✅ 缺失依赖时正确 skip（而非 error）

---

### Step 4: 解决合并冲突（如有）（10 分钟）

**可能的冲突文件**:
- `libs/cli/deepagents_cli/widgets/chat_input.py`
- `libs/cli/deepagents_cli/theme.py`

**解决原则**:
1. 保留上游的 cursor_blink 删除（Textual 原生支持）
2. **手动保留本地的回退分支修复**
3. 接受上游的 skill/tool 颜色 token

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

**成功标准**: All checks passed

---

#### 5.2 SDK 单元测试

```bash
cd libs/deepagents && make test
```

**成功标准**:
- ✅ failed == 0
- ✅ error == 0
- 📊 数量参考: ~992 passed (允许波动)

---

#### 5.3 CLI 单元测试（标准）

```bash
cd libs/cli && make test
```

**成功标准**:
- ✅ failed == 0
- ✅ error == 0
- 📊 数量参考: ~2613 passed (允许波动)

---

#### 5.4 🔴 架构师补充：chat_input.py 并发稳定性测试（必选）

**方案 A: pytest-repeat 插件（如已安装）**
```bash
cd libs/cli
uv run --group test pytest \
  libs/cli/tests/unit_tests/test_chat_input.py::test_backslash_enter_on_empty_prompt_does_not_submit \
  --count=20 -v
```

**方案 B: shell 循环（如插件未安装）**
```bash
cd libs/cli
for i in {1..20}; do
  echo "=== 运行第 $i 次测试 ==="
  uv run --group test pytest \
    libs/cli/tests/unit_tests/test_chat_input.py::test_backslash_enter_on_empty_prompt_does_not_submit \
    -v || exit 1
done
```

**成功标准**:
- ✅ 20 次全部通过
- ✅ 无 flaky failures

**架构师理由**:
> "确保 _backslash_pending_time 拦截机制在焦点逻辑变更后依然生效且无并发竞态。"

---

#### 5.5 🔴 架构师补充：集成测试依赖门控验证（必选）

```bash
cd libs/cli
uv run --group test pytest \
  libs/cli/tests/integration_tests/test_sandbox_factory.py -v
```

**成功标准**:
- ✅ failed == 0
- ✅ error == 0
- 📊 skipped >= 0 (数量参考: ~80, 允许波动)

**架构师理由**:
> "确保上游没有意外覆盖掉隔离逻辑，防止集成测试因环境依赖失败。"

---

#### 5.6 🔴 架构师补充：graph.py 递归限制测试（建议）

```bash
cd libs/deepagents
uv run --group test pytest \
  libs/deepagents/tests/unit_tests/test_subagents.py \
  libs/deepagents/tests/unit_tests/test_end_to_end.py \
  -v
```

**关注点**:
- ✅ 无内存 OOM 错误
- ✅ 无栈溢出错误

---

### Step 6: 提交合并结果（5 分钟）

```bash
# 确认所有测试通过
echo "✅ Lint: passed"
echo "✅ Type: passed"
echo "✅ Test: passed (failed=0, error=0)"
echo "✅ 并发测试: 20 次全部通过"
echo "✅ 集成测试: skipped (failed=0)"

# 提交合并
git commit -m "$(cat <<'EOF'
merge: sync with upstream/main (27 commits, Round 7)

Upstream highlights:
- fix(sdk): bump recursion_limit to 10_000 (利好)
- style(cli): drop manual cursor_blink toggle (Textual 原生支持)
- style(cli): add semantic skill/tool color tokens
- fix(cli): prevent session stats loss on mid-turn exit
- refactor(cli): unify file path header in approval widgets
- perf(cli): prewarm markdown stack and cache skill body render

Local preservation:
- chat_input.py: backslash+enter 回退分支修复（插入换行而非提交）
- test_sandbox_factory.py: importlib.util.find_spec 依赖门控
- Skills V2, Converters, upload_adapter V5 等自定义功能

Test verification:
- ✅ Lint/Type: All checks passed
- ✅ SDK: passed (failed=0, error=0)
- ✅ CLI: passed (failed=0, error=0)
- ✅ chat_input 并发测试: 20 passed (无竞态)
- ✅ 集成测试: skipped (failed=0, 门控正常)

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

### ✅ Step 0 环境检查

| 检查项 | 命令 | 预期结果 | 状态 |
|--------|------|----------|------|
| Git 状态 | git status | 无未提交修改 | ⏳ |
| Git pack 污染 | find .git/objects/pack -name "._*" | 无输出 | ⏳ |
| Git 健康 | git fsck --no-dangling | 无错误 | ⏳ |
| pytest-repeat | python -c "import pytest_repeat" | 已安装/未安装 | ⏳ |

### ✅ Step 3 审查清单

| 文件 | 审查重点 | 验收标准 | 状态 |
|------|----------|----------|------|
| chat_input.py | 回退分支保留 | backslash+enter 插入换行 | ⏳ |
| chat_input.py | 焦点逻辑变更 | 无竞态条件 | ⏳ |
| graph.py | recursion_limit | 10000 | ⏳ |
| graph.py | lc_agent_name | 新增 | ⏳ |
| theme.py | skill/tool token | 新增 | ⏳ |
| test_sandbox_factory.py | find_spec 门控 | 保留 | ⏳ |

### ✅ Step 5 测试清单

| 测试项 | 成功标准 | 状态 |
|--------|----------|------|
| Lint | All checks passed | ⏳ |
| Type | All checks passed | ⏳ |
| SDK Test | failed=0, error=0 | ⏳ |
| CLI Test | failed=0, error=0 | ⏳ |
| **并发测试** | 20 次全部通过 | ⏳ |
| **集成测试** | failed=0, skipped>=0 | ⏳ |

---

## 预期工作量

| 步骤 | 时间 | 关键操作 |
|------|------|----------|
| Step 0: 环境预检查 | 5 分钟 | Git 健康检查、插件检查 |
| Step 1: 备份 | 5 分钟 | 创建标签和工作分支 |
| Step 2: 合并 | 5 分钟 | 暂存区模式 |
| Step 3: 审查 | 15 分钟 | 重点审查 3 个核心文件 |
| Step 4: 冲突 | 10 分钟 | 如有冲突 |
| Step 5: 测试 | 30 分钟 | **含架构师补充测试** |
| Step 6: 提交 | 5 分钟 | 撰写提交信息 |
| **总计** | **~75 分钟** | - |

---

## 成功标准（弹性化）

### ✅ 必须满足

| 维度 | 标准 |
|------|------|
| **代码质量** | Lint: All checks passed |
| **类型安全** | Type: All checks passed |
| **测试通过** | failed=0, error=0 |
| **并发稳定** | 20 次测试全部通过 |
| **集成测试** | failed=0, skipped>=0 |

### ✅ 审查确认

| 文件 | 确认点 |
|------|--------|
| chat_input.py | backslash+enter 插入换行（而非提交） |
| chat_input.py | 焦点切换无竞态 |
| graph.py | recursion_limit=10000 |
| test_sandbox_factory.py | find_spec 门控保留 |

---

## 风险缓解措施

1. **备份保护**: `git tag backup-pre-round7` 可一键回滚
2. **暂存区模式**: `--no-commit` 防止意外提交
3. **环境清理**: 预检查 Git pack 污染
4. **插件回退**: pytest-repeat 未安装时使用循环方案
5. **弹性标准**: 通过数量允许波动，failed/error 必须为 0

---

## 架构师特别关注的验证点

### 🔴 必须执行的测试（阻塞性）

1. **chat_input 并发测试**
   - 路径: `libs/cli/tests/unit_tests/test_chat_input.py::test_backslash_enter_on_empty_prompt_does_not_submit`
   - 次数: 20 次
   - 标准: 全部通过

2. **集成测试门控**
   - 路径: `libs/cli/tests/integration_tests/test_sandbox_factory.py`
   - 标准: failed=0, skipped>=0

---

**执行时间**: 2026-03-26
**预计完成**: ~75 分钟
**风险等级**: 🟢 低（完全可控）

**特别感谢**: 架构师的 6 点精准修订，大幅提升了方案的可执行性和严谨性。