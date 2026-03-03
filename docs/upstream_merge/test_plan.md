# 上游合并测试方案

**版本**: v0.4.4 合并测试
**日期**: 2026-03-02
**架构师**: Claude Opus 4.6
**测试范围**: langchain-ai/deepagents v0.4.4 合并验证

---

## 1. 测试目标

| 目标 | 描述 | 优先级 |
|------|------|--------|
| 正确性 | 确保所有代码语法正确，无合并冲突残留 | P0 |
| 系统性 | 确保所有模块正确导入，依赖关系完整 | P0 |
| 完整性 | 确保所有上游功能已整合，自定义功能保留 | P0 |
| 质量保证 | 单元测试通过，功能验证完成 | P1 |

---

## 2. 测试级别定义

```
┌─────────────────────────────────────────────────────────────┐
│ L4: 集成测试 + 版本验证                                      │
│     - 完整 E2E 测试                                          │
│     - 版本号验证                                             │
│     - 发布准备检查                                           │
├─────────────────────────────────────────────────────────────┤
│ L3: 自定义功能验证                                           │
│     - SkillsMiddleware V2 (load_skill/unload_skill)         │
│     - Upload Adapter V5 (upload_files)                      │
│     - history_path_prefix 参数                              │
│     - Converters 功能                                        │
├─────────────────────────────────────────────────────────────┤
│ L2: 单元测试执行                                             │
│     - SDK 单元测试 (pytest)                                  │
│     - CLI 单元测试 (pytest)                                  │
│     - 测试覆盖率检查                                         │
├─────────────────────────────────────────────────────────────┤
│ L1: 代码完整性和语法验证                                     │
│     - 冲突标记检查 (<<<<<, >>>>>, ====)                      │
│     - Python 语法验证 (py_compile)                           │
│     - 导入检查 (import test)                                 │
│     - 类型检查 (可选)                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 测试用例清单

### 3.1 L1: 代码完整性和语法验证

| ID | 测试项 | 命令/方法 | 预期结果 |
|----|--------|-----------|----------|
| L1.1 | 冲突标记检查 | `grep -r "<<<<<<" libs/` | 无匹配 |
| L1.2 | Python 语法检查 SDK | `python -m py_compile` | 无错误 |
| L1.3 | Python 语法检查 CLI | `python -m py_compile` | 无错误 |
| L1.4 | SDK 导入测试 | `from deepagents import create_deep_agent` | 成功 |
| L1.5 | CLI 导入测试 | `from deepagents_cli import cli_main` | 成功 |
| L1.6 | ACP 导入测试 | `from deepagents_acp import ...` | 成功 |

### 3.2 L2: 单元测试执行

| ID | 测试项 | 命令 | 预期结果 |
|----|--------|------|----------|
| L2.1 | SDK 单元测试 | `cd libs/deepagents && make test` | 全部通过 |
| L2.2 | CLI 单元测试 | `cd libs/cli && make test` | 全部通过 |
| L2.3 | 关键模块测试 | `pytest tests/unit_tests/middleware/` | 全部通过 |

### 3.3 L3: 自定义功能验证

| ID | 测试项 | 验证方法 | 预期结果 |
|----|--------|----------|----------|
| L3.1 | SkillsMiddleware V2 | 检查 load_skill/unload_skill 存在 | 功能存在 |
| L3.2 | ResourceMetadata | 检查类型定义存在 | 类型存在 |
| L3.3 | skills_loaded state | 检查状态字段存在 | 字段存在 |
| L3.4 | Upload Adapter V5 | `from deepagents import upload_files` | 导入成功 |
| L3.5 | history_path_prefix | 检查 graph.py 参数存在 | 参数存在 |
| L3.6 | Converters | 检查 filesystem.py 导入 | 导入存在 |

### 3.4 L4: 集成测试和版本验证

| ID | 测试项 | 验证方法 | 预期结果 |
|----|--------|----------|----------|
| L4.1 | SDK 版本号 | 检查 `__version__` | "0.4.4" |
| L4.2 | CLI 版本号 | 检查 `_version.py` | "0.0.25" |
| L4.3 | 依赖版本 | 检查 pyproject.toml | 版本正确 |
| L4.4 | 创建 Agent 测试 | `create_deep_agent()` | 成功创建 |
| L4.5 | 安全修复验证 | 检查 path traversal 修复 | 修复存在 |

---

## 4. 关键文件清单

### 4.1 必须保护的自定义功能文件

| 文件 | 功能 | 验证优先级 |
|------|------|------------|
| `libs/deepagents/deepagents/middleware/skills.py` | SkillsMiddleware V2 | P0 |
| `libs/deepagents/deepagents/upload_adapter.py` | Upload Adapter V5 | P0 |
| `libs/deepagents/deepagents/graph.py` | history_path_prefix | P0 |
| `libs/deepagents/deepagents/middleware/filesystem.py` | Converters | P1 |

### 4.2 安全修复验证文件

| 文件 | 修复内容 | Commit |
|------|----------|--------|
| `libs/deepagents/deepagents/middleware/filesystem.py` | Path traversal in glob | `194a2db6` |
| `libs/deepagents/deepagents/backends/protocol.py` | Path validation | `0802cf01` |
| `libs/harbor/deepagents_harbor/harbor_sandbox.py` | Command injection | `625a9ff8` |

---

## 5. 测试执行顺序

```
1. L1 测试 (阻塞式) → 失败则修复后继续
       ↓
2. L2 测试 (阻塞式) → 失败则修复后继续
       ↓
3. L3 测试 (阻塞式) → 失败则修复后继续
       ↓
4. L4 测试 (阻塞式) → 失败则修复后继续
       ↓
5. 生成测试报告
```

---

## 6. 验收标准

| 级别 | 通过标准 | 失败处理 |
|------|----------|----------|
| L1 | 100% 通过 | 必须修复后继续 |
| L2 | ≥95% 通过 | 评估失败用例，决定是否阻塞 |
| L3 | 100% 通过 | 必须修复后继续 |
| L4 | 100% 通过 | 必须修复后继续 |

---

## 7. 测试环境

- **Python**: 3.11+
- **包管理**: uv
- **工作目录**: `/Volumes/0-/jameswu projects/deepagents`
- **分支**: `merge-upstream-0.4.4-incremental`

---

**批准人**: ________________
**执行人**: Claude Opus 4.6
**日期**: 2026-03-02
