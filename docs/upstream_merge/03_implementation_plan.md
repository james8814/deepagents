# 上游合并实施方案 (逐个 Commit 版 - 修订版)

**文档类型**: 实施方案
**创建日期**: 2026-03-01
**修订日期**: 2026-03-01
**修订版本**: v2.0
**修订依据**: 架构师 Review 报告
**目标**: 将 langchain-ai/deepagents v0.4.4 逐个 commit 合并到 james8814/deepagents
**总 Commits**: 197 个

---

## 📋 核心原则

### ⚠️ 强制原则

1. **不主动跳过任何 commit** - 默认全部合并
2. **跳过必须确认** - 如需跳过，必须暂停等待明确许可
3. **质量第一** - 宁可慢，不可错
4. **每个 commit 必须测试** - L1+L2 测试必须通过
5. **每个 commit 必须审查** - 代码 Review 必须完成
6. **版本节点完整测试** - 每个 version milestone 执行 L4 测试

### 测试节奏

```
┌─────────────────────────────────────────────────────────────┐
│                    测试节奏规划                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Commit 级别 (每个 commit)                                  │
│  ├── L1: 持续验证 (导入检查 + 语法检查)                     │
│  └── L2: 单元测试 + 代码 Review                             │
│                                                             │
│  版本级别 (每个 release version)                            │
│  └── L4: 完整 E2E + 集成测试 + 自定义功能回归               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛡️ 自定义功能保护清单

以下功能是我们的核心差异化特性，**必须确保合并后完整保留**：

### P0 - 必须保护

| 功能 | 文件 | 验证方法 |
|------|------|----------|
| SkillsMiddleware V2 | `skills.py` | `load_skill()` / `unload_skill()` 工具存在 |
| Upload Adapter V5 | `upload_adapter.py` | `upload_files()` 函数工作正常 |
| 自定义 history_path_prefix | `graph.py`, `summarization.py` | 参数存在且生效 |

### P1 - 需要关注

| 功能 | 文件 | 验证方法 |
|------|------|----------|
| `_compute_summarization_defaults` | `summarization.py` | 函数存在（可能需要重命名） |
| 自定义存储逻辑 | `summarization.py` | 存储路径正确 |
| V2 测试用例 | `test_skills_middleware.py` | V2 测试通过 |

### 验证脚本

```python
# 验证 V2 特性完整性
def verify_v2_features():
    # 1. SkillsMiddleware V2
    from deepagents.middleware.skills import SkillsMiddleware
    middleware = SkillsMiddleware(backend=mock_backend, sources=["/skills/"])
    assert len(middleware.tools) == 2
    assert middleware.tools[0].name == "load_skill"
    assert middleware.tools[1].name == "unload_skill"
    assert middleware._max_loaded_skills == 10

    # 2. Upload Adapter
    from deepagents import upload_files, UploadResult
    assert callable(upload_files)

    # 3. history_path_prefix
    from deepagents import create_deep_agent
    import inspect
    sig = inspect.signature(create_deep_agent)
    assert "history_path_prefix" in sig.parameters

    print("✅ 所有自定义功能验证通过")
```

---

## 🔒 安全检查清单

每个 commit 合并前需检查：

### 代码安全

- [ ] 无硬编码密钥或凭证
- [ ] 无不安全的依赖引入
- [ ] 无危险的命令注入风险
- [ ] 路径遍历保护未被移除

### 敏感文件

以下文件变更需要特别审查：

| 文件 | 敏感原因 |
|------|----------|
| `skills.py` | V2 特性保护 |
| `summarization.py` | 自定义逻辑 |
| `graph.py` | 核心入口 |
| `filesystem.py` | 文件安全 |
| `*_backend.py` | 数据安全 |
| `pyproject.toml` | 依赖安全 |

### State Schema 变更

- [ ] 检查 `AgentState` 子类定义变更
- [ ] 检查 `TypedDict` 字段变更
- [ ] 确认向后兼容性

---

## 🔄 执行流程

### Phase 0: 准备工作

```bash
# 1. 确保 master 干净
git checkout master
git status  # 应显示 "nothing to commit"

# 2. 创建工作分支
git checkout -b merge-upstream-0.4.4-incremental

# 3. 添加上游仓库
git remote add upstream https://github.com/langchain-ai/deepagents.git
git fetch upstream

# 4. 创建备份分支
git branch backup-pre-merge

# 5. 创建初始检查点
git tag checkpoint-start

# 6. 验证当前状态
cd libs/deepagents && make test  # 确保基线测试通过
```

### 单个 Commit 合并流程

```
┌──────────────────────────────────────────────────────────────┐
│                  Commit 合并流程                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 获取 commit 信息                                         │
│     $ git show --stat <SHA>                                  │
│                                                              │
│  2. 分析变更影响                                             │
│     - 影响哪些文件？                                         │
│     - 是否涉及敏感文件？                                     │
│     - 是否影响自定义功能？                                   │
│                                                              │
│  3. ⚠️ 问题检测点                                            │
│     ┌─────────────────────────────────────┐                  │
│     │ 是否有问题需要跳过？                 │                  │
│     └──────────────────┬──────────────────┘                  │
│                        │                                     │
│            ┌───────────┴───────────┐                         │
│            │                       │                          │
│           否                       是                         │
│            │                       │                          │
│            │                       ▼                          │
│            │              ┌─────────────────┐                │
│            │              │ 🛑 暂停执行      │                │
│            │              │ 记录问题描述    │                │
│            │              │ 提交跳过建议    │                │
│            │              └────────┬────────┘                │
│            │                       │                          │
│            │                       ▼                          │
│            │              ┌─────────────────┐                │
│            │              │ ⏳ 等待确认许可  │                │
│            │              │ (必须得到明确   │                │
│            │              │  的继续指令)    │                │
│            │              └────────┬────────┘                │
│            │                       │                          │
│            │              ┌────────┴────────┐                │
│            │              │                 │                 │
│            │         许可跳过          不允许跳过             │
│            │              │                 │                 │
│            │              │                 ▼                 │
│            │              │        ┌─────────────────┐       │
│            │              │        │ 解决问题后继续  │       │
│            │              │        └────────┬────────┘       │
│            │              │                 │                 │
│            ◀──────────────┴─────────────────┘                 │
│            │                                                  │
│            ▼                                                  │
│  4. 执行 Cherry-pick                                         │
│     $ git cherry-pick <SHA>                                  │
│                                                              │
│  5. 解决冲突（如有）                                         │
│     - 手动解决冲突文件                                       │
│     - $ git add . && git cherry-pick --continue              │
│                                                              │
│  6. L1 测试: 持续验证                                        │
│     $ python -c "from deepagents import create_deep_agent"   │
│     $ python -m py_compile libs/deepagents/deepagents/*.py   │
│                                                              │
│  7. L2 测试: 单元测试                                        │
│     $ cd libs/deepagents && make test                        │
│                                                              │
│  8. ⚠️ 代码 Review (必须执行)                                │
│     - 检查变更内容                                           │
│     - 确认自定义功能未受影响                                 │
│     - 记录 Review 结果                                       │
│                                                              │
│  9. 验收记录                                                 │
│     - 更新本文档的状态追踪表                                 │
│     - 记录任何特殊情况                                       │
│                                                              │
│ 10. 版本节点检查                                             │
│     ┌─────────────────────────────────────┐                  │
│     │ 当前 commit 是否为 release version？│                  │
│     └──────────────────┬──────────────────┘                  │
│                        │                                     │
│            ┌───────────┴───────────┐                         │
│            │                       │                          │
│           否                       是                         │
│            │                       │                          │
│            │                       ▼                          │
│            │              ┌─────────────────┐                │
│            │              │ 🎯 L4 完整测试  │                │
│            │              │ - E2E 测试      │                │
│            │              │ - 集成测试      │                │
│            │              │ - 自定义功能回归│                │
│            │              └────────┬────────┘                │
│            │                       │                          │
│            ◀───────────────────────┘                          │
│            │                                                  │
│            ▼                                                  │
│  11. 创建检查点                                              │
│      $ git tag checkpoint-<n>                                │
│                                                              │
│  12. 继续下一个 commit                                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## ⚠️ 跳过确认流程

### 触发条件

当遇到以下情况时，需要进入跳过确认流程：

1. ❌ 冲突无法解决
2. ❌ 测试持续失败且无法修复
3. ❌ 与自定义功能严重冲突
4. ❌ 依赖问题无法解决

### 跳过流程

```
┌─────────────────────────────────────────────────────────────┐
│                     跳过确认流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 🛑 暂停执行                                             │
│                                                             │
│  2. 📝 记录以下信息：                                       │
│     - Commit SHA:                                           │
│     - Commit 描述:                                          │
│     - 问题描述:                                             │
│     - 尝试过的解决方案:                                     │
│     - 建议跳过原因:                                         │
│     - 跳过影响评估:                                         │
│                                                             │
│  3. ⏳ 等待确认                                             │
│     - 提交给负责人审查                                      │
│     - 必须得到明确的书面许可                                │
│                                                             │
│  4. ✅ 收到许可后                                           │
│     - 记录跳过许可                                          │
│     - 标记 commit 为 ⏭️ 已跳过                              │
│     - 继续下一个 commit                                     │
│                                                             │
│  5. ❌ 未收到许可                                           │
│     - 继续尝试解决问题                                      │
│     - 或寻求其他解决方案                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 跳过记录模板

```markdown
### 跳过记录 #N

- **Commit SHA**: `<sha>`
- **Commit 描述**: `<description>`
- **问题描述**: `<issue>`
- **尝试过的解决方案**: `<attempts>`
- **跳过原因**: `<reason>`
- **影响评估**: `<impact>`
- **许可人**: `<approver>`
- **许可时间**: `<timestamp>`
```

---

## 📊 Commit 合并状态追踪

### 状态定义

| 状态 | 符号 | 说明 |
|------|------|------|
| 待处理 | ⬜ | 尚未开始 |
| 进行中 | 🔵 | 正在合并 |
| 已完成 | ✅ | 合并并通过测试 |
| 已跳过 | ⏭️ | 经确认后跳过 |
| 阻塞中 | 🚫 | 遇到问题等待解决 |
| 已回滚 | ↩️ | 合并后回滚 |

### 版本里程碑

| 版本 | Commit # | SHA | 状态 | L4 测试 | 完成时间 |
|------|----------|-----|------|---------|----------|
| 0.4.0 | #34 | `b8612d9` | ⬜ | ⬜ | |
| 0.4.1 | #59 | `4587a4e` | ⬜ | ⬜ | |
| 0.4.2 | #82 | `b89630a` | ⬜ | ⬜ | |
| 0.4.3 | #165 | `698e0fe` | ⬜ | ⬜ | |
| 0.4.4 | #190 | `37a303d` | ⬜ | ⬜ | |

---

## 📋 Commit 详细清单

### Phase 1: Commits 1-34 (→ 0.4.0)

| # | SHA | 日期 | 类型 | 描述 | 状态 | L1 | L2 | Review | 备注 |
|---|-----|------|------|------|------|----|----|--------|------|
| 1 | `3da1e8b` | 02-07 | fix(cli) | per-subcommand help | ⬜ | ⬜ | ⬜ | ⬜ | |
| 2 | `42823a8` | 02-07 | feat(cli) | built-in skills | ⬜ | ⬜ | ⬜ | ⬜ | |
| 3 | `b5c8a99` | 02-07 | fix(sdk) | skills metadata parsing | ⬜ | ⬜ | ⬜ | ⬜ | ⚠️ 检查 V2 |
| 4 | `ad9241d` | 02-07 | fix(cli) | port skills behavior | ⬜ | ⬜ | ⬜ | ⬜ | |
| 5 | `b8179c2` | 02-07 | feat(cli) | enrich skill metadata | ⬜ | ⬜ | ⬜ | ⬜ | |
| 6-10 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 11-20 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 21-30 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 31-33 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 34 | `79ef7ab` | 02-10 | release | **0.4.0** | ⬜ | ⬜ | ⬜ | ⬜ | 🎯 L4 测试 |

### Phase 2: Commits 35-82 (0.4.0 → 0.4.2)

| # | SHA | 日期 | 类型 | 描述 | 状态 | L1 | L2 | Review | 备注 |
|---|-----|------|------|------|------|----|----|--------|------|
| 35-48 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 49 | `8cb9b52` | 02-11 | refactor(sdk) | SummarizationMiddleware | ⬜ | ⬜ | ⬜ | ⬜ | ⚠️ 高风险 |
| 50-58 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 59 | `4587a4e` | 02-11 | release(sdk) | **0.4.1** | ⬜ | ⬜ | ⬜ | ⬜ | 🎯 L4 测试 |
| 60-81 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 82 | `b89630a` | 02-12 | release(sdk) | **0.4.2** | ⬜ | ⬜ | ⬜ | ⬜ | 🎯 L4 测试 |

### Phase 3: Commits 83-165 (0.4.2 → 0.4.3)

| # | SHA | 日期 | 类型 | 描述 | 状态 | L1 | L2 | Review | 备注 |
|---|-----|------|------|------|------|----|----|--------|------|
| 83-86 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 87 | `74ddcbf` | 02-12 | feat(sdk) | base agent prompt | ⬜ | ⬜ | ⬜ | ⬜ | ⚠️ 会覆盖我们的 |
| 88-92 | ... | ... | ... | Security fixes | ⬜ | ⬜ | ⬜ | ⬜ | ✅ 必须 |
| 93 | `342fcf1` | 02-13 | revert | revert skill loading | ⬜ | ⬜ | ⬜ | ⬜ | ⚠️ 检查 V2 |
| 94-164 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 165 | `698e0fe` | 02-20 | release(sdk) | **0.4.3** | ⬜ | ⬜ | ⬜ | ⬜ | 🎯 L4 测试 |

### Phase 4: Commits 166-197 (0.4.3 → 0.4.4)

| # | SHA | 日期 | 类型 | 描述 | 状态 | L1 | L2 | Review | 备注 |
|---|-----|------|------|------|------|----|----|--------|------|
| 166-189 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 190 | `37a303d` | 02-26 | release(sdk) | **0.4.4** | ⬜ | ⬜ | ⬜ | ⬜ | 🎯 L4 测试 |
| 191-192 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |
| 193 | `e87cdad` | 02-27 | feat | compaction hook | ⬜ | ⬜ | ⬜ | ⬜ | ⚠️ 高风险 |
| 194-197 | ... | ... | ... | ... | ⬜ | ⬜ | ⬜ | ⬜ | |

---

## 🛠️ 回滚策略

### 检查点命名规范

```bash
# 版本检查点
checkpoint-v0.4.0
checkpoint-v0.4.1
...

# 阶段检查点
checkpoint-phase1-done
checkpoint-phase2-done
...

# 特殊检查点
checkpoint-before-risky-<sha>
```

### 回滚命令

```bash
# 回滚到上一个 commit
git reset --hard HEAD~1

# 回滚到指定检查点
git reset --hard checkpoint-v0.4.0

# 回滚到备份点
git reset --hard backup-pre-merge
```

---

## 📅 时间估算

| 阶段 | Commits | 合并时间 | 测试时间 | 总计 |
|------|---------|----------|----------|------|
| Phase 1 | 34 | 2-3h | 1h | 3-4h |
| Phase 2 | 48 | 3-4h | 1.5h | 4.5-5.5h |
| Phase 3 | 83 | 5-6h | 2h | 7-8h |
| Phase 4 | 32 | 2-3h | 1h | 3-4h |

**总计**: 17.5-21.5 小时（建议分 4-5 天执行）

---

## ✅ 验收标准

### Commit 验收

- [ ] L1 测试通过
- [ ] L2 单元测试通过
- [ ] 代码 Review 完成
- [ ] V2 特性验证通过

### 版本验收

- [ ] L4 完整测试通过
- [ ] 自定义功能全部正常
- [ ] 无安全警告

### 最终验收

- [ ] 所有 197 个 commits 处理完毕
- [ ] 版本号更新为 0.4.4+
- [ ] 所有自定义功能保留
- [ ] 完整测试套件通过

---

**相关文档**:
- [01_commit_analysis.md](./01_commit_analysis.md) - 最新 10 个 commit 详细分析
- [02_conflict_analysis.md](./02_conflict_analysis.md) - 冲突影响分析
- [04_test_verification.md](./04_test_verification.md) - 测试验证方案
- [05_architect_review.md](./05_architect_review.md) - 架构师 Review 报告
