# 上游合并进度日志

**开始时间**: 2026-03-01
**目标**: 合并 langchain-ai/deepagents v0.4.4 到 james8814/deepagents
**总 Commits**: 197 个

---

## 合并状态

| 阶段 | 目标版本 | Commits | 状态 | 完成时间 |
|------|----------|---------|------|----------|
| Phase 0 | 环境准备 | - | ✅ 完成 | 2026-03-01 |
| Phase 1 | 0.4.0 | 1-34 | ✅ 完成 | 2026-03-01 |
| Phase 2 | 0.4.1 | 35-74 | ✅ 完成 | 2026-03-01 |
| Phase 3 | 0.4.2 | 75-82 | ✅ 完成 | 2026-03-01 |
| Phase 4 | 0.4.3 | 83-165 | 🔄 进行中 | - |
| Phase 5 | 0.4.4 | 166-197 | ⬜ 待处理 | - |

---

## Phase 0: 环境准备 ✅

**完成项**:
- ✅ 创建工作分支 `merge-upstream-0.4.4-incremental`
- ✅ 添加 upstream remote
- ✅ 创建备份分支和检查点
- ✅ 验证基线测试通过

---

## Phase 1: Commits 1-34 (→ 0.4.0) ✅

**状态**: ✅ 完成 (31 commits 合并)

### 关键合并记录

| # | SHA | 描述 | 状态 | 冲突解决 |
|---|-----|------|------|----------|
| 1 | `3da1e8bc` | fix(cli): per-subcommand help screens | ✅ | 无冲突 |
| 2 | `42823a88` | feat(cli): built-in skills | ✅ | 无冲突 |
| 3 | `b5c8a998` | fix(sdk): harden skills metadata parsing | ✅ | ⚠️ 保留 V2 功能 |
| 4 | `ad9241da` | fix(cli): port skills behavior | ✅ | 无冲突 |
| 5 | `b8179c23` | feat(cli): enrich skill metadata | ✅ | 无冲突 |

### 检查点
- ✅ `checkpoint-v0.4.0` 已创建

---

## Phase 2: Commits 35-74 (0.4.0 → 0.4.1) ✅

**状态**: ✅ 完成 (40 commits 合并)

### 关键合并记录

| # | SHA | 描述 | 状态 | 冲突解决 |
|---|-----|------|------|----------|
| 1 | `28fc311d` | feat(cli): model switcher | ✅ | ⚠️ 使用上游版本 |
| 2 | `06eaa5bd` | hotfix(cli): pin version | ✅ | 无冲突 |
| 3 | `662a81df` | release(cli): 0.0.20 | ✅ | 无冲突 |
| 4 | `8cb9b52a` | refactor(sdk): SummarizationMiddleware | ✅ | 无冲突 |
| 5 | `595f6fe6` | chore(deps): bump dependencies | ✅ | 无冲突 |
| 6 | `65600b1c` | feat(sdk): image content blocks | ✅ | ⚠️ 使用上游版本 |
| 7 | `643ea7c7` | chore: migrate to uv workspace | ✅ | 无冲突 |
| 8 | `4587a4e9` | release(sdk): 0.4.1 | ✅ | ⚠️ 版本号冲突 |

### 检查点
- ✅ `checkpoint-v0.4.1` 已创建

---

## Phase 3: Commits 75-82 (0.4.1 → 0.4.2) ✅

**状态**: ✅ 完成 (8 commits 合并)

### 关键合并记录

| # | SHA | 描述 | 状态 | 冲突解决 |
|---|-----|------|------|----------|
| 1 | `15521003` | chore: rollback uv workspace | ✅ | 无冲突 |
| 2 | `3b103c82` | chore: reparameterize init | ✅ | 无冲突 |
| 3 | `c1d30bdd` | feat(cli): /threads command | ✅ | 无冲突 |
| 4 | `98b7d2b9` | chore(acp): parameterization fixes | ✅ | 无冲突 |
| 5 | `bb7820dd` | feat(cli): langsmith thread url | ✅ | 无冲突 |
| 6 | `3643a9e7` | chore(acp): attach checkpointer | ✅ | 无冲突 |
| 7 | `03313835` | hotfix(cli): sdk version pin | ✅ | 无冲突 |
| 8 | `4830e425` | release(cli): 0.0.21 | ✅ | 无冲突 |

### 检查点
- ✅ `checkpoint-v0.4.2` 已创建

---

## Phase 4: Commits 83-165 (0.4.2 → 0.4.3) 🔄

**状态**: 🔄 进行中

### 已合并记录

| # | SHA | 描述 | 状态 | 冲突解决 |
|---|-----|------|------|----------|
| 1 | `41c73ac7` | hotfix(cli): sdk version pin | ✅ | 无冲突 |

### 待合并 Commits

| # | SHA | 描述 | 风险 | 备注 |
|---|-----|------|------|------|
| 1 | `db05de1b` | feat(infra): ensure dep group version match | 低 | |
| 2 | `c2f0572c` | refactor(infra): move cli check script | 低 | |
| 3 | `906711ea` | chore(cli): update README.md | 低 | |
| 4 | `2aeb092e` | feat(cli): update system & default prompt | 中 | ⚠️ 检查 BASE_AGENT_PROMPT |
| 5 | `74ddcbff` | feat(sdk): add base agent prompt | 高 | ⚠️ 高风险 - 检查自定义 prompt |
| 6 | `194a2db6` | fix(sdk): path traversal in glob | 高 | 安全修复 |
| 7 | `342fcf1b` | revert(sdk): skill loading | 高 | ⚠️ 检查 V2 功能 |

---

## Phase 5: Commits 166-197 (0.4.3 → 0.4.4) ⬜

**状态**: ⬜ 待处理

### 关键 Commits 预览

| # | SHA | 描述 | 风险 | 备注 |
|---|-----|------|------|------|
| 1 | `e87cdadd` | feat(cli,sdk): compaction hook | 高 | ⚠️ 检查 summarization 冲突 |
| 2 | `37a303d1` | release(sdk): 0.4.4 | 中 | 版本号更新 |
| 3 | `92aeeb47` | test: add standard tests | 低 | |
| 4 | `4a4be8e8` | fix: code quality findings | 低 | |

---

## 自定义功能保护清单

| 功能 | 文件 | 状态 | 验证方法 |
|------|------|------|----------|
| SkillsMiddleware V2 | `skills.py` | ✅ 保留 | `load_skill()` / `unload_skill()` 工具存在 |
| Upload Adapter V5 | `upload_adapter.py` | ✅ 保留 | `upload_files()` 函数工作正常 |
| history_path_prefix | `graph.py`, `summarization.py` | ✅ 保留 | 参数存在且生效 |
| Converters | `filesystem.py` | ❌ 丢失 | 需要恢复 converters 导入 |

---

## 测试验证记录

### 0.4.0 L4 测试 ✅
- ✅ SDK 导入正常
- ✅ CLI 导入正常
- ✅ V2 功能验证通过
- ✅ Upload Adapter 验证通过

### 0.4.1 L4 测试 ✅
- ✅ SDK 导入正常
- ✅ V2 功能验证通过
- ✅ Version: 0.4.1

### 0.4.2 L4 测试 🔄
- ✅ SDK 导入正常
- ✅ V2 功能验证通过
- ⚠️ Converters 功能需要恢复

---

## 跳过记录

| Commit SHA | 描述 | 原因 | 影响评估 |
|------------|------|------|----------|
| `a9c807cb` | chore: update AGENTS.md | 空合并 - 我们的版本更详细 | 无影响 |

---

## 技术备注

### 环境问题
1. **macOS 资源分支文件**: 外部驱动器上的 `._*` 文件导致 uv 安装问题
   - 解决方案: 使用 `/tmp` 目录创建 venv

### 关键冲突解决策略
1. **skills.py**: 保留 V2 功能 (`load_skill`, `unload_skill` 工具)
2. **summarization.py**: 整合环境变量 (`DEEPAGENTS_FALLBACK_*`)
3. **pyproject.toml**: 使用上游版本号，保留 converters 依赖
4. **filesystem.py**: ⚠️ converters 导入丢失 - 需要恢复

### 待修复
- [ ] filesystem.py 中的 converters 导入和使用

---

**最后更新**: 2026-03-01
**当前 HEAD**: `41c73ac7 hotfix(cli): sdk version pin (#1298)`
**当前版本**: 0.4.1
**已合并**: 74 commits
**剩余**: 123 commits
