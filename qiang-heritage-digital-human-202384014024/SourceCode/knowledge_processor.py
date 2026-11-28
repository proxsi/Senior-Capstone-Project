# Extract editable structured chunks and persist their embeddings.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Use DeepSeek to structure unstructured heritage text and persist embedded knowledge chunks."""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from db_connection import db_manager
from embedding_service import embedding_client
from gemini_chat import gemini_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeProcessor:
    """Extract structured knowledge chunks and coordinate their persistence."""
    
    def __init__(self):
        """Start the chunk counter used to build unique identifiers."""
        self.chunk_counter = 0
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """Request a JSON array from the language model and return its response text."""
        try:
            return gemini_client.generate_content(
                prompt=prompt,
                system_instruction="你是一个专业的非遗知识整理专家，请严格输出 JSON 数组，不要附加额外说明。",
                generation_config={"temperature": 0.3, "topP": 0.9},
                stream=False,
            )
        except Exception as e:
            logger.error(f"LLM调用异常: {e}")
            return None
    
    def process_bulk_text(self, text: str) -> List[Dict[str, Any]]:
        """Structure the raw text into semantic knowledge chunks and return the parsed JSON list, or an empty list on failure."""
        prompt = f"""你是一个专业的非遗知识整理专家。请将以下文本整理成结构化的知识切片。

要求：
1. 识别文本中的所有实体（非遗项目、传承人、节日、地点等）
2. 为每个实体提取关键信息，形成语义完整的知识块
3. 每个知识块必须包含：主体名称、实体类型、主题标签、向量化文本、关联关系、来源网址（如有）

实体类型可选：非遗项目、传承人、节日、地点、技艺、其他
主题标签可选：定义概述、历史渊源、工艺流程、文化价值、代表作品、传承人信息、地域特色、其他

请按以下JSON格式输出（不要有其他内容）：
[
  {{
    "source_entity": "主体名称",
    "entity_type": "实体类型",
    "topic_tag": "主题标签",
    "embedding_text": "[项目：主体名称] [维度：主题标签] 完整的语义描述，必须包含主体名称",
    "relation_desc": "关联信息，如地区：xxx；传承人：xxx",
    "source_url": "来源网址（如文本中有提及网址则填写，否则留空）"
  }}
]

待整理文本：
{text}

请输出JSON数组："""

        result = self._call_llm(prompt)
        
        if not result:
            logger.error("LLM未返回结果")
            return []
        
        try:
            # The model may wrap the array in prose, so isolate the outermost bracketed block.
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                chunks = json.loads(json_match.group())
                return chunks
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
        
        return []
    
    def save_knowledge_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Embed and persist chunks independently; return the number saved successfully."""
        saved_count = 0
        
        for chunk in chunks:
            try:
                # Identifier pairs a timestamp with a process-local counter to stay unique.
                chunk_id = f"QX_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.chunk_counter:04d}"
                self.chunk_counter += 1
                
                embedding = embedding_client.get_embedding(chunk['embedding_text'])
                
                success = db_manager.insert_knowledge_chunk(
                    chunk_id=chunk_id,
                    source_entity=chunk.get('source_entity', ''),
                    entity_type=chunk.get('entity_type', '其他'),
                    topic_tag=chunk.get('topic_tag', '其他'),
                    embedding_text=chunk.get('embedding_text', ''),
                    relation_desc=chunk.get('relation_desc', ''),
                    source_url=chunk.get('source_url', ''),
                    embedding=embedding
                )
                
                if success:
                    saved_count += 1
                    logger.info(f"保存知识切片成功: {chunk_id} - {chunk.get('source_entity')}")
                
            except Exception as e:
                # One bad chunk must not stop the remaining ones from being stored.
                logger.error(f"保存知识切片失败: {e}")
        
        return saved_count
    
    def process_and_save(self, text: str) -> Dict[str, Any]:
        """Extract and save raw text, returning success, extracted count, saved count, and extracted chunks when available."""
        logger.info(f"开始处理文本，长度: {len(text)}")
        
        chunks = self.process_bulk_text(text)
        
        if not chunks:
            return {
                "success": False,
                "message": "未能从文本中提取知识切片",
                "chunks_count": 0,
                "saved_count": 0
            }
        
        saved_count = self.save_knowledge_chunks(chunks)
        
        return {
            "success": True,
            "message": f"成功提取 {len(chunks)} 个知识切片，保存 {saved_count} 个",
            "chunks_count": len(chunks),
            "saved_count": saved_count,
            "chunks": chunks
        }


knowledge_processor = KnowledgeProcessor()
