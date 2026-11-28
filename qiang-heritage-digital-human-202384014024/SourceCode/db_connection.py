# Primary PostgreSQL chunk store; its connection dictionary is independent of config.py.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""PostgreSQL knowledge-chunk persistence and Python cosine-similarity retrieval."""
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Host and port target the managed PostgreSQL instance; the password is supplied at deploy time.
DB_CONFIG = {
    'host': 'dbconn.sealosbja.site',
    'port': 34705,
    'database': 'postgres',
    'user': 'postgres',
    'password': ''
}


class DatabaseManager:
    """Manage knowledge-chunk database operations."""
    
    def __init__(self):
        """Store the connection settings and log the target host for diagnostics."""
        self.config = DB_CONFIG
        logger.info(f"数据库管理器初始化: {self.config['host']}:{self.config['port']}")
    
    @contextmanager
    def get_connection(self):
        """Yield a connection, commit on success, roll back on failure, and always close it."""
        conn = None
        try:
            conn = psycopg2.connect(**self.config)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a parameterized query and return rows as dictionaries."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute a write and return its affected row count."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount
    
    def execute_insert(self, query: str, params: tuple = None) -> str:
        """Insert a row and return its chunk_id."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query + " RETURNING chunk_id", params)
                result = cur.fetchone()
                return result[0] if result else None
    
    def init_knowledge_table(self):
        """Create the chunk table and metadata indexes if absent."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS non_heritage_knowledge_chunks (
            chunk_id VARCHAR(50) PRIMARY KEY,
            source_entity VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            topic_tag VARCHAR(50) NOT NULL,
            embedding_text TEXT NOT NULL,
            relation_desc TEXT,
            source_url TEXT,
            embedding JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_source_entity ON non_heritage_knowledge_chunks(source_entity);
        CREATE INDEX IF NOT EXISTS idx_entity_type ON non_heritage_knowledge_chunks(entity_type);
        CREATE INDEX IF NOT EXISTS idx_topic_tag ON non_heritage_knowledge_chunks(topic_tag);
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # One script issues the table and index statements in a single transaction.
                    cur.execute(create_table_sql)
                logger.info("知识切片表初始化成功")
        except Exception as e:
            logger.warning(f"表可能已存在或创建失败: {e}")
    
    def insert_knowledge_chunk(
        self,
        chunk_id: str,
        source_entity: str,
        entity_type: str,
        topic_tag: str,
        embedding_text: str,
        relation_desc: str = "",
        source_url: str = "",
        embedding: List[float] = None
    ) -> bool:
        """Insert or update a chunk and its JSONB embedding; return whether persistence succeeded."""
        import json
        
        # The vector is stored as JSON text in a JSONB column, so no pgvector extension is needed.
        embedding_json = json.dumps(embedding) if embedding else None
        
        # ON CONFLICT makes re-ingesting the same identifier an update instead of an error.
        query = """
        INSERT INTO non_heritage_knowledge_chunks 
        (chunk_id, source_entity, entity_type, topic_tag, embedding_text, relation_desc, source_url, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (chunk_id) DO UPDATE SET
        source_entity = EXCLUDED.source_entity,
        entity_type = EXCLUDED.entity_type,
        topic_tag = EXCLUDED.topic_tag,
        embedding_text = EXCLUDED.embedding_text,
        relation_desc = EXCLUDED.relation_desc,
        source_url = EXCLUDED.source_url,
        embedding = EXCLUDED.embedding,
        updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            self.execute_update(query, (
                chunk_id, source_entity, entity_type, topic_tag,
                embedding_text, relation_desc, source_url, embedding_json
            ))
            return True
        except Exception as e:
            logger.error(f"插入知识切片失败: {e}")
            return False
    
    def search_similar(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """Load stored embeddings and rank them by cosine similarity computed in Python."""
        import numpy as np
        
        query = """
        SELECT chunk_id, source_entity, entity_type, topic_tag, 
               embedding_text, relation_desc, source_url, embedding
        FROM non_heritage_knowledge_chunks
        WHERE embedding IS NOT NULL
        """
        
        try:
            results = self.execute_query(query)
            
            if not results:
                return []
            
            similarities = []
            # Cosine similarity normalizes by both vector norms so longer passages are not favoured.
            query_vec = np.array(query_embedding)
            query_norm = np.linalg.norm(query_vec)
            
            for result in results:
                if result.get('embedding'):
                    try:
                        emb = np.array(result['embedding'])
                        emb_norm = np.linalg.norm(emb)
                        if emb_norm > 0 and query_norm > 0:
                            similarity = np.dot(query_vec, emb) / (query_norm * emb_norm)
                        else:
                            similarity = 0
                        result['similarity'] = float(similarity)
                        similarities.append(result)
                    except:
                        # Rows holding a malformed vector are skipped instead of failing the search.
                        pass
            
            # Rank in Python because the full result set was loaded above.
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    def get_all_chunks(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Return paginated knowledge chunks ordered by creation time."""
        query = """
        SELECT chunk_id, source_entity, entity_type, topic_tag, 
               embedding_text, relation_desc, source_url, created_at
        FROM non_heritage_knowledge_chunks
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """
        results = self.execute_query(query, (limit, offset))
        # Timestamps are stringified so the API models can serialize them without extra handling.
        for r in results:
            if 'created_at' in r and r['created_at']:
                r['created_at'] = str(r['created_at'])
        return results
    
    def get_chunk_count(self) -> int:
        """Return the total number of stored chunks."""
        query = "SELECT COUNT(*) as count FROM non_heritage_knowledge_chunks"
        result = self.execute_query(query)
        return result[0]['count'] if result else 0


db_manager = DatabaseManager()
