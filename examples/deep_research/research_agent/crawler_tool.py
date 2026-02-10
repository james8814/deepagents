"""Crawler Tool for Deep Agents.

提供网页爬取能力，通过调用外部 Crawler Service。
搜索功能使用现有的 web_search 工具。
"""

import os
import httpx
from langchain_core.tools import tool

# Crawler Service 配置
CRAWLER_SERVICE_URL = os.getenv("CRAWLER_SERVICE_URL", "http://127.0.0.1:8084")


def crawl_webpage(
    url: str,
    timeout: int = 30,
    extract_links: bool = False
) -> dict:
    """调用爬虫服务爬取网页。
    
    Args:
        url: 要爬取的网页 URL
        timeout: 超时时间（秒）
        extract_links: 是否提取页面内链接
        
    Returns:
        爬取结果字典
    """
    try:
        response = httpx.post(
            f"{CRAWLER_SERVICE_URL}/crawl",
            json={
                "url": url,
                "timeout": timeout,
                "extract_links": extract_links
            },
            timeout=timeout + 10
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": f"爬取超时（{timeout}s）",
            "url": url
        }
    except httpx.ConnectError:
        return {
            "success": False,
            "error": f"无法连接爬虫服务（{CRAWLER_SERVICE_URL}），请检查服务是否运行",
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"爬取失败: {str(e)}",
            "url": url
        }


@tool
def fetch_webpage(url: str, extract_links: bool = False) -> str:
    """Fetch and extract content from a specific webpage URL.
    
    Use this tool when you have a specific URL and need its full content.
    This tool extracts the main article/content in clean Markdown format,
    filtering out ads, navigation, and other clutter.
    
    Args:
        url: The full URL to fetch (e.g., "https://example.com/article")
        extract_links: Whether to also extract all links from the page
    """
    result = crawl_webpage(url, timeout=30, extract_links=extract_links)
    
    if not result.get("success"):
        error_msg = result.get("error", "Unknown error")
        return f"❌ Failed to fetch webpage: {error_msg}"
    
    lines = []
    
    if result.get("title"):
        lines.append(f"# {result['title']}\n")
    
    lines.append(f"**Source:** {result.get('url', url)}\n")
    
    if result.get("crawl_time_ms"):
        lines.append(f"*Fetched in {result['crawl_time_ms']}ms*\n")
    
    lines.append("---\n")
    
    if result.get("markdown"):
        lines.append(result["markdown"])
    else:
        lines.append("*No content extracted*")
    
    if extract_links and result.get("links"):
        lines.append("\n---\n")
        lines.append("### Links found on this page:\n")
        for link in result["links"][:20]:
            lines.append(f"- {link}")
    
    return "\n".join(lines)


# 兼容别名
crawl_tool = fetch_webpage
