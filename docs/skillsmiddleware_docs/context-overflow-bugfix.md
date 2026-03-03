# Context Overflow Bug 分析与修复方案

## 错误现象

```
BadRequestError: Error code: 400
This model's maximum context length is 131072 tokens.
However, you requested 149429 tokens (149429 in the messages, 0 in the completion).
```

**关键数据**：
- 模型上下文限制：131,072 tokens (128K)
- 实际请求 tokens：149,429 (超出 ~18K)
- completion tokens：0（已无空间生成回复）

---

## 根因分析

### 直接原因：SummarizationMiddleware 的 fallback 阈值高于模型实际上下文限制

`agent.py` 中使用 `ChatOpenAI` + 自定义 `base_url` 接入 DeepSeek/DashScope 模型：

```python
# agent.py:291
return ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    ...
)
```

LangChain 的 `ChatOpenAI` 只为 OpenAI 官方模型（gpt-4, gpt-4o 等）自动注入 profile。`"deepseek-chat"` 不在注册表中，导致 `model.profile` 缺少 `max_input_tokens`。

### 触发链路

```
agent.py: ChatOpenAI(model="deepseek-chat")
    → model.profile = {} (无 max_input_tokens)
    ↓
graph.py:150: _compute_summarization_defaults(model)
    ↓
summarization.py:104-109: has_profile = False (无 max_input_tokens)
    ↓
summarization.py:120-127 (fallback):
    trigger = ("tokens", 170000)   ← 170K 才触发摘要！
```

**致命不匹配**：

| 参数 | 值 | 说明 |
|------|-----|------|
| DeepSeek 实际上下文 | 131,072 tokens | 模型硬限制 |
| Summarization 触发阈值 | 170,000 tokens | fallback 默认值 |
| 实际请求大小 | 149,429 tokens | 已超出模型限制 |
| 摘要是否触发 | **否** | 149,429 < 170,000 |

**结论**：摘要中间件永远不会在上下文溢出之前触发。fallback 阈值（170K）比模型实际限制（131K）高 ~39K tokens。

### 受影响的模型

所有通过 `ChatOpenAI` + 自定义 `base_url` 接入的非 OpenAI 模型：

- **DeepSeek** (`deepseek-chat`, `deepseek-reasoner`)
- **通义千问/DashScope** (`qwen3-max`, `qwen3-vl-plus`, `qwen-plus`, `qwen-turbo`, `qwen-long`)
- 任何第三方 OpenAI 兼容 API

### 加剧因素

1. **搜索工具返回全文**：`web_search` 每次返回完整网页 markdown（2-5K tokens/次）
2. **子代理结果累积**：最多 3 个并行子代理 x 5 次搜索 = ~75K tokens
3. **系统提示 + 工具 schema 开销**：固定占用大量 tokens
4. **未设置 `max_tokens`**：`ChatOpenAI` 未指定输出 token 限制，没有为 completion 预留空间

---

## 修复方案：Model Profile 注册表（推荐）

### 设计思路

建立一个 **数据驱动的 profile 注册表**，将各第三方模型的上下文参数集中管理。切换模型时自动匹配对应 profile，无需硬编码分散在各处。

### LangChain Profile 机制说明

LangChain 的 `model.profile` 是一个 `ModelProfile` TypedDict（所有字段可选），存储在 Pydantic Field 中：

```python
# langchain_core/language_models/chat_models.py
profile: ModelProfile | None = Field(default=None, exclude=True)
```

- `ChatOpenAI` 初始化时通过 `_set_model_profile()` 验证器自动加载已知模型的 profile
- 未知模型（如 `deepseek-chat`）得到空 dict `{}`，缺少关键字段
- **可安全赋值** `model.profile = {...}`（deepagents 测试套件中已有此模式）

### 各模型实际参数

| 模型名 | Provider | max_input_tokens | max_output_tokens | 备注 |
|--------|----------|-----------------|-------------------|------|
| `deepseek-chat` | DeepSeek | 128,000 | 8,192 | DeepSeek-V3，默认 output 4096 |
| `deepseek-reasoner` | DeepSeek | 128,000 | 65,536 | DeepSeek-R1，含 CoT 推理 tokens |
| `qwen3-max` | DashScope | 258,048 | 65,536 | Qwen3 旗舰，256K 上下文 |
| `qwen3-vl-plus` | DashScope | 262,144 | 32,768 | Qwen3 多模态，支持图像/视频输入 |
| `qwen-plus` | DashScope | 997,952 | 32,768 | 1M 上下文 |
| `qwen-turbo` | DashScope | 1,000,000 | 16,384 | 1M 上下文，正在被 qwen-flash 取代 |
| `qwen-long` | DashScope | 10,000,000 | 8,192 | 10M 超长上下文 |
| `gpt-4` | OpenAI | 8,192 | 8,192 | LangChain 已内置 profile |
| `gpt-4o` | OpenAI | 128,000 | 16,384 | LangChain 已内置 profile |
| `gpt-4o-mini` | OpenAI | 128,000 | 16,384 | LangChain 已内置 profile |

### 实现代码

**修改文件**：`examples/deep_research/agent.py`

#### Step 1：在文件顶部定义 profile 注册表

```python
# ============================================
# 第三方模型 Profile 注册表
# LangChain 仅内置 OpenAI 官方模型的 profile，
# 第三方模型需手动补充以确保 SummarizationMiddleware 正确计算上下文阈值。
# ============================================
MODEL_PROFILES: dict[str, dict[str, object]] = {
    # DeepSeek
    "deepseek-chat": {
        "max_input_tokens": 128_000,
        "max_output_tokens": 8_192,
        "tool_calling": True,
        "structured_output": True,
    },
    "deepseek-reasoner": {
        "max_input_tokens": 128_000,
        "max_output_tokens": 65_536,
        "tool_calling": True,
        "reasoning_output": True,
    },
    # DashScope / 通义千问 (Qwen3)
    "qwen3-max": {
        "max_input_tokens": 258_048,
        "max_output_tokens": 65_536,
        "tool_calling": True,
        "structured_output": True,
    },
    "qwen3-vl-plus": {
        "max_input_tokens": 262_144,
        "max_output_tokens": 32_768,
        "tool_calling": True,
        "image_inputs": True,
    },
    "qwen-plus": {
        "max_input_tokens": 997_952,
        "max_output_tokens": 32_768,
        "tool_calling": True,
    },
    "qwen-turbo": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 16_384,
        "tool_calling": True,
    },
    "qwen-long": {
        "max_input_tokens": 10_000_000,
        "max_output_tokens": 8_192,
        "tool_calling": True,
    },
}


def _ensure_model_profile(model: ChatOpenAI, model_name: str) -> None:
    """确保模型具有正确的 profile（含 max_input_tokens）。

    如果 LangChain 已为该模型自动加载了包含 max_input_tokens 的 profile，
    则不覆盖。否则从 MODEL_PROFILES 注册表中查找并注入。

    Args:
        model: ChatOpenAI 模型实例。
        model_name: 模型名称，用于在注册表中查找。
    """
    # 检查是否已有有效 profile
    if (
        model.profile
        and isinstance(model.profile, dict)
        and isinstance(model.profile.get("max_input_tokens"), int)
    ):
        return

    profile = MODEL_PROFILES.get(model_name)
    if profile:
        model.profile = profile.copy()
        print(f"[Model] Injected profile for {model_name}: "
              f"max_input={profile['max_input_tokens']:,} tokens")
```

#### Step 2：在 `create_model()` 每个分支的 return 前调用

```python
def create_model():
    """根据环境变量创建对应的 LLM 模型实例。"""
    provider = os.getenv("MODEL_PROVIDER", "dashscope").lower()

    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set in environment")
        model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        print(f"[Model] Using DeepSeek: {model_name}")
        model = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            temperature=0.0,
        )
        _ensure_model_profile(model, model_name)  # ← 注入 profile
        return model

    elif provider == "dashscope":
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY not set in environment")
        model_name = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
        print(f"[Model] Using DashScope: {model_name}")
        model = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.0,
        )
        _ensure_model_profile(model, model_name)  # ← 注入 profile
        return model

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        model_name = os.getenv("OPENAI_MODEL", "gpt-4")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        print(f"[Model] Using OpenAI: {model_name}")
        model = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0,
        )
        _ensure_model_profile(model, model_name)  # ← 兜底：非官方 OpenAI 模型也能覆盖
        return model

    else:
        raise ValueError(
            f"Unknown MODEL_PROVIDER: {provider}. "
            "Supported: deepseek, dashscope, openai"
        )
```

### 修复效果

注入 profile 后，`_compute_summarization_defaults()` 的执行路径变化：

```
修复前:
  model.profile = {}  →  has_profile = False
  → trigger = ("tokens", 170000)    ← 超过 DeepSeek 的 128K！

修复后:
  model.profile = {"max_input_tokens": 128000, ...}  →  has_profile = True
  → trigger = ("fraction", 0.85)
  → 实际阈值 = 128000 × 0.85 = 108,800 tokens  ← 安全
  → keep = ("fraction", 0.10)
  → 保留 = 128000 × 0.10 = 12,800 tokens
```

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 摘要触发点 | 170,000 (永远不触发) | 108,800 (安全阈值) |
| 上下文保留 | 最后 6 条消息 | 最后 ~12,800 tokens |
| 参数截断触发 | 20 条消息 | 108,800 tokens (85%) |
| 溢出风险 | **高** | **极低** |

### 设计优势

1. **数据驱动**：新增模型只需在 `MODEL_PROFILES` 字典中加一行，无需改逻辑
2. **不覆盖已有**：`_ensure_model_profile()` 先检查 LangChain 是否已注入有效 profile
3. **集中管理**：所有第三方模型参数在同一处维护，便于更新
4. **环境变量切换**：改 `MODEL_PROVIDER` + `DEEPSEEK_MODEL` 即可切换模型和 profile
5. **可扩展**：后续新增 provider（如 Moonshot、智谱等）只需添加 profile 条目

---

## 辅助措施：限制工具返回内容大小

减少每次搜索返回的内容量，从源头控制 token 增长速度。

**修改文件**：`examples/deep_research/research_agent/tools.py`

```python
MAX_CONTENT_CHARS = 3000  # 约 750 tokens

# 在 web_search 和 fetch_webpage 返回前截断
content = content[:MAX_CONTENT_CHARS]
if len(original_content) > MAX_CONTENT_CHARS:
    content += "\n\n...(content truncated)"
```

---

## 实施优先级

| 优先级 | 改动 | 效果 | 工作量 |
|--------|------|------|--------|
| **P0** | 添加 `MODEL_PROFILES` + `_ensure_model_profile()` | 根本修复：SummarizationMiddleware 正确感知上下文限制 | ~50 行 |
| **P1** | 限制工具返回内容大小 | 辅助：减缓 token 增长，延长可持续对话轮次 | ~5 行 |

---

## 验证方法

### 1. 验证 profile 注入是否生效

```python
model = create_model()
print(f"Profile: {model.profile}")
print(f"max_input_tokens: {model.profile.get('max_input_tokens')}")

from deepagents.middleware.summarization import _compute_summarization_defaults
defaults = _compute_summarization_defaults(model)
print(f"Summarization trigger: {defaults['trigger']}")
# 期望: ('fraction', 0.85) 而非 ('tokens', 170000)
```

### 2. 验证各模型切换

```bash
# 测试 DeepSeek
MODEL_PROVIDER=deepseek DEEPSEEK_MODEL=deepseek-chat langgraph dev
# 期望日志: [Model] Injected profile for deepseek-chat: max_input=128,000 tokens

# 测试 DashScope
MODEL_PROVIDER=dashscope DASHSCOPE_MODEL=qwen-plus langgraph dev
# 期望日志: [Model] Injected profile for qwen-plus: max_input=997,952 tokens

# 测试 DashScope (Qwen3)
MODEL_PROVIDER=dashscope DASHSCOPE_MODEL=qwen3-max langgraph dev
# 期望日志: [Model] Injected profile for qwen3-max: max_input=258,048 tokens

# 测试 OpenAI (已内置 profile，不应覆盖)
MODEL_PROVIDER=openai OPENAI_MODEL=gpt-4o langgraph dev
# 期望: 无 "Injected profile" 日志 (LangChain 自带 profile)
```

### 3. 长对话压力测试

使用连续搜索任务测试摘要是否正确触发：

```
用户: "详细调研 2026 年全球人工智能监管政策的最新进展"
```

观察 LangGraph Studio 中：
- token 使用曲线是否在 ~85% 上下文时出现下降（摘要触发）
- 是否不再出现 400 错误

---

## SDK 层面长期改进建议（仅记录，不修改 SDK 代码）

### 1. fallback 阈值应更保守

```python
# summarization.py:120-127 当前值
"trigger": ("tokens", 170000)   # 对 128K 模型危险

# 建议改为
"trigger": ("tokens", 100000)   # 更安全的通用默认值
```

### 2. 无 profile 时应打印警告

```python
if not has_profile:
    logger.warning(
        "Model profile not found (no max_input_tokens). "
        "Using fallback trigger of 170K tokens. "
        "Set model.profile manually if your model has a smaller context window."
    )
```

### 3. `create_deep_agent()` 应支持传入 summarization 参数

```python
create_deep_agent(
    ...,
    summarization_trigger=("tokens", 110000),
    summarization_keep=("messages", 6),
)
```

---

## 附录：错误调用栈解析

```
useChat.ts:59                    ← deep-agents-ui 前端 (独立仓库)
ChatInterface.tsx:96/107         ← 聊天界面组件
stream.lgp.tsx:405               ← LangGraph Platform 流式调用
manager.ts:245 (StreamManager)   ← 流管理器抛出 400 错误
```

前端调用栈来自 `deep-agents-ui`（独立 React 项目），通过 LangGraph Platform API 连接后端。错误实际发生在后端模型调用时，前端只是转发了 API 的 400 响应。

---

*文档创建时间：2026-02-12*
*涉及文件：`examples/deep_research/agent.py`, `libs/deepagents/deepagents/middleware/summarization.py`, `libs/deepagents/deepagents/graph.py`*
