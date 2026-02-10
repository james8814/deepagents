"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.
"""

import os
from datetime import datetime

from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent

from research_agent.prompts import (
    RESEARCHER_INSTRUCTIONS,
    RESEARCH_WORKFLOW_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)
from research_agent.tools import web_search, think_tool
from research_agent.crawler_tool import fetch_webpage

# ============================================
# 沙盒后端配置
# ============================================
# 使用 Daytona 云端沙盒（完全隔离的容器环境）
from deepagents_cli.integrations.daytona import DaytonaProvider

# 创建 Daytona 沙盒后端
provider = DaytonaProvider()
sandbox_backend = provider.get_or_create()
print(f"[Sandbox] Created Daytona sandbox: {sandbox_backend.id}")

# Limits
max_concurrent_research_units = 3
max_researcher_iterations = 3

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")

# Combine orchestrator instructions (RESEARCHER_INSTRUCTIONS only for sub-agents)
INSTRUCTIONS = (
    RESEARCH_WORKFLOW_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
        max_concurrent_research_units=max_concurrent_research_units,
        max_researcher_iterations=max_researcher_iterations,
    )
)

# Create research sub-agent
research_sub_agent = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
    "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
    "tools": [web_search, think_tool, fetch_webpage],
}

# ============================================
# 模型配置: 使用 Qwen (通义千问)
# ============================================
# 从环境变量读取 DashScope API Key
model = ChatOpenAI(
    model="qwen-max",  # 可选: qwen-max, qwen-plus, qwen-turbo
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0.0,
)

# Create the agent with sandbox backend
agent = create_deep_agent(
    model=model,
    tools=[web_search, think_tool, fetch_webpage],
    system_prompt=INSTRUCTIONS,
    subagents=[research_sub_agent],
    backend=sandbox_backend,  # 使用 Daytona 云端沙盒
)
