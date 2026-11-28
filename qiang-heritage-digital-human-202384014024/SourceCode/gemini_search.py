# Qwen web-search adapter used by the retrieval fallback.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Qwen web-search adapter retaining the search_client interface."""
import http.client
import json
import logging
from typing import Optional, Dict, Any

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QwenSearchClient:
    """Alibaba Qwen web-search client."""

    def __init__(self, api_key: Optional[str] = None):
        """Resolve the API key, base URL, model name, and endpoint from configuration."""
        self.api_key = api_key or config.QWEN_API_KEY
        self.base_url = config.QWEN_BASE_URL
        self.model = config.SEARCH_MODEL
        self.endpoint = config.SEARCH_API_ENDPOINT

    def search(
        self,
        query: str,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request Qwen web-assisted generation and normalize the response into text and source fields."""
        # A single attempt is made; the retrieval engine treats any failure as "no web results".
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": query})

            payload = {
                "model": self.model,
                "input": {
                    "messages": messages
                },
                "parameters": {
                    # The web_search tool asks Qwen to ground its answer in live search results.
                    "tools": [
                        {
                            "type": "web_search",
                            "web_search": {"search_query": query}
                        }
                    ]
                }
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            conn = http.client.HTTPSConnection(self.base_url, timeout=60)
            conn.request("POST", self.endpoint, json.dumps(payload), headers)
            response = conn.getresponse()
            data = response.read().decode("utf-8")
            status = response.status
            conn.close()

            if status != 200:
                logger.error(f"通义联网搜索失败: {status} - {data[:500]}")
                return {"text": f"搜索失败（状态码: {status}）", "search_results": [], "sources": []}

            return self._parse_response(data)
        except Exception as e:
            logger.error(f"通义联网搜索异常: {e}")
            return {"text": f"搜索失败: {str(e)}", "search_results": [], "sources": []}

    def _parse_response(self, data: str) -> Dict[str, Any]:
        """Extract generated text and optional source lists from the Qwen response."""
        try:
            response_json = json.loads(data)
            output = response_json.get("output", {})
            text = output.get("text", "")
            return {
                "text": text,
                "search_results": output.get("search_results", []),
                "sources": output.get("sources", []),
            }
        except Exception as e:
            logger.error(f"解析通义响应失败: {e}")
            return {"text": "", "search_results": [], "sources": []}

    def search_and_answer(
        self,
        query: str,
        system_instruction: Optional[str] = None,
        include_sources: bool = True,
    ) -> str:
        """Return only generated search text; include_sources is retained for compatibility."""
        del include_sources
        system_prompt = system_instruction or "你是一位羌族非物质文化遗产专家，请根据搜索结果准确回答问题。"
        result = self.search(query, system_prompt)
        return result["text"]

    def get_weather(self, location: str) -> str:
        """Build a weather query for the requested location and return search text."""
        return self.search_and_answer(f"今天{location}天气如何?")

    def get_news(self, topic: Optional[str] = None) -> str:
        """Build a news query using the optional topic and return search text."""
        query = f"关于{topic}的最新新闻是什么?" if topic else "今天的最新新闻有哪些?"
        return self.search_and_answer(query)

    def get_information(self, question: str) -> str:
        """Answer a general information question through web-assisted search."""
        return self.search_and_answer(question)


search_client = QwenSearchClient()
