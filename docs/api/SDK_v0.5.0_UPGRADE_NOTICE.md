# DeepAgents SDK v0.5.0 升级通知

**日期**: 2026-03-20
**发布版本**: SDK 0.5.0 / CLI 0.0.34
**上一版本**: SDK 0.4.10 / CLI 0.0.27
**紧急程度**: 中 — 现有代码短期内仍可运行，但建议尽早适配

---

## 升级概要

本次升级合并了上游 langchain-ai/deepagents 的 143 个提交，包含 Backend 类型体系重构、异步子代理、CLI 全面升级等重大变更。

**所有本地增强功能（SkillsMiddleware V2、Converters、SubAgent 日志、upload_adapter 等）均已保留，无需担心功能丢失。**

---

## 需要您关注的变更

### 1. Backend 返回类型变更（最重要）

如果您的项目实现了自定义 Backend（继承 `BackendProtocol`），或直接调用 Backend 方法，请注意两项变更：

**1) 方法名已重命名：**

| 旧方法名 | 新方法名 |
|----------|---------|
| `ls_info()` | **`ls()`** |
| `grep_raw()` | **`grep()`** |
| `glob_info()` | **`glob()`** |

**2) 返回类型已从裸 `list`/`str` 升级为强类型 dataclass：**

| 方法 | 返回类型 |
|------|---------|
| `ls()` | `LsResult(error, entries)` |
| `read()` | `ReadResult(error, file_data)` |
| `grep()` | `GrepResult(error, matches)` |
| `glob()` | `GlobResult(error, matches)` |

**兼容性说明**：
- 旧方法名（`ls_info`/`grep_raw`/`glob_info`）仍然可以工作（deprecation shim）
- 旧返回类型仍然可以工作（内置 deprecation 兼容层）
- 但两者都会打印 `DeprecationWarning`
- 建议尽早迁移到新方法名 + 新返回类型

**迁移方法**：

```python
from deepagents.backends.protocol import LsResult

# 旧代码
items = backend.ls_info("/path")

# 新代码 (方法名 + 返回类型)
result = backend.ls("/path")
if isinstance(result, LsResult):
    items = result.entries or []
else:
    items = result  # 旧类型兼容
```

### 2. 图片读取行为变更

`read_file` 工具读取图片文件（`.png/.jpg/.gif/.webp`）的内部实现已变更：
- **旧方式**：`download_files()` → base64 编码 → `ToolMessage`
- **新方式**：`read()` → `ReadResult` → `_handle_read_result` → `ToolMessage`

**对外部团队的影响**：
- 如果您只通过 `create_deep_agent()` 使用 Agent，**无需任何改动**，`read_file` 工具行为不变
- 如果您直接调用 `backend.read()` 读取图片文件，返回值现在是 `ReadResult` 对象

### 3. 新增异步子代理功能

新增 `AsyncSubAgentMiddleware`，支持连接远程 LangGraph 服务器。

> **重要**：`async_subagents` 参数已合并到统一的 `subagents` 参数中。通过 `graph_id` 字段自动区分同步/异步子代理。

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    subagents=[
        # 同步子代理
        {"name": "helper", "description": "Help with tasks", "system_prompt": "You help."},
        # 异步子代理 (通过 graph_id 识别)
        {
            "name": "researcher",
            "description": "Research agent on remote server",
            "graph_id": "research-agent",
            "url": "http://localhost:8123",
        }
    ],
)
```

**新增公共导出**：
```python
from deepagents import AsyncSubAgent, AsyncSubAgentJob, AsyncSubAgentMiddleware
```

这是新增功能，不影响现有代码。

### 4. 默认模型变更

默认模型从 `claude-sonnet-4-5-20250929` 更新为 `claude-sonnet-4-6`。

如果您的项目显式指定了模型，不受影响。如果使用默认模型，请注意可能的行为差异。

### 5. 依赖版本要求提升

| 依赖 | 旧版本 | 新版本 |
|------|--------|--------|
| `langchain-core` | >=1.2.18 | **>=1.2.19** |
| `langchain` | >=1.2.11 | **>=1.2.12** |
| `langchain-anthropic` | >=1.3.4 | **>=1.3.5** |

如果您的项目锁定了这些依赖的版本，请确保满足新的最低版本要求。

---

## 不受影响的功能

以下功能完全向后兼容，无需改动：

- `create_deep_agent()` 的所有现有参数（`model`、`tools`、`subagents`、`skills`、`middleware` 等）
- `SkillsMiddleware V2`（`load_skill`/`unload_skill`/`expose_dynamic_tools`/`allowed_skills`）
- `Converters` 系统（PDF/DOCX/XLSX/PPTX 自动转换）
- `upload_files()` / `UploadResult`
- `SubAgentMiddleware` 和 `task` 工具
- `MemoryMiddleware` 和 `AGENTS.md` 加载

---

## 检查清单

升级后请逐项确认：

- [ ] `pip install -e libs/deepagents` 或 `uv sync` 成功
- [ ] `python -c "from deepagents import create_deep_agent; print('OK')"` 通过
- [ ] 如有自定义 Backend：将 `ls_info`→`ls`、`grep_raw`→`grep`、`glob_info`→`glob` 方法名更新
- [ ] 如有自定义 Backend：检查返回类型是否产生 deprecation warning
- [ ] 如使用 `async_subagents=` 参数：改为 `subagents=`（在 spec 中加 `graph_id` 字段）
- [ ] 运行项目测试套件确认无回归
- [ ] 如使用 `langchain-anthropic`：确认版本满足 >=1.4.0（已提升）

---

## 联系方式

如遇到升级问题，请联系项目维护团队。

**参考文档**：
- [外部团队 API 指南](EXTERNAL_TEAM_API_GUIDE.md)（已更新至 v2.0.0）
- [上游合并风险分析报告](../upstream_merge/2026-03-17_upstream_143_commits_risk_analysis.md)
