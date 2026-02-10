#!/bin/bash
# 一键启动 Deep Research Agent

cd /root/projects/deepagents/examples/deep_research
source venv/bin/activate

export LANGCHAIN_TRACING_V2=false
export DASHSCOPE_API_KEY="${DASHSCOPE_API_KEY:-your_dashscope_api_key_here}"

python3 start.py
