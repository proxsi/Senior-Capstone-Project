#!/usr/bin/env python3
# Manual connectivity diagnostics for the embedding provider.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Connectivity diagnostics for the embedding API."""
import http.client
import json
from config import ZHIPU_API_KEY, ZHIPU_BASE_URL, EMBEDDING_MODEL, EMBEDDING_API_ENDPOINT


def test_api_connection():
    """Test connectivity to the Zhipu embedding API."""
    print("=" * 60)
    print("Embedding API 连接诊断")
    print("=" * 60)

    print("\nAPI配置:")
    print(f"  Base URL: {ZHIPU_BASE_URL}")
    print(f"  模型: {EMBEDDING_MODEL}")
    print(f"  端点: {EMBEDDING_API_ENDPOINT}")
    print(f"  API Key: {'已配置' if ZHIPU_API_KEY else '未配置'}")

    if not ZHIPU_API_KEY:
        print("\n✗ API Key 未配置，无法测试")
        return

    payload = {
        "model": EMBEDDING_MODEL,
        "input": "测试"
    }
    headers = {
        'Authorization': f'Bearer {ZHIPU_API_KEY}',
        'Content-Type': 'application/json'
    }

    print("\n发送测试请求...")
    print(f"  URL: {ZHIPU_BASE_URL}{EMBEDDING_API_ENDPOINT}")

    try:
        # One plain-text probe distinguishes bad credentials (401) from a wrong endpoint (404).
        conn = http.client.HTTPSConnection(ZHIPU_BASE_URL)
        conn.request("POST", EMBEDDING_API_ENDPOINT, json.dumps(payload), headers)
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        conn.close()

        print(f"\n响应状态码: {response.status}")
        print(f"响应头: {dict(response.getheaders())}")

        if response.status == 200:
            print("\n✓ API 连接成功！")
            print(f"响应数据: {data[:200]}...")
        elif response.status == 401:
            print("\n✗ 认证失败 (401)")
            print(f"响应数据: {data}")
        elif response.status == 404:
            print("\n✗ 端点不存在 (404)")
            print(f"响应数据: {data}")
        else:
            print("\n✗ 请求失败")
            print(f"响应数据: {data}")
    except Exception as e:
        print(f"\n✗ 连接失败: {e}")


if __name__ == "__main__":
    test_api_connection()
