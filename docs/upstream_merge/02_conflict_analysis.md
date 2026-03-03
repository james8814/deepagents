# 冲突影响分析

**文档类型**: 影响分析文档
**创建日期**: 2026-03-01
**分析范围**: james8814/deepagents vs langchain-ai/deepagents
**比较基准**: `5507c6f` (fork) vs `4a4be8e` (upstream)

---

## 📋 执行摘要

通过 GitHub API 比较两个仓库，发现 **231 个文件存在差异**。其中：

| 类别 | 数量 | 风险等级 |
|------|------|----------|
| 🔴 高风险冲突文件 | 12 | 需手动合并 |
| 🟡 中等风险文件 | 28 | 需审查后合并 |
| 🟢 低风险文件 | 35 | 可自动合并 |
| ⚪ 新增文件 | 156 | 直接接受 |

---

## 🔴 高风险冲突文件 (P0)

这些文件我们有大量自定义修改，与上游存在直接冲突：

### 1. `libs/deepagents/deepagents/middleware/skills.py`

| 属性 | Fork | Upstream |
|------|------|----------|
| 行数 | 1116 | 838 |
| 特性 | V2 (load_skill, unload_skill) | V1 (仅元数据) |

**冲突详情**:

我们实现的 V2 特性（上游不存在）：
- `load_skill()` 工具
- `unload_skill()` 工具
- `skills_loaded` 状态字段
- `skill_resources` 资源缓存
- `max_loaded_skills` 参数
- `_discover_resources()` 资源发现函数
- `_format_resource_summary()` 资源摘要格式化

**解决策略**:
- ✅ **保留我们的 V2 实现**
- 📥 可选：合并上游的 bug 修复（如有）
- 🔄 整合上游的文档改进

---

### 2. `libs/deepagents/deepagents/middleware/summarization.py`

| 属性 | Fork | Upstream |
|------|------|----------|
| 特性 | 自定义存储逻辑 | compaction hook |

**冲突详情**:

上游新增功能：
- `compact_conversation` 工具
- `SUMMARIZATION_SYSTEM_PROMPT` 更新
- `SummarizationEvent` TypedDict

我们的自定义：
- `_compute_summarization_defaults()` 函数
- 自定义的存储路径逻辑
- `history_path_prefix` 参数

**解决策略**:
- 📥 **合并上游的 compaction 功能**
- ✅ 保留我们的自定义存储逻辑
- 🔄 需要整合两边的修改

---

### 3. `libs/deepagents/deepagents/graph.py`

| 属性 | Fork | Upstream |
|------|------|----------|
| BASE_AGENT_PROMPT | 简短版本 | 详细版本 (新增行为准则) |
| 函数签名 | 有 `history_path_prefix` | 无此参数 |

**冲突详情**:

上游的 `BASE_AGENT_PROMPT` 包含新增内容：
- Core Behavior 准则
- Professional Objectivity 准则
- Doing Tasks 准则
- Progress Updates 准则

我们的自定义：
- `history_path_prefix` 参数
- `_compute_summarization_defaults()` 引用

**解决策略**:
- 📥 **采用上游的 BASE_AGENT_PROMPT** (更完善)
- ✅ 保留我们的 `history_path_prefix` 参数
- 🔄 整合 summarization 调用

---

### 4. `libs/deepagents/deepagents/middleware/filesystem.py`

| 属性 | Fork | Upstream |
|------|------|----------|
| 特性 | Upload Adapter V5 | 基础版本 |

**冲突详情**:

我们的自定义：
- 统一文件上传接口
- 大文件处理逻辑
- 与 `upload_adapter.py` 集成

**解决策略**:
- ✅ **保留我们的实现**
- 📥 检查上游是否有 bug 修复需要合并

---

### 5. `libs/cli/deepagents_cli/agent.py`

| 属性 | Fork | Upstream |
|------|------|----------|
| 特性 | 自定义 CLI agent | compaction hook 集成 |

**冲突详情**:

上游新增：
- compaction hook 配置
- 新的 middleware 配置

我们的自定义：
- 可能有自定义的 agent 创建逻辑

**解决策略**:
- 📥 合并上游的 compaction 配置
- ✅ 保留我们的自定义逻辑

---

### 6-12. 其他高风险文件

| 文件 | 冲突原因 | 解决策略 |
|------|----------|----------|
| `libs/deepagents/deepagents/middleware/__init__.py` | 导出差异 | 合并两边导出 |
| `libs/deepagents/deepagents/middleware/memory.py` | 自定义逻辑 | 保留 + 合并修复 |
| `libs/deepagents/deepagents/middleware/subagents.py` | 状态隔离逻辑 | 需审查差异 |
| `libs/deepagents/deepagents/backends/state.py` | Upload 集成 | 保留自定义 |
| `libs/deepagents/deepagents/backends/filesystem.py` | Upload 集成 | 保留自定义 |
| `libs/cli/deepagents_cli/app.py` | UI 变更 | 需审查合并 |

---

## 🟡 中等风险文件 (P1)

这些文件有修改但冲突可能性较低：

### SDK 核心

| 文件 | 变更类型 | 风险 |
|------|----------|------|
| `libs/deepagents/pyproject.toml` | 版本号、依赖 | 需合并 |
| `libs/deepagents/deepagents/_version.py` | 版本号 | 直接使用上游 |
| `libs/deepagents/deepagents/backends/protocol.py` | 接口变更 | 需审查 |
| `libs/deepagents/deepagents/backends/composite.py` | 功能更新 | 需审查 |
| `libs/deepagents/deepagents/backends/sandbox.py` | 功能更新 | 需审查 |

### CLI 相关

| 文件 | 变更类型 | 风险 |
|------|----------|------|
| `libs/cli/pyproject.toml` | 版本号、依赖 | 需合并 |
| `libs/cli/deepagents_cli/_version.py` | 版本号 | 直接使用上游 |
| `libs/cli/deepagents_cli/main.py` | 新功能 | 需审查 |
| `libs/cli/deepagents_cli/local_context.py` | 功能更新 | 需审查 |
| `libs/cli/deepagents_cli/integrations/daytona.py` | 集成更新 | 可选合并 |
| `libs/cli/deepagents_cli/integrations/modal.py` | 集成更新 | 可选合并 |
| `libs/cli/deepagents_cli/integrations/runloop.py` | 集成更新 | 可选合并 |

### 测试文件

| 文件 | 变更类型 | 风险 |
|------|----------|------|
| `tests/unit_tests/middleware/test_skills_middleware.py` | 测试更新 | 需保留 V2 测试 |
| `tests/unit_tests/middleware/test_summarization_middleware.py` | 测试更新 | 需合并 |
| `tests/integration_tests/test_filesystem_middleware.py` | 测试修复 | 可合并 |

### Backend 测试

| 文件 | 变更类型 | 风险 |
|------|----------|------|
| `tests/unit_tests/backends/test_state_backend.py` | 测试更新 | 需审查 |
| `tests/unit_tests/backends/test_filesystem_backend.py` | 测试更新 | 需审查 |
| `tests/unit_tests/backends/test_composite_backend.py` | 测试更新 | 需审查 |

---

## 🟢 低风险文件 (P2)

这些文件可以自动合并或直接使用上游版本：

### 新增合作伙伴库

| 目录 | 说明 |
|------|------|
| `libs/partners/modal/` | Modal sandbox 集成 (新增) |
| `libs/partners/runloop/` | Runloop sandbox 集成 (新增) |

### 配置文件

| 文件 | 说明 |
|------|------|
| `.github/workflows/ci.yml` | CI 配置更新 |
| `.github/workflows/release.yml` | 发布配置更新 |
| `.pre-commit-config.yaml` | Pre-commit 配置 |

### Lockfiles

| 文件 | 说明 |
|------|------|
| `libs/acp/uv.lock` | 依赖锁定 |
| `libs/harbor/uv.lock` | 依赖锁定 |
| `examples/*/uv.lock` | 示例项目依赖 |

---

## 📊 统计分析

### 按目录分布

```
libs/deepagents/
├── deepagents/           # 23 文件 (8 高风险)
│   ├── backends/         # 7 文件
│   ├── middleware/       # 8 文件 (6 高风险)
│   └── tests/            # 8 文件
├── libs/cli/             # 45 文件 (4 高风险)
├── libs/acp/             # 12 文件
├── libs/harbor/          # 6 文件
└── libs/partners/        # 42 文件 (新增)
```

### 按变更类型分布

| 类型 | 数量 |
|------|------|
| modified (修改) | 156 |
| added (新增) | 71 |
| removed (删除) | 4 |
| renamed (重命名) | 1 |

---

## 🎯 关键冲突点总结

### 1. SkillsMiddleware V2 vs V1

```
┌─────────────────────────────────────────────────────────┐
│                    SkillsMiddleware                      │
├─────────────────────┬───────────────────────────────────┤
│      Fork (V2)      │         Upstream (V1)             │
├─────────────────────┼───────────────────────────────────┤
│ load_skill() ✅     │ ❌ 不存在                         │
│ unload_skill() ✅   │ ❌ 不存在                         │
│ skills_loaded ✅    │ ❌ 不存在                         │
│ max_loaded_skills ✅│ ❌ 不存在                         │
│ 1116 行             │ 838 行                            │
└─────────────────────┴───────────────────────────────────┘
```

**结论**: 必须保留我们的 V2 实现，这是核心差异化功能。

### 2. SummarizationMiddleware 增强

```
┌─────────────────────────────────────────────────────────┐
│                 SummarizationMiddleware                  │
├─────────────────────┬───────────────────────────────────┤
│      Fork           │         Upstream                  │
├─────────────────────┼───────────────────────────────────┤
│ history_path_prefix │ compact_conversation 工具         │
│ 自定义存储逻辑       │ SUMMARIZATION_SYSTEM_PROMPT       │
│ _compute_defaults   │ SummarizationEvent                │
└─────────────────────┴───────────────────────────────────┘
```

**结论**: 需要整合两边的修改，接受 compaction 功能同时保留自定义逻辑。

### 3. BASE_AGENT_PROMPT 差异

```
Fork:   "In order to complete the objective..."
        (简短，约 1 行)

Upstream: 包含 Core Behavior, Professional Objectivity,
          Doing Tasks, Progress Updates 等
        (详细，约 40 行)
```

**结论**: 采用上游版本，更完善的 Agent 行为指导。

---

## ⚠️ 删除文件处理

以下文件在上游被删除，需要评估是否保留：

| 文件 | 状态 | 建议 |
|------|------|------|
| `libs/cli/deepagents_cli/backends.py` | 上游删除 | 检查是否迁移到其他文件 |
| `libs/cli/tests/unit_tests/test_backend_timeout.py` | 上游删除 | 检查是否合并到其他测试 |
| `libs/deepagents/tests/integration_tests/test_hitl.py` | 上游删除 | 迁移到 evals/ |
| `libs/deepagents/tests/integration_tests/test_summarization.py` | 上游删除 | 迁移到 evals/ |
| `.github/images/deepagents_tools.png` | 上游删除 | 可忽略 |

---

**下一步**: 参考 [03_实施方案.md](./03_实施方案.md) 了解具体合并步骤和冲突解决策略。
