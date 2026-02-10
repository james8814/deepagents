#!/usr/bin/env python3
"""Deep Research Agent - 一键启动"""

import os
import sys

# 自动设置环境变量
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["DASHSCOPE_API_KEY"] = os.environ.get("DASHSCOPE_API_KEY", "your_dashscope_api_key_here")

print("=" * 60)
print("🚀 Deep Research Agent")
print("=" * 60)
print("🤖 模型: Qwen (通义千问)")
print("🔍 搜索: DuckDuckGo (免费)")
print("=" * 60)
print()

# 加载 Agent
print("⏳ 加载中...")
from agent import agent
print("✅ 准备就绪！\n")

# 交互式循环
while True:
    try:
        query = input("🔍 输入研究问题 (或输入 exit 退出): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n👋 再见!")
        break
    
    if not query or query.lower() in ['exit', 'quit', '退出']:
        print("👋 再见!")
        break
    
    print("\n⏳ 研究中...\n")
    
    try:
        result = agent.invoke({
            "messages": [{"role": "user", "content": query}]
        })
        
        # 输出结果
        if isinstance(result, dict) and "messages" in result:
            content = result["messages"][-1].content
            print(content)
        else:
            print(result)
            
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    print("\n" + "-" * 60 + "\n")
