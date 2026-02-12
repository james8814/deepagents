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
# 沙盒后端配置（带自动重建的健壮实现）
# ============================================
from deepagents_cli.integrations.daytona import DaytonaProvider
from deepagents.backends.protocol import ExecuteResponse

class ResilientDaytonaBackend:
    """自动重建的 Daytona Backend 包装器。
    
    当底层 sandbox 停止或出错时自动创建新的 sandbox。
    使用 auto_stop_interval=60 1小时后自动停止。
    """
    
    def __init__(self):
        from daytona import Daytona, DaytonaConfig, CreateSandboxFromImageParams
        import os
        
        self._config = DaytonaConfig(api_key=os.getenv('DAYTONA_API_KEY'))
        self._client = Daytona(self._config)
        self._backend = None
        self._ensure_backend()
    
    def _create_sandbox(self):
        """创建新的 sandbox，设置永不自动停止。"""
        from daytona import CreateSandboxFromImageParams
        
        print(f"[Sandbox] Creating new Daytona sandbox (auto_stop_interval=60min)...")
        
        # 使用 CreateSandboxFromImageParams 创建长时间运行的 sandbox
        # auto_stop_interval=60 表示60分钟后自动停止（根据文档）
        params = CreateSandboxFromImageParams(
            image="daytonaio/sandbox:0.5.1",
            auto_stop_interval=60,  # 60 = 1小时后自动停止
            auto_archive_interval=10080,  # 7天后归档
            resources={"cpu": "1", "memory": "2", "disk": "10"}
        )
        
        sandbox = self._client.create(params=params, timeout=180)
        
        # 等待 sandbox 启动（使用忙循环避免阻塞）
        import time
        start_time = time.time()
        last_check = 0
        while time.time() - start_time < 180:
            # 每秒检查一次，不使用 sleep
            if time.time() - last_check >= 1:
                try:
                    result = sandbox.process.exec("echo ready", timeout=5)
                    if result.exit_code == 0:
                        break
                except:
                    pass
                last_check = time.time()
            # 忙等待，避免使用 sleep
        
        from deepagents_cli.integrations.daytona import DaytonaBackend
        return DaytonaBackend(sandbox)
    
    def _ensure_backend(self):
        """确保 backend 可用，如果不健康则重建。"""
        if self._backend is not None:
            try:
                result = self._backend.execute("echo health_check")
                if result.exit_code == 0:
                    return
            except Exception as e:
                print(f"[Sandbox] Health check failed: {e}")
        
        # 创建新的 sandbox
        self._backend = self._create_sandbox()
        print(f"[Sandbox] Created: {self._backend.id}")
    
    @property
    def id(self):
        self._ensure_backend()
        return self._backend.id
    
    def execute(self, command):
        self._ensure_backend()
        try:
            return self._backend.execute(command)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['unauthorized', 'no ip address', 'sandbox started', 'not found']):
                print(f"[Sandbox] Connection lost, recreating...")
                self._backend = None
                self._ensure_backend()
                return self._backend.execute(command)
            raise
    
    def read(self, file_path, offset=0, limit=2000):
        self._ensure_backend()
        try:
            return self._backend.read(file_path, offset, limit)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['unauthorized', 'no ip address', 'sandbox started', 'not found']):
                print(f"[Sandbox] Connection lost during read, recreating...")
                self._backend = None
                self._ensure_backend()
                return self._backend.read(file_path, offset, limit)
            raise
    
    def write(self, file_path, content):
        self._ensure_backend()
        try:
            return self._backend.write(file_path, content)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['unauthorized', 'no ip address', 'sandbox started', 'not found']):
                print(f"[Sandbox] Connection lost during write, recreating...")
                self._backend = None
                self._ensure_backend()
                return self._backend.write(file_path, content)
            raise
    
    def ls(self, path):
        self._ensure_backend()
        try:
            return self._backend.ls(path)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['unauthorized', 'no ip address', 'sandbox started', 'not found']):
                print(f"[Sandbox] Connection lost during ls, recreating...")
                self._backend = None
                self._ensure_backend()
                return self._backend.ls(path)
            raise
    
    # 异步方法 - 委托给底层 backend
    async def als_info(self, path: str):
        self._ensure_backend()
        try:
            return await self._backend.als_info(path)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['unauthorized', 'no ip address', 'sandbox started', 'not found']):
                print(f"[Sandbox] Connection lost, recreating...")
                self._backend = None
                self._ensure_backend()
                return await self._backend.als_info(path)
            raise
    
    async def aread(self, file_path, offset=0, limit=2000):
        self._ensure_backend()
        try:
            return await self._backend.aread(file_path, offset, limit)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['unauthorized', 'no ip address', 'sandbox started', 'not found']):
                print(f"[Sandbox] Connection lost during read, recreating...")
                self._backend = None
                self._ensure_backend()
                return await self._backend.aread(file_path, offset, limit)
            raise
    
    async def awrite(self, file_path, content):
        self._ensure_backend()
        try:
            return await self._backend.awrite(file_path, content)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['unauthorized', 'no ip address', 'sandbox started', 'not found']):
                print(f"[Sandbox] Connection lost during write, recreating...")
                self._backend = None
                self._ensure_backend()
                return await self._backend.awrite(file_path, content)
            raise
    
    async def aexecute(self, command):
        self._ensure_backend()
        try:
            return await self._backend.aexecute(command)
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['unauthorized', 'no ip address', 'sandbox started', 'not found']):
                print(f"[Sandbox] Connection lost, recreating...")
                self._backend = None
                self._ensure_backend()
                return await self._backend.aexecute(command)
            raise

# 延迟初始化 sandbox 后端（避免模块加载时创建，解决 Daytona 磁盘限制问题）
_sandbox_backend = None

def get_sandbox_backend():
    """延迟获取 sandbox 后端实例。"""
    global _sandbox_backend
    if _sandbox_backend is None:
        _sandbox_backend = ResilientDaytonaBackend()
        print(f"[AGENT MODULE] Sandbox initialized: {_sandbox_backend.id}", flush=True)
    return _sandbox_backend

# 为了兼容性，保留 sandbox_backend 引用（实际使用时会触发初始化）
class LazySandboxBackend:
    """延迟加载的 sandbox backend 代理类。"""
    
    @property
    def id(self):
        return get_sandbox_backend().id
    
    def execute(self, command):
        return get_sandbox_backend().execute(command)
    
    def read(self, file_path, offset=0, limit=2000):
        return get_sandbox_backend().read(file_path, offset, limit)
    
    def write(self, file_path, content):
        return get_sandbox_backend().write(file_path, content)
    
    def ls(self, path):
        return get_sandbox_backend().ls(path)
    
    async def als_info(self, path: str):
        return await get_sandbox_backend().als_info(path)
    
    async def aread(self, file_path, offset=0, limit=2000):
        return await get_sandbox_backend().aread(file_path, offset, limit)
    
    async def awrite(self, file_path, content):
        return await get_sandbox_backend().awrite(file_path, content)
    
    async def aexecute(self, command):
        return await get_sandbox_backend().aexecute(command)

sandbox_backend = LazySandboxBackend()
print("[AGENT MODULE] Loaded with lazy sandbox initialization", flush=True)

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
# 模型配置: 支持多提供商 (OpenAI / DashScope / DeepSeek)
# ============================================
def create_model():
    """根据环境变量创建对应的 LLM 模型实例。"""
    provider = os.getenv("MODEL_PROVIDER", "dashscope").lower()
    
    if provider == "deepseek":
        # DeepSeek 配置 (OpenAI 兼容 API)
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set in environment")
        model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")  # deepseek-chat 或 deepseek-reasoner
        print(f"[Model] Using DeepSeek: {model_name}")
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            temperature=0.0,
        )
    
    elif provider == "dashscope":
        # 通义千问 (DashScope) 配置
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY not set in environment")
        model_name = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
        print(f"[Model] Using DashScope: {model_name}")
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.0,
        )
    
    elif provider == "openai":
        # OpenAI 配置
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        model_name = os.getenv("OPENAI_MODEL", "gpt-4")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        print(f"[Model] Using OpenAI: {model_name}")
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0,
        )
    
    else:
        raise ValueError(f"Unknown MODEL_PROVIDER: {provider}. Supported: deepseek, dashscope, openai")

# 创建模型实例
model = create_model()

# Create the agent with sandbox backend
agent = create_deep_agent(
    model=model,
    tools=[web_search, think_tool, fetch_webpage],
    system_prompt=INSTRUCTIONS,
    subagents=[research_sub_agent],
    backend=sandbox_backend,  # 使用 Daytona 云端沙盒
)
