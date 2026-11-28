#!/usr/bin/env python3
# Manual provider diagnostics; running this file can make external API calls.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Diagnostic script that displays detailed responses from the configured AI providers."""
import http.client
import json
from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    ZHIPU_API_KEY,
    ZHIPU_BASE_URL,
    EMBEDDING_MODEL,
    EMBEDDING_API_ENDPOINT,
    QWEN_API_KEY,
    QWEN_BASE_URL,
    SEARCH_MODEL,
    SEARCH_API_ENDPOINT,
)


def debug_chat_api():
    """Inspect the DeepSeek chat API response."""
    print("=" * 60)
    print("调试 DeepSeek 对话 API")
    print("=" * 60)

    conn = http.client.HTTPSConnection(DEEPSEEK_BASE_URL)
    payload = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": "你好"}],
        "stream": False,
    })
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json',
    }

    print(f"请求端点: /v1/chat/completions")
    print(f"请求体: {payload}")

    conn.request("POST", "/v1/chat/completions", payload, headers)
    res = conn.getresponse()
    data = res.read().decode("utf-8")
    # Provider responses are printed verbatim so error details stay visible during debugging.
    print(f"\n响应状态码: {res.status}")
    print(f"响应头: {res.getheaders()}")
    print("\n完整响应内容:")
    print(data)
    print()
    conn.close()


def debug_embedding_api():
    """Inspect the Zhipu embedding API response."""
    print("=" * 60)
    print("调试智谱 Embedding API")
    print("=" * 60)

    conn = http.client.HTTPSConnection(ZHIPU_BASE_URL)
    payload = json.dumps({
        "model": EMBEDDING_MODEL,
        "input": "测试文本",
    })
    headers = {
        'Authorization': f'Bearer {ZHIPU_API_KEY}',
        'Content-Type': 'application/json',
    }

    print(f"请求端点: {EMBEDDING_API_ENDPOINT}")
    print(f"请求体: {payload}")

    conn.request("POST", EMBEDDING_API_ENDPOINT, payload, headers)
    res = conn.getresponse()
    data = res.read().decode("utf-8")
    print(f"\n响应状态码: {res.status}")
    print(f"响应头: {res.getheaders()}")
    print("\n完整响应内容:")
    print(data)
    print()
    conn.close()


def debug_search_api():
    """Inspect the Qwen web-search API response."""
    print("=" * 60)
    print("调试阿里通义联网搜索 API")
    print("=" * 60)

    conn = http.client.HTTPSConnection(QWEN_BASE_URL)
    payload = json.dumps({
        "model": SEARCH_MODEL,
        "input": {
            "messages": [{"role": "user", "content": "今天天气如何?"}]
        },
        "parameters": {
            "tools": [
                {
                    "type": "web_search",
                    "web_search": {"search_query": "今天天气如何?"}
                }
            ]
        }
    })
    headers = {
        'Authorization': f'Bearer {QWEN_API_KEY}',
        'Content-Type': 'application/json',
    }

    print(f"请求端点: {SEARCH_API_ENDPOINT}")
    print(f"请求体: {payload}")

    conn.request("POST", SEARCH_API_ENDPOINT, payload, headers)
    res = conn.getresponse()
    data = res.read().decode("utf-8")
    print(f"\n响应状态码: {res.status}")
    print(f"响应头: {res.getheaders()}")
    print("\n完整响应内容:")
    print(data)
    print()
    conn.close()


if __name__ == "__main__":
    print("\n开始 API 调试...\n")
    debug_chat_api()
    debug_embedding_api()
    debug_search_api()
    print("\n调试完成！")
