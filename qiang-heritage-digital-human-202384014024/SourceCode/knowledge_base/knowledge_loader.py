# Optional Neo4j ingestion path, separate from online PostgreSQL retrieval.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Neo4j knowledge loader with rule-based entity extraction and vector storage."""
import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import re
import config
from gemini_embedding import embedding_client

# Configure logging.
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KnowledgeLoader:
    """Load graph entities and embedded text chunks into Neo4j."""
    
    def __init__(self):
        """Initialize the loader and attempt a Neo4j connection."""
        self.driver = None
        try:
            self._connect_neo4j()
        except Exception as e:
            logger.warning(f"Neo4j连接失败，系统将在没有本地知识库的情况下运行: {e}")
        
    def _connect_neo4j(self):
        """Connect to Neo4j and verify the connection with a simple query."""
        try:
            self.driver = GraphDatabase.driver(
                config.NEO4J_CONFIG['uri'],
                auth=(
                    config.NEO4J_CONFIG['user'],
                    config.NEO4J_CONFIG['password']
                )
            )
            # Verify connectivity.
            with self.driver.session(database=config.NEO4J_CONFIG['database']) as session:
                session.run("RETURN 1")
            logger.info("成功连接到Neo4j数据库")
        except Exception as e:
            logger.error(f"连接Neo4j数据库失败: {e}")
            raise
    
    def close(self):
        """Close the Neo4j driver."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j连接已关闭")
    
    def _split_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """Split text into chunks of chunk_size characters with overlap; prefer nearby sentence boundaries."""
        chunk_size = chunk_size or config.CHUNK_SIZE
        overlap = overlap or config.CHUNK_OVERLAP
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # For intermediate chunks, prefer a sentence-ending punctuation boundary.
            if end < len(text):
                # Find the nearest sentence-ending character.
                for i in range(len(chunk) - 1, max(0, len(chunk) - 100), -1):
                    if chunk[i] in ['。', '！', '？', '\n']:
                        chunk = chunk[:i+1]
                        end = start + i + 1
                        break
            
            chunks.append(chunk.strip())
            # Step back by the overlap so consecutive chunks share sentence context.
            start = end - overlap
            
            # Stop when the next start position reaches the end of the text.
            if start >= len(text):
                break
        
        logger.info(f"文本切分完成，共 {len(chunks)} 个块")
        return chunks
    
    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """Extract entity types and names from text using simple regular-expression rules."""
        entities = []
        
        # Simple extraction rules; a production pipeline could use an NER model.
        # Extract heritage practitioners.
        inheritor_pattern = r'([\u4e00-\u9fa5]{2,4})(传承人|大师|艺人)'
        inheritors = re.findall(inheritor_pattern, text)
        for name, title in inheritors:
            entities.append({'type': '传承人', 'name': name, 'title': title})
        
        # Extract heritage project names.
        project_pattern = r'([羌][\u4e00-\u9fa5]{1,4})(技艺|工艺|文化|艺术)'
        projects = re.findall(project_pattern, text)
        for name, category in projects:
            entities.append({'type': '非遗项目', 'name': name, 'category': category})
        
        # Extract place names.
        location_pattern = r'(四川省|阿坝州|茂县|汶川|理县|北川)'
        locations = re.findall(location_pattern, text)
        for loc in locations:
            entities.append({'type': '地点', 'name': loc})
        
        logger.info(f"从文本中提取到 {len(entities)} 个实体")
        return entities
    
    def _create_graph_nodes(self, tx, entities: List[Dict[str, str]], source: str):
        """Create entity nodes and simplified inheritance relationships in transaction tx, tagged with source."""
        # Create entity nodes.
        for entity in entities:
            entity_type = entity['type']
            entity_name = entity['name']
            
            # Map entity types to graph labels.
            label_map = {
                '传承人': 'Inheritor',
                '非遗项目': 'HeritageProject',
                '地点': 'Location'
            }
            
            label = label_map.get(entity_type, 'Entity')
            
            # Create or update the node.
            query = f"""
            MERGE (n:{label} {{name: $name}})
            SET n.source = $source, n.updated_at = datetime()
            """
            tx.run(query, name=entity_name, source=source)
        
        # Create simplified practitioner-to-project INHERITS relationships.
        inheritors = [e for e in entities if e['type'] == '传承人']
        projects = [e for e in entities if e['type'] == '非遗项目']
        
        for inheritor in inheritors:
            for project in projects:
                query = """
                MATCH (i:Inheritor {name: $inheritor_name})
                MATCH (p:HeritageProject {name: $project_name})
                MERGE (i)-[r:INHERITS]->(p)
                SET r.source = $source
                """
                tx.run(
                    query,
                    inheritor_name=inheritor['name'],
                    project_name=project['name'],
                    source=source
                )
    
    def _create_vector_index(self):
        """Create the Neo4j vector index if it does not exist."""
        try:
            with self.driver.session(database=config.NEO4J_CONFIG['database']) as session:
                # Check whether the index exists.
                result = session.run("SHOW INDEXES WHERE name = 'text_vector_index'")
                if not result.single():
                    # Neo4j needs an explicit dimension and metric for every vector index.
                    session.run("""
                    CREATE VECTOR INDEX text_vector_index 
                    FOR (c:Chunk) ON (c.embedding)
                    OPTIONS {
                        indexConfig: {
                            `vector.dimensions`: 768,
                            `vector.similarity_function`: 'cosine'
                        }
                    }
                    """)
                    logger.info("向量索引创建成功")
                else:
                    logger.info("向量索引已存在")
        except Exception as e:
            logger.warning(f"创建向量索引时出现警告: {e}")
    
    def _store_vector_chunks(self, chunks: List[str], source: str) -> List[str]:
        """Embed chunks, store them with source metadata, and return their generated identifiers."""
        chunk_ids = []
        
        try:
            with self.driver.session(database=config.NEO4J_CONFIG['database']) as session:
                for i, chunk in enumerate(chunks):
                    # Generate the embedding.
                    embedding = embedding_client.embed_text(chunk)
                    
                    # Store the chunk in Neo4j.
                    # Identifier is derived from the source name plus the chunk offset.
                    chunk_id = f"{source}_{i}"
                    query = """
                    CREATE (c:Chunk {
                        id: $id,
                        text: $text,
                        embedding: $embedding,
                        source: $source,
                        created_at: datetime()
                    })
                    RETURN c.id as id
                    """
                    result = session.run(
                        query,
                        id=chunk_id,
                        text=chunk,
                        embedding=embedding,
                        source=source
                    )
                    chunk_ids.append(result.single()['id'])
            
            logger.info(f"成功存储 {len(chunks)} 个向量块")
            return chunk_ids
            
        except Exception as e:
            logger.error(f"存储向量块失败: {e}")
            raise
    
    def ingest_text_data(self, text_content: str, source_name: str):
        """Ingest text_content under source_name: split text, extract entities, build graph relationships, store embeddings, and return counts."""
        logger.info(f"开始导入数据，来源: {source_name}")
        
        if not self.driver:
            logger.error("Neo4j未连接，无法导入数据到知识库")
            return {
                'source': source_name,
                'chunks_count': 0,
                'entities_count': 0,
                'chunk_ids': [],
                'error': 'Neo4j未连接'
            }
        
        try:
            # 1. Split the text.
            chunks = self._split_text(text_content)
            
            # 2. Extract entities.
            entities = self._extract_entities(text_content)
            
            # 3. Create graph nodes and relationships.
            with self.driver.session(database=config.NEO4J_CONFIG['database']) as session:
                session.execute_write(
                    self._create_graph_nodes,
                    entities,
                    source_name
                )
            
            # 4. Create the vector index if absent.
            self._create_vector_index()
            
            # 5. Store embedded text chunks.
            chunk_ids = self._store_vector_chunks(chunks, source_name)
            
            stats = {
                'source': source_name,
                'chunks_count': len(chunks),
                'entities_count': len(entities),
                'chunk_ids': chunk_ids
            }
            
            logger.info(f"数据导入成功: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"数据导入失败: {e}")
            return {
                'source': source_name,
                'chunks_count': 0,
                'entities_count': 0,
                'chunk_ids': [],
                'error': str(e)
            }
    
    def search_by_vector(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Embed query and return the top_k matching Neo4j chunks with similarity scores."""
        top_k = top_k or config.TOP_K_RESULTS
        
        if not self.driver:
            logger.warning("Neo4j未连接，跳过向量搜索")
            return []
        
        try:
            # Generate the query vector.
            try:
                query_embedding = embedding_client.embed_text(query)
            except Exception as e:
                logger.error(f"生成查询向量失败: {e}")
                return []
            
            # Run Neo4j vector search; queryNodes ranks by the index similarity function.
            with self.driver.session(database=config.NEO4J_CONFIG['database']) as session:
                query_str = """
                CALL db.index.vector.queryNodes('text_vector_index', $top_k, $embedding)
                YIELD node, score
                RETURN node.text as text, node.source as source, score
                ORDER BY score DESC
                """
                results = session.run(
                    query_str,
                    top_k=top_k,
                    embedding=query_embedding
                )
                
                search_results = []
                for record in results:
                    search_results.append({
                        'text': record['text'],
                        'source': record['source'],
                        'score': record['score']
                    })
                
                logger.info(f"向量搜索完成，返回 {len(search_results)} 个结果")
                return search_results
                
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    def search_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """Search stored chunk text for keyword and return matching text and source fields."""
        if not self.driver:
            logger.warning("Neo4j未连接，跳过关键词搜索")
            return []
        
        try:
            with self.driver.session(database=config.NEO4J_CONFIG['database']) as session:
                # Search chunk text for the keyword.
                query_str = """
                MATCH (c:Chunk)
                WHERE c.text CONTAINS $keyword
                RETURN c.text as text, c.source as source
                LIMIT 10
                """
                results = session.run(query_str, keyword=keyword)
                
                search_results = []
                for record in results:
                    search_results.append({
                        'text': record['text'],
                        'source': record['source']
                    })
                
                logger.info(f"关键词搜索完成，返回 {len(search_results)} 个结果")
                return search_results
                
        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
            return []


# Create the shared loader instance.
knowledge_loader = KnowledgeLoader()


if __name__ == "__main__":
    # Manual integration-test example.
    test_text = """
    羌绣是羌族传统的刺绣工艺，有着悠久的历史。羌绣以其精美的图案和独特的技艺而闻名。
    羌绣传承人汪国芳是国家级非物质文化遗产代表性传承人，她从小跟随母亲学习羌绣技艺。
    羌绣主要流行于四川省阿坝州茂县、汶川、理县等地。羌绣的图案多取材于自然和生活，
    如花卉、动物、山水等，色彩鲜艳，寓意吉祥。
    """
    
    # Ingest the example text.
    stats = knowledge_loader.ingest_text_data(
        test_text,
        source_name="测试数据.txt"
    )
    print(f"导入统计: {stats}")
    
    # Test vector search.
    results = knowledge_loader.search_by_vector("羌绣的特点是什么？")
    print(f"\n向量搜索结果:")
    for i, result in enumerate(results, 1):
        print(f"{i}. 相似度: {result['score']:.4f}")
        print(f"   来源: {result['source']}")
        print(f"   内容: {result['text'][:100]}...")
        print()
    
    # Close the connection.
    knowledge_loader.close()
