# Validate and deduplicate scraped items before optional Neo4j ingestion.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Scrapy pipelines for validating, deduplicating, and ingesting heritage content."""
import logging
from typing import Dict, Any
import sys
import os

# Add the project root to the Python import path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from knowledge_base import knowledge_loader

logger = logging.getLogger(__name__)


class ICHDataPipeline:
    """Ingest accepted heritage items through the Neo4j knowledge loader."""
    
    def __init__(self):
        """Initialize pipeline state."""
        self.loader = None
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0
        }
    
    def open_spider(self, spider):
        """Initialize the loader when the spider opens."""
        try:
            self.loader = knowledge_loader.KnowledgeLoader()
            logger.info(f"爬虫 {spider.name} 启动，知识库连接成功")
        except Exception as e:
            logger.error(f"知识库连接失败: {e}")
            raise
    
    def close_spider(self, spider):
        """Close loader resources when the spider closes."""
        logger.info(f"爬虫 {spider.name} 完成，统计信息: {self.stats}")
        if self.loader:
            self.loader.close()
    
    def process_item(self, item: Dict[str, Any], spider) -> Dict[str, Any]:
        """Format an item as one document, ingest it, and count the outcome."""
        self.stats['total'] += 1
        
        try:
            # Assemble the complete document text.
            text_content = self._build_text_content(item)
            
            # Set the source name.
            source_name = f"爬虫数据: {item.get('url', '未知来源')}"
            
            # Ingest through the knowledge loader.
            self.loader.ingest_text_data(
                text_content=text_content,
                source_name=source_name
            )
            
            self.stats['success'] += 1
            logger.info(f"成功入库: {item.get('title', '无标题')}")
            
        except Exception as e:
            self.stats['failed'] += 1
            logger.error(f"入库失败: {item.get('title', '无标题')}, 错误: {e}")
        
        return item
    
    def _build_text_content(self, item: Dict[str, Any]) -> str:
        """Format item fields as a single text document for ingestion."""
        parts = []
        
        # Title.
        if item.get('title'):
            parts.append(f"标题: {item['title']}")
        
        # Category.
        if item.get('category'):
            parts.append(f"分类: {item['category']}")
        
        # Publication date.
        if item.get('date'):
            parts.append(f"发布日期: {item['date']}")
        
        # URL
        if item.get('url'):
            parts.append(f"来源链接: {item['url']}")
        
        # Article content.
        if item.get('content'):
            parts.append(f"\n正文内容:\n{item['content']}")
        
        return '\n\n'.join(parts)


class DataValidationPipeline:
    """Validate required fields, content length, and source URLs."""
    
    def process_item(self, item: Dict[str, Any], spider) -> Dict[str, Any]:
        """Validate item fields and return the accepted item; raise DropItem on invalid input."""
        # Required field check runs first so later checks can read content safely.
        if not item.get('title') or not item.get('content'):
            logger.warning(f"数据不完整，丢弃: {item.get('url', '未知URL')}")
            raise scrapy.exceptions.DropItem("缺少标题或内容")
        
        # Check content length.
        if len(item['content']) < 50:
            logger.warning(f"内容过短，丢弃: {item['title']}")
            raise scrapy.exceptions.DropItem("内容过短")
        
        # Validate the URL.
        if not item.get('url') or not item['url'].startswith('http'):
            logger.warning(f"URL无效，丢弃: {item['title']}")
            raise scrapy.exceptions.DropItem("URL无效")
        
        return item


class DeduplicationPipeline:
    """Reject duplicate items within a crawler run."""
    
    def __init__(self):
        """Initialize the set of previously seen items."""
        self.seen_urls = set()
    
    def process_item(self, item: Dict[str, Any], spider) -> Dict[str, Any]:
        """Return unseen items and raise DropItem for duplicates."""
        url = item.get('url')
        
        if url in self.seen_urls:
            logger.info(f"重复URL，跳过: {url}")
            raise scrapy.exceptions.DropItem("重复数据")
        
        self.seen_urls.add(url)
        return item


# Import Scrapy at the end so the pipeline classes stay importable when it is absent.
try:
    import scrapy
except ImportError:
    logger.warning("Scrapy未安装，去重管道将无法使用")
    DeduplicationPipeline = None
