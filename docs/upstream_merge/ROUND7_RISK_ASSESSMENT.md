# Round 7 上游合并风险评估报告

**日期**: 2026-03-26
**上游范围**: `d15a3992..d10dfbd7` (27 commits)
**评估团队**: 架构师 + LangChain/LangGraph/DeepAgent 专家组

---

## 执行摘要

| 风险等级 | 提交数 | 占比 | 建议 |
|----------|--------|------|------|
| 🔴 **高** | 3 | 11% | 需深度处理，可能需手动合并 |
| 🟡 **中** | 6 | 22% | 需审查冲突，可能需调整 |
| 🟢 **低** | 18 | 67% | 可直接 cherry-pick，无冲突 |
| **总计** | **27** | **100%** | - |

**关键风险**：
1. **chat_input.py 竞态条件回退**：上游删除了刚修复的 backslash+enter 回退分支
2. **graph.py recursion_limit 变更**：上游改回 1000，本地保留 10000
3. **theme.py 大量重构**：新增 skill/tool 颜色 token，无冲突但需测试

---

## 提交风险详细分析

### 🔴 高风险 (3 commits)

#### 1. f266db54 - style(cli): drop manual cursor blink toggle from chat input (#2243)

**变更文件**: `libs/cli/deepagents_cli/widgets/chat_input.py`

**变更内容**:
- 删除 `_app_has_focus` 属性
- 删除手动 `cursor_blink` 控制
- **删除刚修复的 backslash+enter 回退分支** (lines 603-609)

**冲突分析**:
```diff
- 上游删除了我们刚修复的回退逻辑
- 如果直接合并，竞态条件 bug 会重新出现
```

**风险评估**: 🔴 **严重**
- 本地刚修复的 `chat_input.py:592-608` 竞态条件会被上游覆盖
- 上游认为 Textual 已原生处理 cursor blink，删除了手动控制
- 但我们的修复是关于 backslash 查找失败时的回退逻辑，不是 cursor blink

**合并策略**:
```python
# 保留上游删除 cursor_blink 的改动
# 但手动保留我们的回退分支修复
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
    # ⚠️ 关键修复：保留此回退分支
    event.prevent_default()
    event.stop()
    self.insert("\n")
    return
```

**建议**: 手动合并，保留回退分支

---

#### 2. 7dbc2518 - fix(sdk): bump recursion limit to 10_000 in deepagents and set agent name (#2194)

**变更文件**: `libs/deepagents/deepagents/graph.py`

**变更内容**:
- 设置 recursion_limit 为 10_000
- 添加 `lc_agent_name` metadata

**冲突分析**:
```diff
上游 (7dbc2518):
+ "recursion_limit": 10_000,
+ "lc_agent_name": name,

后续上游变更:
- "recursion_limit": 10_000,
+ "recursion_limit": 1000,
- "lc_agent_name": name,

本地 (master):
+ "recursion_limit": 1000,  # 原始值
+ 本地已有 state_schema 和 skills_expose_dynamic_tools 参数
```

**风险评估**: 🔴 **严重**
- 上游最后将 recursion_limit 改回 1000
- 但用户可能依赖 10000 的高递归限制
- `lc_agent_name` metadata 被删除，需评估影响

**合并策略**:
```python
# 方案 A: 保留本地 1000（与上游一致）
"recursion_limit": 1000,

# 方案 B: 恢复 10000（支持更深递归）
"recursion_limit": 10000,

# lc_agent_name: 评估是否需要保留
```

**建议**: 保留 10000，提供文档说明；评估 lc_agent_name 用途

---

#### 3. e288d8fa - style(cli): add semantic skill and tool color tokens (#2242)

**变更文件**:
- `libs/cli/deepagents_cli/theme.py` (+87 lines)
- `libs/cli/deepagents_cli/widgets/messages.py` (217 lines refactor)

**变更内容**:
- 新增 `LC_SKILL`, `LC_SKILL_HOVER`, `LC_TOOL`, `LC_TOOL_HOVER` 颜色常量
- 重构 messages.py 使用新的语义化颜色 token
- 删除 `LC_ORANGE` (被 `LC_TOOL` 替代)

**冲突分析**:
```diff
本地主题变量注入:
+ $mode-bash, $mode-command 已注册

上游新增:
+ $skill, $skill-hover, $tool, $tool-hover

无直接代码冲突，但需要:
1. 更新 theme.py 添加新常量
2. 更新 messages.py 的渲染逻辑
3. 注册新的 CSS 变量
```

**风险评估**: 🟡 **中等**（降级）
- 大量代码变更，但无语义冲突
- 本地 theme.py 无自定义修改
- messages.py 上游重构可能引入新渲染逻辑

**合并策略**: 直接合并，测试主题渲染

---

### 🟡 中风险 (6 commits)

#### 4. b1807aab - fix(cli): prevent session stats loss on mid-turn exit (#2238)

**变更文件**: `libs/cli/deepagents_cli/app.py`, `textual_adapter.py`

**变更内容**: 防止 mid-turn 退出时会话统计丢失

**风险评估**: 🟡 **中等**
- app.py 本地有 session 管理逻辑
- 需审查是否与本地实现冲突

---

#### 5. e0b6e506 - refactor(cli): unify file path header in approval widgets (#2237)

**变更文件**: `agent.py`, `tool_widgets.py`

**变更内容**: 统一 approval widgets 的文件路径头部

**风险评估**: 🟡 **中等**
- tool_widgets.py 本地可能有自定义渲染
- 需审查 widget 渲染逻辑

---

#### 6. 0a3ba476 - perf(cli): prewarm markdown stack and cache skill body render (#2236)

**变更文件**: `app.py`, `messages.py`

**变更内容**: 性能优化 - 预热 markdown 栈并缓存 skill body 渲染

**风险评估**: 🟡 **中等**
- 性能优化，需验证是否与本地 messages.py 兼容
- 可能影响 skill 渲染性能

---

#### 7. d10dfbd7 - fix(cli): use relative paths in langgraph config for Windows compat (#2244)

**变更文件**: `server_manager.py`

**变更内容**: Windows 兼容性修复

**风险评估**: 🟢 **低**（本地无此文件自定义）

---

#### 8. 77a0b0b5 - ci: add minimum workflow permissions and SHA-pin third-party actions (#2223)

**变更文件**: `.github/workflows/*.yml`

**变更内容**: CI 安全加固

**风险评估**: 🟢 **低**（CI 配置，无代码冲突）

---

#### 9. 74f4b579 - feat(evals): add model groups reference doc and drift test (#2234)

**变更文件**: `libs/evals/*`

**变更内容**: 新增 model groups 文档和 drift 测试

**风险评估**: 🟢 **低**（evals 模块，无 SDK/CLI 核心代码）

---

### 🟢 低风险 (18 commits)

| # | Commit | 描述 | 文件 | 风险 |
|---|--------|------|------|------|
| 10 | 1d69c27c | chore(evals): remove duplicate models from set1 | models.py | 🟢 |
| 11 | 9325eb0a | chore(infra): harden security comments | workflows | 🟢 |
| 12 | e5e5cf9b | fix(evals): prevent langsmith auto-capture | evals tests | 🟢 |
| 13 | adb2b43a | fix(evals): exclude unit_test from radar | evals scripts | 🟢 |
| 14 | f459a238 | chore(evals): switch nemotron 3 to ollama | models.py | 🟢 |
| 15 | bde1faf7 | chore: update dependabot.yml | dependabot.yml | 🟢 |
| 16 | 455bda49 | chore(deps): bump uv group | uv.lock | 🟢 |
| 17 | 99451754 | chore(deps): bump requests | uv.lock | 🟢 |
| 18 | 1bfef380 | feat(evals): add frontier/fast model groups | models.py | 🟢 |
| 19 | 59d7d4f3 | chore(deps): bump requests | uv.lock | 🟢 |
| 20 | 4f0af9dd | chore(evals): switch minimax to ollama | models.py | 🟢 |
| 21 | c87bdd57 | docs(evals): fix stale category references | README.md | 🟢 |
| 22 | fefbfba7 | chore(evals): switch nemotron to baseten | models.py | 🟢 |
| 23 | 6720e4c5 | fix(sdk): route subagent model resolution | graph.py | 🟡 |
| 24 | 2798e51f | feat(sdk,cli): add openrouter SDK attribution | 多文件 | 🟡 |
| 25 | 06ce26b5 | style(evals): deduplicate eval_categories row | evals | 🟢 |
| 26 | 9614225a | fix(infra): pre-commit hook target new Makefile path | Makefile | 🟢 |
| 27 | 80e8f4bc | fix(evals): log field-level diffs on tau2-airline | evals | 🟢 |

---

## 自定义功能影响评估

| 自定义功能 | 上游变更影响 | 风险等级 |
|------------|--------------|----------|
| Skills V2 | ✅ 无影响 | 🟢 |
| Converters | ✅ 无影响 | 🟢 |
| upload_adapter V5 | ✅ 无影响 | 🟢 |
| state_schema 参数 | ✅ 上游已支持 | 🟢 |
| skills_expose_dynamic_tools | ✅ 上游已支持 | 🟢 |
| Memory isawaitable | ✅ 无影响 | 🟢 |
| SubAgent logging | ✅ 无影响 | 🟢 |
| **chat_input 回退修复** | ❌ **被覆盖** | 🔴 |
| **recursion_limit** | ⚠️ 回退到 1000 | 🔴 |

---

## 合并策略建议

### 方案 A: 分批合并 + 手动修复（推荐）

```bash
# Phase 1: 合并低风险提交（18 commits）
git cherry-pick 1d69c27c..9614225a --exclude f266db54,7dbc2518,e288d8fa

# Phase 2: 手动处理高风险提交
# f266db54: 手动合并 chat_input.py，保留回退分支
# 7dbc2518: 手动调整 recursion_limit
# e288d8fa: 直接合并，测试主题功能

# Phase 3: 测试验证
make test && make lint && make type
```

### 方案 B: 全量合并 + 回滚修复

```bash
# 直接合并所有提交
git merge upstream/main

# 手动回滚关键文件的破坏性变更
git checkout HEAD -- libs/cli/deepagents_cli/widgets/chat_input.py
# 手动恢复回退分支修复

# 调整 recursion_limit
# vim libs/deepagents/deepagents/graph.py
```

### 方案 C: 等待上游修复（延期）

- 观察 1-2 天，看上游是否会修复 chat_input 竞态
- 等待上游稳定后再合并

---

## 测试验证计划

### L1 测试（每个提交）

```bash
# 语法检查
python -m py_compile libs/cli/deepagents_cli/widgets/chat_input.py
python -m py_compile libs/deepagents/deepagents/graph.py

# 导入检查
python -c "from deepagents_cli.widgets.chat_input import ChatTextArea"
```

### L2 测试（合并后）

```bash
# 单元测试
make test

# Lint 检查
make lint

# 类型检查
make type
```

### L3 测试（集成测试）

```bash
# 主题渲染测试
uv run pytest tests/unit_tests/test_theme.py -v

# chat_input 测试
uv run pytest tests/unit_tests/test_chat_input.py -v

# SDK 测试
uv run pytest libs/deepagents/tests/unit_tests/test_graph.py -v
```

---

## 风险缓解措施

1. **备份当前 master**
   ```bash
   git tag backup-pre-round7
   ```

2. **创建测试分支**
   ```bash
   git checkout -b round7-test
   ```

3. **逐个提交测试**
   - 每合并一个高风险提交后运行 L1 测试
   - 发现问题立即回滚

4. **保留关键修复**
   - chat_input.py 的回退分支必须保留
   - recursion_limit 需评估后决定

---

## 结论与建议

### 立即行动

1. ✅ 备份当前 master (`git tag backup-pre-round7`)
2. ⏳ 创建测试分支 (`git checkout -b round7-test`)
3. ⏳ 分批合并低风险提交（18 commits）
4. ⏳ 手动处理高风险提交（3 commits）

### 关键决策

| 决策点 | 选项 | 建议 |
|--------|------|------|
| chat_input 回退分支 | 保留 vs 删除 | **保留**（防止竞态） |
| recursion_limit | 1000 vs 10000 | **10000**（支持深递归） |
| lc_agent_name metadata | 保留 vs 删除 | **评估后决定** |
| 合并时机 | 立即 vs 延期 | **立即**（风险可控） |

### 最终建议

**建议采用方案 A（分批合并 + 手动修复）**：
- 18 个低风险提交可直接合并
- 3 个高风险提交需手动处理
- 预计工作量：2-3 小时
- 风险等级：中等（可控）

---

*报告生成时间: 2026-03-26*
*评估团队: 架构师 + LangChain/LangGraph/DeepAgent 专家组*