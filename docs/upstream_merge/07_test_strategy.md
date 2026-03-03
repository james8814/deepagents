# 合并测试策略

**项目**: deepagents v0.4.4 上游合并
**日期**: 2026-03-02
**测试架构师**: Claude Opus 4.6

---

## 测试级别定义

### L1: 持续验证 (每个 commit)
**执行时机**: 每个 commit cherry-pick 后
**执行内容**:
- [x] Python 语法检查 (`py_compile`)
- [x] 导入测试 (核心模块可导入)
- [x] V2 功能存在性检查

**命令**:
```bash
# 语法检查
python3 -m py_compile libs/deepagents/deepagents/graph.py
python3 -m py_compile libs/deepagents/deepagents/middleware/skills.py
python3 -m py_compile libs/deepagents/deepagents/middleware/filesystem.py

# 导入测试
cd libs/deepagents && uv run python -c "from deepagents import create_deep_agent"
cd libs/cli && uv run python -c "from deepagents_cli import cli_main"
```

---

### L2: 单元测试 (每个 commit)
**执行时机**: 每个 commit 通过 L1 后
**执行内容**:
- [x] SDK 单元测试 (关键模块)
- [x] CLI 单元测试 (关键模块)
- [x] 代码 Review (自动化)

**命令**:
```bash
# SDK 测试
cd libs/deepagents && uv run --group test pytest tests/unit_tests/middleware/ -v -k "not slow"

# CLI 测试
cd libs/cli && uv run --group test pytest tests/unit_tests/ -v -k "not slow"
```

---

### L3: 阶段测试 (每个 Phase 完成)
**执行时机**: 每个版本阶段完成后
**执行内容**:
- [x] 完整单元测试
- [x] 功能回归测试
- [x] V2 功能验证

**命令**:
```bash
# 完整测试
cd libs/deepagents && make test
cd libs/cli && make test

# V2 功能验证
uv run python -c "
from deepagents.middleware.skills import SkillsMiddleware
assert hasattr(SkillsMiddleware, 'load_skill')
assert hasattr(SkillsMiddleware, 'unload_skill')
print('✅ V2 功能验证通过')
"
```

---

### L4: 版本测试 (每个 release commit)
**执行时机**: 每个 release commit (0.4.2, 0.4.3, 0.4.4)
**执行内容**:
- [x] 版本号验证
- [x] 集成测试
- [x] 完整功能验证
- [x] 安全修复验证

**命令**:
```bash
# 版本号验证
grep "__version__" libs/deepagents/deepagents/_version.py
grep "__version__" libs/cli/deepagents_cli/_version.py

# 集成测试 (如可用)
cd libs/deepagents && make integration_test
```

---

## 测试矩阵

| Commit 类型 | L1 | L2 | L3 | L4 |
|------------|----|----|----|----|
| 普通功能 | ✅ | ✅ | - | - |
| 安全修复 | ✅ | ✅ | ✅ | ✅ |
| 版本 Release | ✅ | ✅ | ✅ | ✅ |
| V2 相关 | ✅ | ✅ | ✅ | ✅ |
| 依赖更新 | ✅ | - | ✅ | - |

---

## 关键验证点

### 自定义功能保护验证

| 功能 | 验证命令 | 预期结果 |
|------|----------|----------|
| load_skill | `grep -n "load_skill" skills.py` | > 0 |
| unload_skill | `grep -n "unload_skill" skills.py` | > 0 |
| ResourceMetadata | `grep -n "ResourceMetadata" skills.py` | > 0 |
| upload_files | `grep -n "upload_files" upload_adapter.py` | > 0 |
| history_path_prefix | `grep -n "history_path_prefix" graph.py` | > 0 |

### 安全修复验证

| CVE | 验证命令 | 状态 |
|-----|----------|------|
| Path Traversal | `grep -n "_validate_path" filesystem.py` | ✅ |
| Command Injection | `grep -n "escape" harbor/` | ✅ |

---

## 回归门控

### 阻塞条件
- L1 测试失败 → 必须修复后继续
- L2 测试 < 90% 通过 → 评估后决定
- V2 功能丢失 → 必须恢复后继续

### 跳过条件
- 空合并 (内容已存在)
- 被 revert 的 commit
- 文档更新 (我们的版本更详细)

---

## 测试执行日志

| 时间 | Commit | L1 | L2 | 结果 |
|------|--------|----|----|------|
| 2026-03-01 | Phase 0-2 | ✅ | - | 通过 |
| 2026-03-02 | Phase 3-4 | ✅ | - | 通过 |
| 2026-03-02 | Phase 5 | ✅ | ✅ | 通过 |
| 2026-03-02 | 最终验证 | ✅ | ✅ | 通过 |

---

## 测试命令速查

```bash
# 快速 L1 测试
alias test-l1='python3 -m py_compile libs/deepagents/deepagents/graph.py libs/deepagents/deepagents/middleware/skills.py'

# 快速 L2 测试 (关键模块)
alias test-l2='cd libs/deepagents && uv run --group test pytest tests/unit_tests/middleware/test_skills_middleware.py -v -k "list_skills"'

# 完整测试
alias test-full='cd libs/deepagents && make test && cd ../cli && make test'

# V2 验证
alias test-v2='uv run python -c "from deepagents.middleware.skills import SkillsMiddleware; print(\"✅ V2 OK\")"'
```

---

**文档创建时间**: 2026-03-02
