# 测试验证方案

**文档类型**: 测试策略文档
**创建日期**: 2026-03-01
**适用范围**: 上游 v0.4.4 合并验证
**测试级别**: 单元测试 + 集成测试 + 回归测试

---

## 📋 执行摘要

合并后的测试验证分为三个层次：

| 层次 | 覆盖范围 | 通过标准 |
|------|----------|----------|
| L1: 冒烟测试 | 核心导入和基本功能 | 100% 通过 |
| L2: 单元测试 | 所有模块的单元测试 | 100% 通过 |
| L3: 集成测试 | 跨模块集成验证 | 100% 通过 |
| L4: 回归测试 | 自定义功能验证 | 100% 通过 |

---

## 🎯 测试范围

### 1. 自定义功能验证 (L4 回归测试)

这些是我们的核心差异化功能，必须确保合并后正常工作：

#### 1.1 SkillsMiddleware V2

| 功能 | 测试文件 | 验证点 |
|------|----------|--------|
| `load_skill()` | `test_skills_middleware.py` | 工具存在，可调用 |
| `unload_skill()` | `test_skills_middleware.py` | 工具存在，可调用 |
| `skills_loaded` 状态 | `test_skills_middleware.py` | 状态正确更新 |
| `skill_resources` 缓存 | `test_skills_middleware.py` | 资源正确发现 |
| `max_loaded_skills` 限制 | `test_skills_middleware.py` | 限制生效 |

**测试命令**:
```bash
cd libs/deepagents
uv run --group test pytest tests/unit_tests/middleware/test_skills_middleware.py -v
uv run --group test pytest tests/unit_tests/middleware/test_skills_middleware_async.py -v
```

**验证脚本**:
```python
# test_skills_v2.py
from deepagents.middleware.skills import SkillsMiddleware

# 验证 V2 特性存在
middleware = SkillsMiddleware(backend=mock_backend, sources=["/skills/"])

# 1. 检查 tools 属性
assert len(middleware.tools) == 2
assert middleware.tools[0].name == "load_skill"
assert middleware.tools[1].name == "unload_skill"

# 2. 检查 max_loaded_skills
assert middleware._max_loaded_skills == 10

# 3. 检查状态字段
from deepagents.middleware.skills import SkillsState
assert "skills_loaded" in SkillsState.__annotations__
assert "skill_resources" in SkillsState.__annotations__

print("✅ SkillsMiddleware V2 验证通过")
```

#### 1.2 Upload Adapter V5

| 功能 | 测试文件 | 验证点 |
|------|----------|--------|
| `upload_files()` | `test_upload_adapter.py` | 统一接口工作 |
| `UploadResult` | `test_upload_adapter.py` | 结果格式正确 |
| StateBackend 上传 | `test_upload_adapter.py` | 策略选择正确 |
| FilesystemBackend 上传 | `test_upload_adapter.py` | 策略选择正确 |

**测试命令**:
```bash
cd libs/deepagents
uv run --group test pytest tests/unit_tests/test_upload_adapter.py -v
```

#### 1.3 自定义 Summarization

| 功能 | 测试文件 | 验证点 |
|------|----------|--------|
| `history_path_prefix` | `test_summarization.py` | 参数生效 |
| `_compute_summarization_defaults` | `test_summarization.py` | 函数存在 |

---

### 2. 上游新功能验证 (L2 单元测试)

#### 2.1 Compaction Hook

| 功能 | 测试文件 | 验证点 |
|------|----------|--------|
| `compact_conversation` 工具 | `test_compact_tool.py` | 工具存在 |
| Compaction 触发 | `test_compact.py` | 触发逻辑正确 |
| 系统提示注入 | `test_summarization.py` | 提示正确注入 |

**测试命令**:
```bash
cd libs/deepagents
uv run --group test pytest tests/unit_tests/middleware/test_compact_tool.py -v
uv run --group test pytest tests/unit_tests/middleware/test_summarization_middleware.py -v

cd ../cli
uv run --group test pytest tests/unit_tests/test_compact.py -v
uv run --group test pytest tests/unit_tests/test_compact_tool.py -v
```

#### 2.2 Bug 修复验证

| Bug | 测试文件 | 验证点 |
|-----|----------|--------|
| except 块顺序 | `test_non_interactive.py` | NotImplementedError 正确捕获 |
| 变量重复定义 | `test_filesystem_middleware.py` | 无静态分析警告 |

---

### 3. 核心模块测试 (L2)

#### 3.1 Backend 测试

```bash
cd libs/deepagents
uv run --group test pytest tests/unit_tests/backends/ -v
```

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_state_backend.py` | StateBackend 功能 |
| `test_filesystem_backend.py` | FilesystemBackend 功能 |
| `test_composite_backend.py` | CompositeBackend 路由 |
| `test_sandbox_backend.py` | SandboxBackend 功能 |

#### 3.2 Middleware 测试

```bash
cd libs/deepagents
uv run --group test pytest tests/unit_tests/middleware/ -v
```

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_skills_middleware.py` | SkillsMiddleware V2 |
| `test_summarization_middleware.py` | Summarization |
| `test_memory_middleware.py` | MemoryMiddleware |
| `test_filesystem_middleware_init.py` | FilesystemMiddleware |

---

### 4. 集成测试 (L3)

#### 4.1 Deep Agent 集成

```bash
cd libs/deepagents
uv run --group test pytest tests/integration_tests/ -v
```

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_deepagents.py` | 完整 agent 创建和执行 |
| `test_filesystem_middleware.py` | 文件操作集成 |
| `test_subagent_middleware.py` | 子 agent 集成 |

#### 4.2 CLI 集成

```bash
cd libs/cli
uv run --group test pytest tests/integration_tests/ -v
```

---

### 5. 冒烟测试 (L1)

快速验证基本功能：

```bash
# 1. 导入检查
python -c "from deepagents import create_deep_agent; print('✅ create_deep_agent')"
python -c "from deepagents.middleware.skills import SkillsMiddleware; print('✅ SkillsMiddleware')"
python -c "from deepagents.middleware.summarization import SummarizationMiddleware; print('✅ SummarizationMiddleware')"
python -c "from deepagents.backends import StateBackend, FilesystemBackend; print('✅ Backends')"
python -c "from deepagents import upload_files, UploadResult; print('✅ Upload Adapter')"

# 2. Agent 创建检查
python -c "
from deepagents import create_deep_agent
agent = create_deep_agent()
print(f'✅ Agent created: {type(agent).__name__}')
"

# 3. SkillsMiddleware V2 检查
python -c "
from deepagents.middleware.skills import SkillsMiddleware
m = SkillsMiddleware.__init__
print(f'✅ SkillsMiddleware has tools attr: {hasattr(SkillsMiddleware, \"tools\")}')
"

# 4. 版本检查
python -c "
from deepagents import __version__
print(f'✅ Version: {__version__}')
"
```

---

## 📋 测试执行清单

### Phase 1: 冒烟测试 (5 分钟)

```bash
# 在合并后的环境中执行
cd libs/deepagents

# 1. 导入测试
python -c "from deepagents import create_deep_agent"

# 2. 版本确认
python -c "from deepagents import __version__; print(__version__)"

# 3. V2 特性确认
python -c "from deepagents.middleware.skills import SkillsMiddleware; print(hasattr(SkillsMiddleware, 'tools'))"
```

**通过标准**: 所有命令无错误执行

### Phase 2: 单元测试 (30 分钟)

```bash
# SDK 单元测试
cd libs/deepagents
uv run --group test pytest tests/unit_tests/ -v --tb=short

# CLI 单元测试
cd ../cli
uv run --group test pytest tests/unit_tests/ -v --tb=short
```

**通过标准**: 所有测试通过，无 failures

### Phase 3: 集成测试 (30 分钟)

```bash
# SDK 集成测试
cd libs/deepagents
uv run --group test pytest tests/integration_tests/ -v --timeout 60

# CLI 集成测试
cd ../cli
uv run --group test pytest tests/integration_tests/ -v --timeout 60
```

**通过标准**: 所有测试通过

### Phase 4: 回归测试 (30 分钟)

```bash
# Skills V2 测试
cd libs/deepagents
uv run --group test pytest tests/unit_tests/middleware/test_skills_middleware.py -v
uv run --group test pytest tests/unit_tests/middleware/test_skills_middleware_async.py -v

# Upload Adapter 测试
uv run --group test pytest tests/unit_tests/test_upload_adapter.py -v
```

**通过标准**: 所有自定义功能正常

---

## 🚨 失败处理

### 常见问题及解决方案

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 导入失败 | 模块路径变更 | 检查 `__init__.py` 导出 |
| V2 特性丢失 | skills.py 被覆盖 | 重新应用 ours 策略 |
| 测试失败 | 接口变更 | 更新测试适配新接口 |
| 依赖冲突 | 版本不兼容 | 更新 pyproject.toml |

### 回滚触发条件

如果出现以下情况，考虑回滚：

1. 🔴 V2 特性完全丢失
2. 🔴 核心功能测试失败 > 5 个
3. 🔴 无法解决的依赖冲突
4. 🔴 Agent 创建失败

---

## 📊 测试覆盖率要求

| 模块 | 最低覆盖率 | 当前状态 |
|------|------------|----------|
| SkillsMiddleware | 80% | 需验证 |
| SummarizationMiddleware | 75% | 需验证 |
| FilesystemMiddleware | 80% | 需验证 |
| Backends | 70% | 需验证 |

```bash
# 生成覆盖率报告
cd libs/deepagents
uv run --group test pytest --cov=deepagents --cov-report=html tests/unit_tests/
```

---

## 📅 测试时间表

| 阶段 | 预估时间 | 累计 |
|------|----------|------|
| L1: 冒烟测试 | 5 min | 5 min |
| L2: 单元测试 | 30 min | 35 min |
| L3: 集成测试 | 30 min | 65 min |
| L4: 回归测试 | 30 min | 95 min |

**总计**: 约 1.5-2 小时

---

## ✅ 最终验收标准

合并验收需要满足以下所有条件：

- [ ] 所有冒烟测试通过
- [ ] 所有单元测试通过 (0 failures)
- [ ] 所有集成测试通过 (0 failures)
- [ ] SkillsMiddleware V2 功能完整
- [ ] Upload Adapter V5 功能完整
- [ ] Compaction hook 功能可用
- [ ] 版本号正确更新
- [ ] 无新增的安全警告
- [ ] 代码覆盖率未下降

---

**相关文档**:
- [01_commit_analysis.md](./01_commit_analysis.md) - Commit 分析
- [02_conflict_analysis.md](./02_conflict_analysis.md) - 冲突影响分析
- [03_implementation_plan.md](./03_implementation_plan.md) - 实施方案
