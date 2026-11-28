#!/usr/bin/env python3
# Manual integration checks for embedding quality; external services may be required.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Manual embedding quality checks for similarity, retrieval, stability, and batching."""
import time
from gemini_embedding import embedding_client
from typing import List, Tuple

def test_basic_embedding():
    """Test basic text embedding."""
    print("\n" + "="*60)
    print("测试1: 基础文本嵌入")
    print("="*60)

    test_texts = [
        "羌族刺绣是羌族文化的重要组成部分",
        "羌笛是羌族的传统乐器",
        "今天天气很好",
        "人工智能技术发展迅速"
    ]

    for i, text in enumerate(test_texts, 1):
        try:
            print(f"\n测试文本 {i}: {text}")
            embedding = embedding_client.embed_text(text)
            print(f"  ✓ 嵌入成功")
            print(f"  - 向量维度: {len(embedding)}")
            print(f"  - 前5个值: {embedding[:5]}")
            print(f"  - 向量范围: [{min(embedding):.4f}, {max(embedding):.4f}]")
            time.sleep(1)  # Avoid sending requests too quickly.
        except Exception as e:
            print(f"  ✗ 嵌入失败: {e}")

def test_similarity_computation():
    """Test similarity calculation on related and unrelated text pairs."""
    print("\n" + "="*60)
    print("测试2: 语义相似度计算")
    print("="*60)

    # Related and unrelated text pairs for comparison.
    test_pairs = [
        ("羌族刺绣是传统手工艺", "羌绣是羌族的文化遗产", "高度相关"),
        ("羌笛是乐器", "羌笛是羌族的传统乐器", "相关"),
        ("羌族文化", "人工智能技术", "不相关"),
        ("羌族服饰", "羌族刺绣", "相关"),
        ("羌族刺绣", "今天天气很好", "不相关")
    ]

    for text1, text2, expected in test_pairs:
        try:
            print(f"\n文本1: {text1}")
            print(f"文本2: {text2}")
            print(f"预期关系: {expected}")

            embedding1 = embedding_client.embed_text(text1)
            embedding2 = embedding_client.embed_text(text2)

            similarity = embedding_client.compute_similarity(embedding1, embedding2)
            print(f"  相似度: {similarity:.4f}")

            # Evaluate whether the similarity is plausible.
            if "高度相关" in expected:
                if similarity > 0.7:
                    print(f"  ✓ 相似度合理（>0.7）")
                else:
                    print(f"  ⚠ 相似度偏低（期望>0.7）")
            elif "相关" in expected:
                if similarity > 0.5:
                    print(f"  ✓ 相似度合理（>0.5）")
                else:
                    print(f"  ⚠ 相似度偏低（期望>0.5）")
            else:
                if similarity < 0.5:
                    print(f"  ✓ 相似度合理（<0.5）")
                else:
                    print(f"  ⚠ 相似度偏高（期望<0.5）")

            time.sleep(1)
        except Exception as e:
            print(f"  ✗ 测试失败: {e}")

def test_most_similar_search():
    """Test nearest-text retrieval from a small candidate corpus."""
    print("\n" + "="*60)
    print("测试3: 最相似文本搜索")
    print("="*60)

    # Candidate text corpus.
    corpus = [
        "羌族刺绣是国家级非物质文化遗产",
        "羌笛有着悠久的历史",
        "羌族服饰色彩鲜艳",
        "羌族建筑风格独特",
        "羌族舞蹈富有节奏感",
        "人工智能改变世界",
        "机器学习是AI的分支",
        "深度学习技术发展迅速"
    ]

    # Query text.
    query = "羌族的传统手工艺有哪些？"

    try:
        print(f"\n查询文本: {query}")
        print(f"候选文本库: {len(corpus)} 条")

        # Generate the query embedding.
        query_embedding = embedding_client.embed_text(query)
        print(f"查询嵌入维度: {len(query_embedding)}")

        # Generate corpus embeddings.
        print("\n生成语料库嵌入...")
        corpus_embeddings = []
        for i, text in enumerate(corpus):
            embedding = embedding_client.embed_text(text)
            corpus_embeddings.append(embedding)
            print(f"  [{i+1}/{len(corpus)}] {text[:20]}... - 维度: {len(embedding)}")
            time.sleep(0.5)

        # Find the most similar candidates.
        print("\n查找最相似的文本...")
        results = embedding_client.find_most_similar(
            query_embedding,
            corpus_embeddings,
            top_k=3
        )

        print("\nTop 3 最相似文本:")
        for idx, (corpus_idx, similarity) in enumerate(results, 1):
            print(f"\n{idx}. 相似度: {similarity:.4f}")
            print(f"   文本: {corpus[corpus_idx]}")

    except Exception as e:
        print(f"✗ 测试失败: {e}")

def test_embedding_quality():
    """Measure embedding stability and basic quality indicators."""
    print("\n" + "="*60)
    print("测试4: 嵌入质量评估")
    print("="*60)

    test_text = "羌族刺绣是羌族文化的重要组成部分"

    try:
        print(f"\n测试文本: {test_text}")

        # Generate repeated embeddings to check stability.
        print("\n测试嵌入稳定性（生成3次）:")
        embeddings = []
        for i in range(3):
            embedding = embedding_client.embed_text(test_text)
            embeddings.append(embedding)
            print(f"  第{i+1}次: 维度={len(embedding)}, 范围=[{min(embedding):.4f}, {max(embedding):.4f}]")
            time.sleep(1)

        # Compare repeated embeddings; similarity is expected to approach 1.0.
        if len(embeddings) >= 2:
            sim_12 = embedding_client.compute_similarity(embeddings[0], embeddings[1])
            sim_13 = embedding_client.compute_similarity(embeddings[0], embeddings[2])
            sim_23 = embedding_client.compute_similarity(embeddings[1], embeddings[2])

            print(f"\n嵌入相似度（应该接近1.0）:")
            print(f"  第1次 vs 第2次: {sim_12:.4f}")
            print(f"  第1次 vs 第3次: {sim_13:.4f}")
            print(f"  第2次 vs 第3次: {sim_23:.4f}")

            avg_similarity = (sim_12 + sim_13 + sim_23) / 3
            print(f"\n平均相似度: {avg_similarity:.4f}")

            if avg_similarity > 0.95:
                print("  ✓ 嵌入稳定性优秀")
            elif avg_similarity > 0.90:
                print("  ✓ 嵌入稳定性良好")
            else:
                print("  ⚠ 嵌入稳定性一般")

    except Exception as e:
        print(f"✗ 测试失败: {e}")

def test_batch_embedding():
    """Test batch embedding."""
    print("\n" + "="*60)
    print("测试5: 批量文本嵌入")
    print("="*60)

    texts = [
        "文本1",
        "文本2",
        "文本3"
    ]

    try:
        print(f"\n批量嵌入 {len(texts)} 个文本...")
        embeddings = embedding_client.embed_batch(texts)

        print("\n结果:")
        for i, (text, embedding) in enumerate(zip(texts, embeddings), 1):
            if embedding:
                print(f"  {i}. {text}: ✓ 成功 (维度: {len(embedding)})")
            else:
                print(f"  {i}. {text}: ✗ 失败")

    except Exception as e:
        print(f"✗ 测试失败: {e}")

def main():
    """Run the embedding quality checks."""
    print("="*60)
    print("智谱 AI 嵌入模型效果测试")
    print("="*60)

    try:
        # Run all checks.
        test_basic_embedding()
        test_similarity_computation()
        test_most_similar_search()
        test_embedding_quality()
        test_batch_embedding()

        print("\n" + "="*60)
        print("✓ 所有测试完成")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n✗ 测试过程出错: {e}")

if __name__ == "__main__":
    main()
