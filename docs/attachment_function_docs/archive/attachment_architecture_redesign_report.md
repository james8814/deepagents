# Deep Agents 附件管理机制重构设计报告

**版本**: v1.0
**日期**: 2026-02-26
**状态**: 设计阶段

---

## 1. 调研摘要

### 1.1 现有项目对比分析

| 项目 | 文件管理策略 | Context 策略 | 关键洞察 |
|------|-------------|--------------|----------|
| **Claude Code** | 自动缓存所有打开文件 | Context Caching (ephemeral) | 文件作为"隐式上下文"，用户无感知 |
| **Manus AI** | 文件作为 Memory 存储 | File-based Memory + AREL | 大文件走 RAG，小文件直接注入 |
| **Open Code** | 工具驱动 | 显式 `read_file` | 无自动注入，完全显式控制 |
| **OpenClawd** | State-backed | 与 State 绑定 | 文件即状态，可版本化 |

### 1.2 Deep Agents 现有中间件模式分析

#### SkillsMiddleware V2 (已验证的模式)

```python
# 核心设计原则
class SkillsMiddleware:
    state_schema = SkillsState  # 声明式状态管理
    tools = [load_skill, unload_skill]  # 显式生命周期控制

    # Progressive Disclosure (渐进式披露)
    - 启动时：只注入元数据 (name, description)
    - 使用时：调用 load_skill() 加载完整内容
    - 退出时：调用 unload_skill() 释放资源

    # 预算管理
    - max_loaded_skills: 限制同时加载数量
    - 状态持久化: skills_loaded, skill_resources
```

#### MemoryMiddleware (对比模式)

```python
# 与 Skills 的核心区别
class MemoryMiddleware:
    # 无 tools - 完全自动管理
    # 启动时全量加载，无卸载概念
    # 适合: 小型、稳定的上下文 (AGENTS.md)
```

---

## 2. 当前 AttachmentMiddleware 的问题诊断

### 2.1 架构层面问题

```python
# 当前实现 (问题版本)
class AttachmentMiddleware:
    # ❌ 无 state_schema - 无法利用 LangGraph state 管理
    # ❌ 无 tools - 无生命周期控制
    # ❌ 每次请求重新扫描目录
    # ❌ 阈值硬编码，无预算概念
```

| 问题 | 影响 | 与 Skills V2 对比 |
|------|------|------------------|
| 无状态声明 | Context 无法持久化，每次重新读取 | Skills 有 `SkillsState` |
| 无工具控制 | 无法显式 load/unload | Skills 有 `load_skill/unload_skill` |
| 自动全量扫描 | 性能开销大，无法预测 | Skills 渐进式披露 |
| 硬编码阈值 | 无法适应不同模型/场景 | Skills 有 `max_loaded_skills` |

### 2.2 与 Framework 的冲突

```python
# LangGraph State 管理哲学
"State is the single source of truth"

# 当前 AttachmentMiddleware 的问题:
# 1. 从 backend 读取文件 (正确)
# 2. 直接注入 system message (正确)
# 3. 但: 没有记录"已注入"状态 (错误!)
# 4. 每次请求重复扫描 (性能问题)
```

---

## 3. 优雅设计方案: Stateful Attachment Management

### 3.1 核心理念: "Attachments as Skills"

将附件视为**特殊的、一次性的 Skills**：

```
Skill:          reusable, 有目录结构, 可多次加载/卸载
Attachment:     one-time, 扁平存储, 通常加载后不解绑
```

### 3.2 新架构设计

```python
# attachment_v2.py
from typing import NotRequired, Annotated, TypedDict
from langchain.agents.middleware.types import PrivateStateAttr

class AttachmentMetadata(TypedDict):
    """附件元数据 - 类似于 SkillMetadata"""
    id: str  # 唯一标识符 (UUID)
    name: str  # 文件名
    path: str  # 存储路径
    mime_type: str
    size: int
    token_estimate: int
    status: Literal["pending", "loaded", "unloaded"]
    loaded_at: str | None  # ISO timestamp

class LoadedAttachment(TypedDict):
    """已加载的附件状态"""
    id: str
    content: str  # 内容或引用
    content_type: Literal["full", "metadata_only"]  # 加载模式
    token_count: int  # 实际 token 数

class AttachmentState(AgentState):
    """State schema - 遵循 LangGraph 最佳实践"""
    attachments_metadata: Annotated[list[AttachmentMetadata], PrivateStateAttr]
    attachments_loaded: Annotated[list[LoadedAttachment], PrivateStateAttr]
    attachments_budget_used: Annotated[int, PrivateStateAttr]  # 已用 token 预算

class AttachmentMiddleware(AgentMiddleware):
    """
    附件管理中间件 - V2 重构版

    设计原则:
    1. 声明式状态管理 (state_schema)
    2. 显式生命周期控制 (tools)
    3. 渐进式披露 (progressive disclosure)
    4. 预算管理 (token budget)
    """
    state_schema = AttachmentState

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        uploads_dir: str = "/uploads",
        max_attachment_tokens: int = 50000,  # 附件专用预算
        max_attachments: int = 10,  # 数量限制
        auto_load_small_files: bool = True,  # < 1k tokens 自动加载
    ):
        self._backend = backend
        self._uploads_dir = uploads_dir
        self._max_tokens = max_attachment_tokens
        self._max_count = max_attachments
        self._auto_load = auto_load_small_files

        # 工具注册
        self.tools = [
            self._create_upload_attachment_tool(),
            self._create_load_attachment_tool(),
            self._create_unload_attachment_tool(),
            self._create_list_attachments_tool(),
        ]
```

### 3.3 工具设计

#### Tool 1: upload_attachment

```python
def upload_attachment(
    file_path: str,
    runtime: ToolRuntime,
) -> Command | str:
    """
    上传文件到附件系统。

    流程:
    1. 验证文件存在
    2. 生成 attachment_id
    3. 估算 token 数
    4. (可选) 小文件自动加载
    5. 更新 metadata 到 state
    """
```

#### Tool 2: load_attachment

```python
def load_attachment(
    attachment_id: str,
    mode: Literal["auto", "full", "metadata_only"] = "auto",
    runtime: ToolRuntime,
) -> Command | str:
    """
    加载附件到上下文。

    预算检查:
    - 如果 full 模式超预算 -> 降级为 metadata_only
    - 如果 metadata_only 也超预算 -> 返回错误提示 unload 其他附件

    Context 注入策略:
    - full: 注入完整内容，带 cache_control
    - metadata_only: 只注入描述信息，提示 Agent 使用 read_file
    """
```

#### Tool 3: unload_attachment

```python
def unload_attachment(
    attachment_id: str,
    runtime: ToolRuntime,
) -> Command | str:
    """
    从上下文中卸载附件，释放预算。

    注意: 卸载不会删除文件，只从 context 中移除。
    """
```

#### Tool 4: list_attachments

```python
def list_attachments(
    runtime: ToolRuntime,
) -> str:
    """
    列出所有已上传附件及其状态。

    输出格式:
    ```
    [Loaded] data.csv (15k tokens) - ID: att_xxx
    [Pending] large.log (est. 500k tokens) - ID: att_yyy
              ^ Use load_attachment("att_yyy") to access
    ```
    """
```

### 3.4 Context 注入策略

```python
def _inject_attachments(self, request: ModelRequest) -> ModelRequest:
    """
    与 SkillsMiddleware 类似的注入逻辑
    """
    loaded = request.state.get("attachments_loaded", [])

    if not loaded:
        return request

    # 分段缓存策略
    content_blocks = []

    for att in loaded:
        if att["content_type"] == "full":
            # 每个附件独立缓存块
            content_blocks.append({
                "type": "text",
                "text": f"<attachment id=\"{att['id']}\">{att['content']}</attachment>",
                "cache_control": {"type": "ephemeral"}
            })
        else:
            # metadata_only 模式
            content_blocks.append({
                "type": "text",
                "text": f"<attachment id=\"{att['id']}\" mode=\"metadata_only\">...use tools...</attachment>"
            })

    # 合并到 system message
    return request.override(
        system_message=append_content_blocks(request.system_message, content_blocks)
    )
```

---

## 4. 与现有中间件的协同

### 4.1 与 SkillsMiddleware 的协同

```python
# 预算分配建议
class ContextBudget:
    """总上下文预算分配"""
    SYSTEM_PROMPT: int = 2000      # 基础提示词
    MEMORY: int = 10000            # AGENTS.md
    SKILLS: int = 30000            # 最多 10 个 skill x 3k tokens
    ATTACHMENTS: int = 40000       # 附件专用预算
    CONVERSATION: int = 16000      # 历史消息保留
    # Total: ~100k (Claude Sonnet 4.5 支持 200k)
```

### 4.2 与 SummarizationMiddleware 的协同

```python
# Summarization 触发时:
# 1. 压缩 conversation history
# 2. 不压缩 attachments (已在 cache 中)
# 3. 如果 attachments 总 token 过大，提示用户 unload
```

---

## 5. 实施路线图

### Phase 1: 核心重构 (1 周)

- [ ] 实现 `AttachmentState` 状态定义
- [ ] 实现 4 个工具 (upload/load/unload/list)
- [ ] 实现 `wrap_model_call` 注入逻辑
- [ ] 单元测试覆盖

### Phase 2: 高级特性 (1 周)

- [ ] 自动降级逻辑 (full -> metadata_only)
- [ ] 多模态支持 (图片、PDF)
- [ ] 与 CLI 的 `/upload` 命令集成

### Phase 3: 优化 (1 周)

- [ ] Token 估算优化 (file size based)
- [ ] 异步 I/O 优化
- [ ] 性能基准测试

---

## 6. 关键设计决策

### Decision 1: 是否保留自动扫描?

**选项 A**: 保留自动扫描 `/uploads` 目录 (当前设计)
**选项 B**: 完全显式工具控制 (推荐)

**推荐 B 的理由**:
1. 与 Skills V2 模式一致
2. 可预测的性能 (无意外的大文件读取)
3. 用户意图明确 (显式 upload 才处理)

### Decision 2: 预算超限如何处理?

**选项 A**: 拒绝加载新附件
**选项 B**: 自动降级为 metadata_only
**选项 C**: LRU 驱逐旧附件

**推荐 B + 可选 C**:
```python
if new_tokens + budget_used > max_tokens:
    if mode == "full":
        return "建议降级为 metadata_only"
    else:
        return "预算已满，请 unload 其他附件"
```

### Decision 3: 与 Backend 的关系

```python
# 遵循现有模式
backend.upload_files()  # 写入 backend
backend.read()          # 读取内容

# AttachmentMiddleware 只管理"哪些文件在 context 中"
# 不管理文件存储本身
```

---

## 7. 代码示例

### 用户使用示例

```python
from deepagents import create_deep_agent
from deepagents.middleware.attachment import AttachmentMiddleware
from deepagents.backends import FilesystemBackend

agent = create_deep_agent(
    middleware=[
        AttachmentMiddleware(
            backend=FilesystemBackend(root_dir="/workspace"),
            max_attachment_tokens=50000,
        )
    ]
)

# 用户交互流程:
# 1. User: "/upload data.csv"
# 2. Agent: upload_attachment("/workspace/data.csv")
# 3. (自动加载，小文件)
# 4. User: "分析这个文件"
# 5. Agent: 直接访问已加载内容

# 大文件场景:
# 1. User: "/upload huge.log"
# 2. Agent: upload_attachment("/workspace/huge.log")
# 3. (检测到大文件，标记为 metadata_only)
# 4. User: "分析这个文件"
# 5. Agent: grep + read_file 工具链访问
```

---

## 8. 总结

### 新设计的优势

| 维度 | 当前设计 | 新设计 |
|------|---------|--------|
| **架构一致性** | ❌ 独特模式 | ✅ 与 Skills V2 一致 |
| **状态管理** | ❌ 无状态 | ✅ 声明式 state_schema |
| **生命周期** | ❌ 无控制 | ✅ 显式 tools |
| **预算管理** | ❌ 硬编码 | ✅ 可配置 |
| **性能** | ❌ 每次扫描 | ✅ 状态驱动 |
| **可预测性** | ❌ 隐式行为 | ✅ 显式控制 |

### 核心原则

1. **"Attachments are skills for data"** - 用管理技能的方式管理附件
2. **"State is truth"** - 所有状态通过 LangGraph state 管理
3. **"Explicit over implicit"** - 显式工具调用优于自动魔法
4. **"Budget matters"** - 上下文资源是有限的，需要管理

---

**下一步行动**: 审查此设计文档，确认后开始 Phase 1 实施。
