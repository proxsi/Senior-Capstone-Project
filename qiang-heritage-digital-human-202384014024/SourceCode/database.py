# Legacy pooled PostgreSQL helper configured through config.py.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Pooled PostgreSQL database utility."""
import psycopg2
from psycopg2 import pool, sql
from typing import Optional, List, Dict, Any
import logging
from config import DB_CONFIG, DATABASE_URL

# Configure logging.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage pooled PostgreSQL connections and common SQL operations."""
    
    def __init__(self):
        """Create the pooled manager and connect to PostgreSQL immediately."""
        self.connection_pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the connection pool."""
        # A small pool (one to ten connections) is enough for the single-process API server.
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database']
            )
            logger.info("数据库连接池初始化成功")
        except Exception as e:
            logger.error(f"数据库连接池初始化失败: {e}")
            raise
    
    def get_connection(self):
        """Borrow a connection from the pool."""
        if self.connection_pool:
            return self.connection_pool.getconn()
        raise Exception("连接池未初始化")
    
    def return_connection(self, conn):
        """Return a connection to the pool."""
        if self.connection_pool and conn:
            self.connection_pool.putconn(conn)
    
    def execute_query(self, query: str, params: Optional[tuple] = None, fetch: bool = True) -> Optional[List[tuple]]:
        """Execute query with optional params; fetch controls whether result rows are returned."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch:
                result = cursor.fetchall()
                return result
            else:
                conn.commit()
                return None
                
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"执行查询失败: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def execute_insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert data, a column-to-value mapping, into table and return the inserted row ID."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            columns = data.keys()
            values = data.values()
            
            insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
                # Identifiers are composed with psycopg2.sql so names are quoted safely.
                sql.Identifier(table),
                sql.SQL(', ').join(map(sql.Identifier, columns)),
                sql.SQL(', ').join(sql.Placeholder() * len(columns))
            )
            
            cursor.execute(insert_query, tuple(values))
            conn.commit()
            
            inserted_id = cursor.fetchone()[0]
            logger.info(f"成功插入数据到表 {table}，ID: {inserted_id}")
            return inserted_id
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"插入数据失败: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def execute_update(self, table: str, data: Dict[str, Any], where_clause: str, where_params: tuple) -> int:
        """Update table with data under where_clause and where_params; return the affected row count."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            set_clause = sql.SQL(', ').join(
                sql.SQL('{} = {}').format(sql.Identifier(k), sql.Placeholder())
                for k in data.keys()
            )
            
            update_query = sql.SQL("UPDATE {} SET {} WHERE {}").format(
                sql.Identifier(table),
                set_clause,
                sql.SQL(where_clause)
            )
            
            params = tuple(data.values()) + where_params
            # SET values come first, then the WHERE placeholders, matching the SQL order above.
            cursor.execute(update_query, params)
            conn.commit()
            
            affected_rows = cursor.rowcount
            logger.info(f"更新表 {table}，影响行数: {affected_rows}")
            return affected_rows
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"更新数据失败: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def execute_delete(self, table: str, where_clause: str, where_params: tuple) -> int:
        """Delete rows matching where_clause and where_params and return the affected row count."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            delete_query = sql.SQL("DELETE FROM {} WHERE {}").format(
                sql.Identifier(table),
                sql.SQL(where_clause)
            )
            
            cursor.execute(delete_query, where_params)
            conn.commit()
            
            affected_rows = cursor.rowcount
            logger.info(f"从表 {table} 删除数据，影响行数: {affected_rows}")
            return affected_rows
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"删除数据失败: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            result = self.execute_query("SELECT version()")
            if result:
                logger.info(f"数据库连接成功，版本: {result[0][0]}")
                return True
            return False
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False
    
    def create_table_if_not_exists(self, table_name: str, columns: Dict[str, str]) -> None:
        """Create table_name if absent using the column-name-to-SQL-type mapping columns."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            column_definitions = [
                sql.SQL("{} {}").format(sql.Identifier(col), sql.SQL(type_def))
                for col, type_def in columns.items()
            ]
            
            create_query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
                sql.Identifier(table_name),
                sql.SQL(', ').join(column_definitions)
            )
            
            cursor.execute(create_query)
            conn.commit()
            logger.info(f"表 {table_name} 创建成功或已存在")
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"创建表失败: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def close_all_connections(self):
        """Close every pooled connection."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("所有数据库连接已关闭")


# Create the shared database manager.
db_manager = DatabaseManager()


if __name__ == "__main__":
    # Test database connectivity.
    print("测试数据库连接...")
    if db_manager.test_connection():
        print("✓ 数据库连接成功！")
    else:
        print("✗ 数据库连接失败！")
