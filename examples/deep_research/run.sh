#!/bin/bash
# Deep Research Agent 启动脚本
# 使用 Qwen + DuckDuckGo (免费方案)

cd /root/projects/deepagents/examples/deep_research
source venv/bin/activate

export LANGCHAIN_TRACING_V2=false
export DASHSCOPE_API_KEY="${DASHSCOPE_API_KEY:-your_dashscope_api_key_here}"

echo "🚀 启动 Deep Research Agent"
echo "==========================="
echo "🤖 模型: Qwen (通义千问)"
echo "🔍 搜索: DuckDuckGo (免费)"
echo "==========================="
echo ""

python3 << 'PYEOF'
import os
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from agent import agent

print("✅ Agent 已就绪！")
print()
print("使用示例:")
print("  result = agent.invoke({")
print("      'messages': [{'role': 'user', 'content': '研究量子计算'}]")
print("  })")
print()

# 简单测试
result = agent.invoke({
    "messages": [{"role": "user", "content": "搜索 Python 编程语言介绍"}]
})

print("📊 测试结果:")
if isinstance(result, dict) and "messages" in result:
    content = result["messages"][-1].content
    print(content[:500] if len(content) > 500 else content)
else:
    print(result)
PYEOF
