# Manual integration checks for all; external services may be required.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Manual integration checks for database connectivity and external AI providers."""
import sys
from database import db_manager
from gemini_chat import gemini_client
from gemini_embedding import embedding_client
from gemini_search import search_client


def test_database_connection():
    """Test database connectivity."""
    print("=" * 60)
    print("测试1: 数据库连接")
    print("=" * 60)

    try:
        if db_manager.test_connection():
            print("✓ 数据库连接成功！")
            return True
        print("✗ 数据库连接失败！")
        return False
    except Exception as e:
        print(f"✗ 数据库连接测试异常: {e}")
        return False


def test_gemini_chat():
    """Test the DeepSeek chat model."""
    print("\n" + "=" * 60)
    print("测试2: DeepSeek 对话模型")
    print("=" * 60)

    try:
        prompt = "1+2+3+4+5+....+999?"
        print(f"发送问题: {prompt}")

        response = gemini_client.generate_content(
            prompt=prompt,
            system_instruction="你是一个数学助手，请帮我计算数学问题。",
            stream=True,
        )

        print(f"AI回复: {response}")
        print("✓ 对话模型测试成功！")
        return True
    except Exception as e:
        print(f"✗ 对话模型测试失败: {e}")
        return False


def test_gemini_embedding():
    """Test the Zhipu embedding model."""
    print("\n" + "=" * 60)
    print("测试3: 智谱AI 嵌入模型")
    print("=" * 60)

    try:
        text = "这是一个测试文本，用于生成嵌入向量。"
        print(f"测试文本: {text}")

        embedding = embedding_client.embed_text(text)
        print(f"嵌入向量维度: {len(embedding)}")
        print(f"前10个值: {embedding[:10]}")

        text1 = "人工智能是计算机科学的一个分支"
        text2 = "机器学习是人工智能的一个子领域"
        text3 = "今天天气很好"

        embedding1 = embedding_client.embed_text(text1)
        embedding2 = embedding_client.embed_text(text2)
        embedding3 = embedding_client.embed_text(text3)

        similarity_12 = embedding_client.compute_similarity(embedding1, embedding2)
        similarity_13 = embedding_client.compute_similarity(embedding1, embedding3)

        print(f"\n文本1: {text1}")
        print(f"文本2: {text2}")
        print(f"文本3: {text3}")
        print(f"\n文本1和文本2的相似度: {similarity_12:.4f}")
        print(f"文本1和文本3的相似度: {similarity_13:.4f}")

        print("✓ 嵌入模型测试成功！")
        return True
    except Exception as e:
        print(f"✗ 嵌入模型测试失败: {e}")
        return False


def test_gemini_search():
    """Test Qwen web search."""
    print("\n" + "=" * 60)
    print("测试4: 阿里通义 联网搜索")
    print("=" * 60)

    try:
        query = "今天重庆天气如何?"
        print(f"搜索查询: {query}")

        result = search_client.search_and_answer(query)
        print(f"搜索结果:\n{result}")

        print("\n✓ 联网搜索测试成功！")
        return True
    except Exception as e:
        print(f"✗ 联网搜索测试失败: {e}")
        return False


def main():
    """Run the integration checks and summarize results."""
    print("\n" + "=" * 60)
    print("开始综合测试")
    print("=" * 60)

    results = {
        "数据库连接": test_database_connection(),
        "DeepSeek对话模型": test_gemini_chat(),
        "智谱AI嵌入模型": test_gemini_embedding(),
        "阿里通义联网搜索": test_gemini_search(),
    }

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")

    passed = sum(1 for r in results.values() if r)
    total = len(results)
    # Percentage is only informational; the exit code drives pass/fail for scripts.
    pass_rate = (passed / total) * 100

    print(f"\n通过率: {passed}/{total} ({pass_rate:.1f}%)")

    db_manager.close_all_connections()
    print("\n所有测试完成，数据库连接已关闭。")

    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
