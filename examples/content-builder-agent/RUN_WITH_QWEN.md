# Content Builder Agent - 使用 Qwen 运行

## 快速开始

### 1. 设置 Qwen API Key

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，设置 DashScope API Key
# 或者直接用命令行设置
export DASHSCOPE_API_KEY="your-dashscope-api-key"
```

### 2. 运行 Agent

```bash
# 使用 run.sh 脚本 (推荐)
./run.sh "Write a blog post about AI agents"

# 或者直接运行
uv run python content_writer.py "Write a blog post about prompt engineering"
```

## 支持的 Qwen 模型

| 模型 | 说明 | 上下文 |
|------|------|--------|
| `qwen-plus` | 通义千问 Plus，性价比高 | 1M tokens |
| `qwen3-max` | Qwen3 旗舰，最强性能 | 256K tokens |
| `qwen3-vl-plus` | 多模态，支持图像输入 | 256K tokens |
| `qwen-turbo` | 快速响应 | 1M tokens |
| `qwen-long` | 超长上下文 | 10M tokens |

切换模型：
```bash
export DASHSCOPE_MODEL="qwen3-max"
./run.sh "Write a blog post about AI"
```

## 完整示例

```bash
# 设置 API Key
export DASHSCOPE_API_KEY="sk-xxxx"
export DASHSCOPE_MODEL="qwen-plus"

# 运行
./run.sh "写一篇关于 AI 代理如何改变软件开发的博客文章"
```

## 输出位置

- 博客文章：`blogs/<slug>/post.md`
- 封面图片：`blogs/<slug>/hero.png` (需要 GOOGLE_API_KEY)

## 注意事项

1. **图片生成** 需要 Google API Key (Gemini)
2. **Web 搜索** 需要 Tavily API Key (可选)
3. 国内用户建议使用 Qwen，国际用户建议使用 Claude
