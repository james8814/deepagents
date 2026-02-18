#!/usr/bin/env bash
# Content Builder Agent - 运行脚本
# 用法：./run.sh "Write a blog post about AI agents"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 加载 .env 文件 (如果存在)
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo "✓ 已加载 .env 文件"
fi

# 设置 uv 环境变量，避免跨文件系统问题
export UV_LINK_MODE=copy

echo "========================================================================"
echo "Content Builder Agent"
echo "========================================================================"
echo ""

# 检测模型配置
if [ -n "$DASHSCOPE_API_KEY" ]; then
    echo "🤖 模型：Qwen (通义千问) - ${DASHSCOPE_MODEL:-qwen-plus}"
    export MODEL_PROVIDER="dashscope"
elif [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "🤖 模型：Claude - ${ANTHROPIC_MODEL:-claude-sonnet-4-5-20250929}"
elif [ -n "$OPENAI_API_KEY" ]; then
    echo "🤖 模型：OpenAI - ${OPENAI_MODEL:-gpt-5.2}"
else
    echo "❌ 错误：未设置任何模型的 API Key"
    echo ""
    echo "请设置以下至少一个环境变量:"
    echo "  DASHSCOPE_API_KEY  - 通义千问/Qwen (推荐国内用户)"
    echo "  ANTHROPIC_API_KEY  - Claude (推荐国际用户)"
    echo "  OPENAI_API_KEY     - OpenAI GPT"
    echo ""
    echo "你可以:"
    echo "  1. 直接设置：export DASHSCOPE_API_KEY=your_key"
    echo "  2. 或编辑 .env 文件 (参考 .env.example)"
    exit 1
fi

# 检查可选的 API Keys
if [ -n "$GOOGLE_API_KEY" ]; then
    echo "🖼️  图片生成：已启用 (Google Gemini)"
else
    echo "⚠️  图片生成：未启用 (需要 GOOGLE_API_KEY)"
fi

if [ -n "$TAVILY_API_KEY" ]; then
    echo "🔍 Web 搜索：已启用 (Tavily)"
else
    echo "⚠️  Web 搜索：未启用 (可选，需要 TAVILY_API_KEY)"
fi

echo ""

# 获取用户输入
if [ -n "$1" ]; then
    TASK="$*"
else
    echo "请输入任务描述 (例如：Write a blog post about AI agents)"
    read -r TASK
    if [ -z "$TASK" ]; then
        echo "❌ 错误：未输入任务"
        exit 1
    fi
fi

echo "任务：$TASK"
echo ""

# 选择运行方式
if command -v uv &> /dev/null; then
    echo "使用 uv 运行..."
    uv run --no-cache python content_writer.py "$TASK"
elif command -v python3 &> /dev/null; then
    echo "使用 python3 运行..."
    python3 content_writer.py "$TASK"
else
    echo "❌ 错误：找不到 uv 或 python3"
    exit 1
fi
