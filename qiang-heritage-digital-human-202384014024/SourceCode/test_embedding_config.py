#!/usr/bin/env python3
# Manual integration checks for embedding config; external services may be required.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Check the configured embedding provider and model."""
from config import ZHIPU_API_KEY, ZHIPU_BASE_URL, EMBEDDING_MODEL, EMBEDDING_API_ENDPOINT

print('=== 智谱 AI 嵌入模型配置信息 ===')
print(f'API Base: {ZHIPU_BASE_URL}')
print(f'模型名称: {EMBEDDING_MODEL}')
print(f'API端点: {EMBEDDING_API_ENDPOINT}')
print(f'API Key: {"已配置" if ZHIPU_API_KEY else "未配置"}')
if ZHIPU_API_KEY:
    print(f'API Key长度: {len(ZHIPU_API_KEY)} 字符')
