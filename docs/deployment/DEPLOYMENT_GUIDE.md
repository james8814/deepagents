# DeepAgents 部署指南

**版本**: 0.4.4
**日期**: 2026-03-03
**适用**: 生产环境部署

---

## 快速开始

```bash
# 安装 DeepAgents
pip install deepagents

# 或使用 uv
uv add deepagents

# 安装带文件格式支持（推荐）
pip install "deepagents[converters]"
```

---

## 部署方案

### 方案 1: 本地开发部署

**适用场景**: 本地开发、测试

```python
from deepagents import create_deep_agent

# 基础配置
agent = create_deep_agent()

# 带自定义模型
from langchain_anthropic import ChatAnthropic

agent = create_deep_agent(
    model=ChatAnthropic(model="claude-sonnet-4-5-20250929")
)
```

### 方案 2: Docker 部署

**适用场景**: 容器化环境、CI/CD

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 DeepAgents
RUN pip install "deepagents[converters]"

# 复制应用代码
COPY . .

# 运行
CMD ["python", "agent.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  deepagent:
    build: .
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./skills:/app/skills
    ports:
      - "8000:8000"
```

### 方案 3: LangSmith 部署

**适用场景**: 生产环境、需要监控和追踪

```python
import os
from deepagents import create_deep_agent

# 配置 LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-langsmith-api-key"
os.environ["LANGCHAIN_PROJECT"] = "deepagents-production"

# 创建 Agent
agent = create_deep_agent()

# 部署为服务
from langserve import add_routes
from fastapi import FastAPI

app = FastAPI()
add_routes(app, agent, path="/agent")
```

### 方案 4: 云端沙盒部署

**适用场景**: 需要隔离执行环境

#### Modal

```python
import modal
from deepagents import create_deep_agent

app = modal.App("deepagents")

@app.function(
    image=modal.Image.debian_slim().pip_install("deepagents[converters]")
)
def run_agent(task: str):
    agent = create_deep_agent()
    return agent.invoke({"messages": [{"role": "user", "content": task}]})
```

#### Runloop

```python
from langchain_runloop import RunloopSandbox
from deepagents import create_deep_agent

sandbox = RunloopSandbox(devbox=devbox)
agent = create_deep_agent(backend=sandbox)
```

#### Daytona

```python
from langchain_daytona import DaytonaSandbox
from deepagents import create_deep_agent

sandbox = DaytonaSandbox(workspace_id="your-workspace")
agent = create_deep_agent(backend=sandbox)
```

---

## 环境配置

### 必需环境变量

```bash
# LLM Provider（至少配置一个）
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export OPENAI_API_KEY="your-openai-api-key"

# 或使用 DashScope (Qwen)
export DASHSCOPE_API_KEY="your-dashscope-api-key"
```

### 可选环境变量

```bash
# LangSmith 追踪（推荐用于生产）
export LANGCHAIN_TRACING_V2="true"
export LANGCHAIN_API_KEY="your-langsmith-api-key"
export LANGCHAIN_PROJECT="deepagents"

# 模型配置
export DEEPAGENTS_DEFAULT_MODEL="claude-sonnet-4-5-20250929"
export DEEPAGENTS_FALLBACK_TRIGGER_TOKENS="100000"

# 文件上传配置
export DEEPAGENTS_UPLOAD_MAX_SIZE="104857600"  # 100MB
```

---

## 配置文件示例

### config.yaml

```yaml
# DeepAgents 配置
model:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  temperature: 0.7

backend:
  type: filesystem
  root_dir: /workspace

skills:
  sources:
    - /skills/user
    - /skills/system
  max_loaded: 10

memory:
  type: store
  namespace: default

summarization:
  trigger_tokens: 100000
  keep_messages: 6

logging:
  level: INFO
  format: json
```

---

## 生产环境最佳实践

### 1. 安全性

- ✅ 使用环境变量管理 API Key
- ✅ 启用虚拟模式隔离文件系统
- ✅ 配置沙盒后端隔离执行
- ✅ 使用 HTTPS 传输数据

### 2. 性能优化

- ✅ 启用提示缓存（Anthropic 模型）
- ✅ 配置自动摘要防止上下文溢出
- ✅ 使用分页读取大文件
- ✅ 配置适当的超时时间

### 3. 监控

- ✅ 启用 LangSmith 追踪
- ✅ 配置日志收集
- ✅ 监控 Token 使用量
- ✅ 设置告警阈值

### 4. 备份

- ✅ 定期备份技能文件
- ✅ 备份 Store 持久化数据
- ✅ 版本控制配置文件

---

## 故障排除

### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| API Key 错误 | 环境变量未设置 | 检查 `ANTHROPIC_API_KEY` |
| 文件读取失败 | 路径问题 | 使用绝对路径或检查 `root_dir` |
| 上下文溢出 | 对话过长 | 启用自动摘要或限制消息数 |
| 工具调用失败 | 权限问题 | 检查文件系统权限或沙盒配置 |

---

## 相关文档

- [API 文档](./API_REFERENCE.md)
- [SDK 迁移指南](../SDK_MIGRATION_GUIDE_v0.4.0.md)
- [Upload Adapter 指南](../UPLOAD_ADAPTER_GUIDE.md)
- [沙盒生命周期管理](../sandbox-lifecycle-management.md)
