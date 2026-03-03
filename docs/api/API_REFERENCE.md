# DeepAgents API 参考文档

**版本**: 0.4.4
**日期**: 2026-03-03

---

## 核心 API

### create_deep_agent

创建 Deep Agent 的主要入口函数。

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model=None,                    # 可选: LLM 模型实例
    tools=None,                    # 可选: 额外工具列表
    system_prompt=None,            # 可选: 自定义系统提示
    backend=None,                  # 可选: 后端实例
    sources=None,                  # 可选: 技能源路径
    max_loaded_skills=10,          # 可选: 最大加载技能数
    history_path_prefix=None,      # 可选: 历史记录路径前缀
    middlewares=None,              # 可选: 自定义中间件
    auto_approve=False,            # 可选: 自动批准工具调用
)
```

#### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | BaseChatModel | None | LLM 模型，默认使用 Claude Sonnet 4.5 |
| `tools` | List[BaseTool] | None | 额外工具列表 |
| `system_prompt` | str | None | 自定义系统提示 |
| `backend` | BackendProtocol | None | 后端实例，默认 StateBackend |
| `sources` | List[str] | None | 技能源路径列表 |
| `max_loaded_skills` | int | 10 | 最大同时加载技能数 |
| `history_path_prefix` | str | None | 历史记录存储路径前缀 |
| `middlewares` | List | None | 自定义中间件列表 |
| `auto_approve` | bool | False | 是否自动批准工具调用 |

#### 返回值

返回编译后的 `CompiledGraph` 实例，可调用 `invoke()`、`stream()` 等方法。

#### 示例

```python
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

# 基础用法
agent = create_deep_agent()

# 使用自定义模型
agent = create_deep_agent(
    model=ChatOpenAI(model="gpt-4o")
)

# 使用自定义技能源
agent = create_deep_agent(
    sources=["/skills/user", "/skills/team"],
    max_loaded_skills=5
)

# 调用
result = agent.invoke({
    "messages": [{"role": "user", "content": "Hello"}]
})
```

---

## 中间件 API

### FilesystemMiddleware

文件系统操作中间件。

```python
from deepagents.middleware import FilesystemMiddleware
from deepagents.backends import FilesystemBackend

middleware = FilesystemMiddleware(
    backend=FilesystemBackend(root_dir="/workspace")
)
```

#### 提供的工具

| 工具 | 说明 | 参数 |
|------|------|------|
| `read_file` | 读取文件 | `path: str`, `offset: int`, `limit: int` |
| `write_file` | 写入文件 | `path: str`, `content: str`, `overwrite: bool` |
| `edit_file` | 编辑文件 | `path: str`, `old_string: str`, `new_string: str` |
| `ls` | 列出目录 | `path: str`, `long_format: bool` |
| `glob` | 模式匹配 | `pattern: str` |
| `grep` | 文本搜索 | `pattern: str`, `path: str` |
| `execute` | 执行命令 | `command: str`, `timeout: int` |

### SkillsMiddleware

技能系统中间件（V2）。

```python
from deepagents.middleware.skills import SkillsMiddleware

middleware = SkillsMiddleware(
    backend=backend,
    sources=["/skills/user"],
    max_loaded_skills=10
)
```

#### V2 新增工具

| 工具 | 说明 | 参数 |
|------|------|------|
| `load_skill` | 加载技能 | `skill_name: str` |
| `unload_skill` | 卸载技能 | `skill_name: str` |

#### 技能元数据

```python
from deepagents.middleware.skills import SkillMetadata, ResourceMetadata

skill = SkillMetadata(
    name="web-research",
    description="Web research skill",
    path="/skills/web-research/SKILL.md",
    license="MIT",
    compatibility="Python 3.10+",
    allowed_tools=["web_search", "fetch_url"],
    metadata={}
)
```

### MemoryMiddleware

内存/上下文管理中间件。

```python
from deepagents.middleware import MemoryMiddleware

middleware = MemoryMiddleware(
    backend=backend,
    memory_path="/memories"
)
```

### SubAgentMiddleware

子代理中间件。

```python
from deepagents.middleware import SubAgentMiddleware

middleware = SubAgentMiddleware(
    subagents=[
        SubAgent(
            name="researcher",
            description="Research specialist",
            tools=[web_search]
        )
    ]
)
```

#### task 工具

| 工具 | 说明 | 参数 |
|------|------|------|
| `task` | 委托子代理 | `description: str`, `subagent_type: str` |

---

## 后端 API

### StateBackend

内存状态后端（默认）。

```python
from deepagents.backends import StateBackend

backend = StateBackend(runtime_context)
```

### FilesystemBackend

文件系统后端。

```python
from deepagents.backends import FilesystemBackend

backend = FilesystemBackend(
    root_dir="/workspace",
    virtual_mode=True
)
```

### StoreBackend

持久化存储后端。

```python
from deepagents.backends import StoreBackend

backend = StoreBackend(
    runtime_context,
    namespace=lambda ctx: f"user-{ctx['user_id']}"
)
```

### CompositeBackend

组合后端（路由到不同后端）。

```python
from deepagents.backends import CompositeBackend

backend = CompositeBackend(
    default=StateBackend(runtime),
    routes={
        "/memories/": StoreBackend(runtime),
        "/uploads/": FilesystemBackend(root_dir="/uploads")
    }
)
```

---

## Upload Adapter API

### upload_files

通用文件上传函数。

```python
from deepagents import upload_files

results = upload_files(
    backend=backend,
    files=[
        UploadSource(path="/local/file.txt", dest_path="/uploads/file.txt"),
        UploadSource(content=b"bytes", dest_path="/uploads/bytes.txt")
    ]
)
```

### UploadResult

上传结果类型。

```python
from deepagents import UploadResult

result = UploadResult(
    success=True,
    source_path="/local/file.txt",
    dest_path="/uploads/file.txt",
    strategy="direct",
    error=None
)
```

---

## Converter API

### 注册自定义转换器

```python
from deepagents.middleware.converters import register_converter, BaseConverter

class MyConverter(BaseConverter):
    def convert(self, content: bytes, filename: str) -> str:
        # 转换逻辑
        return converted_content

register_converter(".myext", MyConverter())
```

### 获取转换器

```python
from deepagents.middleware.converters import get_converter

converter = get_converter(".pdf")
result = converter.convert(file_bytes, "doc.pdf")
```

---

## 类型定义

### 主要类型

```python
from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    messages: List[BaseMessage]
    todos: List[Dict[str, Any]]
    skills_metadata: List[SkillMetadata]
    memory_contents: Dict[str, str]

class SkillMetadata(TypedDict):
    name: str
    description: str
    path: str
    license: Optional[str]
    compatibility: Optional[str]
    allowed_tools: List[str]
    metadata: Dict[str, str]

class ResourceMetadata(TypedDict):
    name: str
    path: str
    type: str  # "script", "reference", "asset"
```

---

## 配置参考

### 环境变量

```bash
# 必需
ANTHROPIC_API_KEY="your-key"
OPENAI_API_KEY="your-key"

# 可选
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_API_KEY="your-key"
DEEPAGENTS_DEFAULT_MODEL="claude-sonnet-4-5-20250929"
DEEPAGENTS_FALLBACK_TRIGGER_TOKENS="100000"
```

### 模型支持

| 提供商 | 模型 | 代码示例 |
|--------|------|----------|
| Anthropic | claude-sonnet-4-5 | `ChatAnthropic(model="claude-sonnet-4-5-20250929")` |
| OpenAI | gpt-4o | `ChatOpenAI(model="gpt-4o")` |
| DashScope | qwen-plus | `ChatOpenAI(model="qwen-plus", base_url="...")` |

---

## 错误处理

### 常见错误码

| 错误 | 说明 | 处理建议 |
|------|------|----------|
| `file_not_found` | 文件不存在 | 检查路径 |
| `permission_denied` | 权限不足 | 检查文件权限 |
| `is_directory` | 路径是目录 | 使用目录操作 |
| `invalid_path` | 无效路径 | 使用绝对路径 |

### 异常类型

```python
from deepagents.exceptions import (
    DeepAgentsError,
    FileNotFoundError,
    PermissionDeniedError,
    ValidationError
)

try:
    result = agent.invoke(...)
except FileNotFoundError as e:
    logger.error(f"File not found: {e.path}")
```

---

## 相关文档

- [部署指南](../deployment/DEPLOYMENT_GUIDE.md)
- [SDK 迁移指南](../SDK_MIGRATION_GUIDE_v0.4.0.md)
- [Upload Adapter 指南](../UPLOAD_ADAPTER_GUIDE.md)
