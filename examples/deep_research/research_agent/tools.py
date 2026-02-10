"""Research Tools.

This module provides search and content processing utilities for the research agent.
支持 Tavily 和 DuckDuckGo (免费) 两种搜索方式。
"""

import os
import httpx
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from typing_extensions import Annotated, Literal

# 尝试导入 Tavily (可选)
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

# 尝试导入 DuckDuckGo (免费)
try:
    from ddgs import DDGS
    DUCKDUCKGO_AVAILABLE = True
except ImportError:
    DUCKDUCKGO_AVAILABLE = False


def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch and convert webpage content to markdown.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Webpage content as markdown
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return markdownify(response.text)
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


def duckduckgo_search(query: str, max_results: int = 5) -> list:
    """使用 DuckDuckGo 免费搜索 (无需 API Key).
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数
        
    Returns:
        搜索结果列表
    """
    if not DUCKDUCKGO_AVAILABLE:
        raise ImportError("DuckDuckGo search not available. Install: pip install ddgs")
    
    results = []
    with DDGS() as ddgs:
        for result in ddgs.text(query, max_results=max_results):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "content": result.get("body", ""),
            })
    return results


def tavily_search_impl(query: str, max_results: int = 5, topic: str = "general") -> list:
    """使用 Tavily 搜索 (需要 API Key).
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数
        topic: 主题过滤
        
    Returns:
        搜索结果列表
    """
    if not TAVILY_AVAILABLE:
        raise ImportError("Tavily not available. Install: pip install tavily-python")
    
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or api_key == "your_tavily_api_key_here":
        raise ValueError("TAVILY_API_KEY not configured")
    
    client = TavilyClient(api_key=api_key)
    search_results = client.search(query, max_results=max_results, topic=topic)
    
    results = []
    for result in search_results.get("results", []):
        results.append({
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get("content", ""),
        })
    return results


@tool(parse_docstring=True)
def web_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 3,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Search the web for information on a given query.

    Uses DuckDuckGo (free, no API key required) or Tavily (if configured) to discover relevant URLs,
    then fetches and returns full webpage content as markdown.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 3)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')

    Returns:
        Formatted search results with full webpage content
    """
    # 优先尝试 DuckDuckGo (免费，无需 API Key)
    try:
        search_results = duckduckgo_search(query, max_results=max_results)
        search_engine = "DuckDuckGo"
    except Exception as e:
        # 如果 DuckDuckGo 失败，尝试 Tavily
        try:
            search_results = tavily_search_impl(query, max_results=max_results, topic=topic)
            search_engine = "Tavily"
        except Exception:
            return f"❌ Search failed. DuckDuckGo error: {e}. Please check your internet connection or configure TAVILY_API_KEY."

    if not search_results:
        return f"🔍 No results found for '{query}'"

    # Fetch full content for each URL
    result_texts = []
    for result in search_results:
        url = result["url"]
        title = result["title"]

        # Fetch webpage content
        content = fetch_webpage_content(url)

        result_text = f"""## {title}
**URL:** {url}

{content}

---
"""
        result_texts.append(result_text)

    # Format final response
    response = f"""🔍 Found {len(result_texts)} result(s) for '{query}' (via {search_engine}):

{chr(10).join(result_texts)}"""

    return response


# 为了兼容性，保留 tavily_search 别名
tavily_search = web_search


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"
