from langchain.tools import tool
import requests
from typing import Optional, Literal

from agentchat.settings import app_settings
from agentchat.tools.web_search.tavily_search.action import _tavily_search

# 定义 freshness 的合法值（提升类型安全性）
FreshnessType = Literal[
    "noLimit", "oneDay", "oneWeek", "oneMonth", "oneYear"
]


def _bocha_key_unavailable(api_key: Optional[str]) -> bool:
    normalized = (api_key or "").strip()
    return not normalized or "*" in normalized


def _fallback_to_tavily(query: str, count: int, freshness: FreshnessType) -> str:
    freshness_to_time_range = {
        "oneDay": "day",
        "oneWeek": "week",
        "oneMonth": "month",
        "oneYear": "year",
    }
    return _tavily_search(
        query=query,
        topic="general",
        max_results=min(max(count, 1), 10),
        time_range=freshness_to_time_range.get(freshness),
    )

@tool("bocha_search", parse_docstring=True)
def bocha_search(
    query: str,
    count: int = 10,
    freshness: FreshnessType = "noLimit",
    summary: bool = True,
    include: Optional[str] = None,
    exclude: Optional[str] = None
) -> str:
    """
    使用 Bocha Web Search API 进行网页搜索。

    Args:
        query (str): 用户的搜索词（必填）
        count (int): 返回结果条数，范围 1-50，默认 10
        freshness (str): 时间范围，默认 "noLimit" 可选: "noLimit", "oneDay", "oneWeek", "oneMonth", "oneYear" 也支持自定义日期格式如 "2025-01-01..2025-04-06" 或 "2025-04-06"
        summary (bool): 是否返回文本摘要，默认 False（与 API 默认一致）
        include (str, optional): 限定搜索的网站域名，多个用 | 或 , 分隔（≤100个）
        exclude (str, optional): 排除的网站域名，多个用 | 或 , 分隔（≤100个）

    Returns:
        str: 格式化的搜索结果或错误信息
    """
    bocha_api_key = app_settings.tools.bocha.get("api_key")
    if _bocha_key_unavailable(bocha_api_key):
        return _fallback_to_tavily(query, count, freshness)

    url = app_settings.tools.bocha.get("endpoint")
    headers = {
        'Authorization': f'Bearer {bocha_api_key}',
        'Content-Type': 'application/json'
    }
    # 构建请求体（只包含非 None 值）
    data = {
        "query": query,
        "count": min(max(count, 1), 50),  # 确保在 1-50 范围内
    }

    # 可选参数：仅当用户显式传入时才添加
    if freshness != "noLimit":
        data["freshness"] = freshness
    if summary:
        data["summary"] = True
    if include is not None:
        data["include"] = include
    if exclude is not None:
        data["exclude"] = exclude

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
    except requests.RequestException as err:
        try:
            return _fallback_to_tavily(query, count, freshness)
        except Exception:
            return f"搜索API请求失败，原因是：{str(err)}"

    if response.status_code in (401, 403):
        return _fallback_to_tavily(query, count, freshness)

    if response.status_code == 200:
        json_response = response.json()
        try:
            if json_response["code"] != 200 or not json_response["data"]:
                error_message = json_response.get("msg") or json_response.get("message") or "未知错误"
                if "auth" in error_message.lower() or "认证" in error_message or "鉴权" in error_message:
                    return _fallback_to_tavily(query, count, freshness)
                return f"搜索API请求失败，原因是: {error_message}"

            webpages = json_response["data"]["webPages"]["value"]
            if not webpages:
                return "未找到相关结果。"
            formatted_results = ""
            for idx, page in enumerate(webpages, start=1):
                formatted_results += (
                    f"引用: {idx}\n"
                    f"标题: {page.get('name', '')}\n"
                    f"URL: {page.get('url', '')}\n"
                    f"摘要: {page.get('summary', '')}\n"
                    f"网站名称: {page.get('siteName', '')}\n"
                    f"网站图标: {page.get('siteIcon', '')}\n"
                    f"发布时间: {page.get('dateLastCrawled', '')}\n\n"
                )
            return formatted_results.strip()
        except Exception as e:
            return f"搜索API请求失败，原因是：搜索结果解析失败 {str(e)}"
    else:
        return f"搜索API请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
