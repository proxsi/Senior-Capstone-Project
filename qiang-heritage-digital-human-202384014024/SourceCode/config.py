# Environment settings for provider APIs and optional database utilities.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Environment-backed configuration for databases and external AI services."""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# Neo4j connection settings for the optional knowledge graph loader.
# ============================================
NEO4J_CONFIG = {
    'uri': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    'user': os.getenv('NEO4J_USER', 'neo4j'),
    'password': os.getenv('NEO4J_PASSWORD', ''),
    'database': os.getenv('NEO4J_DATABASE', 'neo4j')
}

# ============================================
# PostgreSQL connection settings for the pooled database utility.
# ============================================
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'dbconn.sealosbja.site'),
    'port': int(os.getenv('POSTGRES_PORT', 34705)),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', ''),
    'database': os.getenv('POSTGRES_DATABASE', 'postgres'),
    'direct_connection': True
}

# A single DSN is kept for tooling that prefers one connection string over a dictionary.
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?directConnection=true"

# ============================================
# AI provider configuration.
# ============================================
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', 'your_deepseek_key')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'api.deepseek.com')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
VISION_MODEL = os.getenv('VISION_MODEL', DEEPSEEK_MODEL)

ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY', 'your_zhipuai_key')
ZHIPU_BASE_URL = os.getenv('ZHIPU_BASE_URL', 'open.bigmodel.cn')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'embedding-3')

QWEN_API_KEY = os.getenv('QWEN_API_KEY', 'your_aliyun_key')
QWEN_BASE_URL = os.getenv('QWEN_BASE_URL', 'dashscope.aliyuncs.com')
SEARCH_MODEL = os.getenv('SEARCH_MODEL', 'qwen-plus-latest')

XF_APP_ID = os.getenv('XF_APP_ID', 'your_xfyun_app_id')
XF_API_KEY = os.getenv('XF_API_KEY', 'your_xfyun_api_key')
XF_API_SECRET = os.getenv('XF_API_SECRET', 'your_xfyun_api_secret')

# Provider API paths.
CHAT_API_ENDPOINT = '/v1/chat/completions'
EMBEDDING_API_ENDPOINT = '/api/paas/v4/embeddings'
SEARCH_API_ENDPOINT = '/api/v1/services/aigc/text-generation/generation'

# ============================================
# Optional web-search API configuration.
# ============================================
SERPER_API_KEY = os.getenv('SERPER_API_KEY', '')

# ============================================
# RAG settings; individual modules may also use their own defaults.
# ============================================
SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.75))
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 500))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', 50))
TOP_K_RESULTS = int(os.getenv('TOP_K_RESULTS', 3))
WEB_SEARCH_RESULTS = int(os.getenv('WEB_SEARCH_RESULTS', 3))

# ============================================
# FastAPI server configuration.
# ============================================
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', 8080))
API_RELOAD = os.getenv('API_RELOAD', 'True').lower() == 'true'

# ============================================
# Logging configuration.
# ============================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'logs/qiang_heritage.log')

# ============================================
# Crawler configuration.
# ============================================
CRAWLER_ENABLED = os.getenv('CRAWLER_ENABLED', 'True').lower() == 'true'
CRAWLER_INTERVAL = int(os.getenv('CRAWLER_INTERVAL', 3600))
CRAWLER_TARGET_URL = os.getenv('CRAWLER_TARGET_URL', 'https://www.ihchina.cn/')

# Defaults consumed by the chat adapter; individual requests may override these keys.
DEFAULT_GENERATION_CONFIG = {
    'temperature': 1,
    'topP': 1,
    'maxOutputTokens': 4096
}

# Legacy Gemini-style safety thresholds kept for compatibility; the DeepSeek adapter ignores them.
SAFETY_SETTINGS = [
    {
        'category': 'HARM_CATEGORY_HATE_SPEECH',
        'threshold': 'OFF'
    },
    {
        'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT',
        'threshold': 'OFF'
    },
    {
        'category': 'HARM_CATEGORY_HARASSMENT',
        'threshold': 'OFF'
    },
    {
        'category': 'HARM_CATEGORY_DANGEROUS_CONTENT',
        'threshold': 'OFF'
    },
    {
        'category': 'HARM_CATEGORY_CIVIC_INTEGRITY',
        'threshold': 'BLOCK_NONE'
    }
]
