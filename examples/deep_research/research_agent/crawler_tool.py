"""Crawler Tool for Deep Agents.

提供网页爬取能力，通过调用外部 Crawler Service。
搜索功能使用现有的 web_search 工具。
"""

import os
import re
import httpx
from langchain_core.tools import tool

# Crawler Service 配置
CRAWLER_SERVICE_URL = os.getenv("CRAWLER_SERVICE_URL", "http://127.0.0.1:8084")

# 浏览器请求头，用于绕过反爬虫
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Cache-Control": "max-age=0",
}

# 备用抓取服务
FALLBACK_SERVICES = [
    "https://r.jina.ai/http://{url}",
    "https://r.jina.ai/{url}",
]


def clean_html_to_text(html: str) -> str:
    """将 HTML 转换为纯文本，保留基本结构。"""
    # 移除 script 和 style 标签及其内容
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除 HTML 注释
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    
    # 将常见块级标签转换为换行
    html = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    
    # 提取标题
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else None
    
    # 移除所有 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', html)
    
    # 解码 HTML 实体
    import html as html_module
    text = html_module.unescape(text)
    
    # 清理空白
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # 限制长度
    text = text.strip()[:10000]
    
    return title, text


def fetch_with_browser_headers(url: str, timeout: int = 30) -> dict:
    """使用浏览器请求头直接抓取网页。"""
    try:
        with httpx.Client(headers=BROWSER_HEADERS, follow_redirects=True, timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            
            title, text = clean_html_to_text(response.text)
            
            return {
                "success": True,
                "url": str(response.url),
                "title": title or "",
                "markdown": text,
                "crawl_time_ms": 0,
            }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


def fetch_with_jina_ai(url: str, timeout: int = 30) -> dict:
    """使用 jina.ai 的文本提取服务作为备选。"""
    try:
        # jina.ai 可以直接从 URL 提取文章内容
        jina_url = f"https://r.jina.ai/http://{url}"
        
        with httpx.Client(timeout=timeout) as client:
            response = client.get(jina_url)
            response.raise_for_status()
            
            content = response.text
            
            # jina.ai 返回格式: Title\n\nContent
            lines = content.split('\n', 1)
            title = lines[0].strip() if lines else ""
            text = lines[1].strip() if len(lines) > 1 else content
            
            return {
                "success": True,
                "url": url,
                "title": title,
                "markdown": text[:15000],  # 限制长度
                "crawl_time_ms": 0,
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"jina.ai fallback failed: {str(e)}",
            "url": url
        }


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
    # 首先尝试 crawler service
    result = crawl_webpage(url, timeout=30, extract_links=extract_links)
    
    # 如果失败（403/503 等），使用本地 fallback
    if not result.get("success"):
        error_msg = result.get("error", "Unknown error")
        
        # 第二级: 使用浏览器 headers 直接抓取
        if any(code in error_msg for code in ["403", "503", "429", "Connection", "Timeout"]):
            print(f"[fetch_webpage] Crawler service failed ({error_msg}), trying direct fetch with browser headers...")
            result = fetch_with_browser_headers(url, timeout=30)
            
            # 第三级: 使用 jina.ai 服务
            if not result.get("success"):
                print(f"[fetch_webpage] Direct fetch failed, trying jina.ai service...")
                result = fetch_with_jina_ai(url, timeout=30)
        
        if not result.get("success"):
            return f"❌ Failed to fetch webpage: {result.get('error', error_msg)}"
    
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
