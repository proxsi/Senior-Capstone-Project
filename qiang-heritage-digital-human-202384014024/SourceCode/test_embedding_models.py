#!/usr/bin/env python3
# Manual integration checks for embedding models; external services may be required.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Manual checks for the embedding-3 model."""
import http.client
import json
from config import ZHIPU_API_KEY, ZHIPU_BASE_URL, EMBEDDING_MODEL, EMBEDDING_API_ENDPOINT


def test_embedding_model(model_name):
    """Test the requested embedding model."""
    print(f"\n测试模型: {model_name}")
    print("-" * 50)

    payload = {
        "model": model_name,
        "input": "测试文本"
    }

    headers = {
        'Authorization': f'Bearer {ZHIPU_API_KEY}',
        'Content-Type': 'application/json'
    }

    try:
        conn = http.client.HTTPSConnection(ZHIPU_BASE_URL)
        conn.request("POST", EMBEDDING_API_ENDPOINT, json.dumps(payload), headers)
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        conn.close()

        print(f"状态码: {response.status}")

        if response.status == 200:
            result = json.loads(data)
            if 'data' in result and len(result['data']) > 0:
                embedding = result['data'][0]['embedding']
                print("✓ 成功！")
                print(f"  向量维度: {len(embedding)}")
                print(f"  前5个值: {embedding[:5]}")
                return True, len(embedding)
        print("✗ 失败")
        print(f"  响应: {data[:200]}")
        return False, None

    except Exception as e:
        print(f"✗ 错误: {e}")
        return False, None


if __name__ == "__main__":
    print("=" * 60)
    print("测试 embedding-3 模型")
    print("=" * 60)

    successful_models = []

    success, dimension = test_embedding_model(EMBEDDING_MODEL)
    if success:
        successful_models.append((EMBEDDING_MODEL, dimension))

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if successful_models:
        print(f"\n✓ 成功的模型 ({len(successful_models)} 个):")
        for model, dimension in successful_models:
            print(f"  - {model} (维度: {dimension})")
    else:
        print("\n✗ embedding-3 模型不可用")
