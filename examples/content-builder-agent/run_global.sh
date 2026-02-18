#!/usr/bin/env bash
# Content Builder Agent - 快速运行脚本
# 使用全局 Python 环境，避免 venv 问题

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "Content Builder Agent (使用全局 Python 环境)"
echo "========================================================================"
echo ""

# 加载 .env 文件 (如果存在)
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

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
    exit 1
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

# 使用全局 Python 环境运行
echo "使用全局 Python 环境运行..."
python3 content_writer.py "$TASK"
