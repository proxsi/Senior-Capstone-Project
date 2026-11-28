# Configure Scrapy throttling, pipelines, logging, and exports.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Scrapy project settings: request throttling, item pipelines, logging, and JSON exports."""
# Scrapy settings for crawler project

BOT_NAME = 'qiang_heritage_crawler'

SPIDER_MODULES = ['crawler.spiders']
NEWSPIDER_MODULE = 'crawler.spiders'

# Respect robots.txt rules.
ROBOTSTXT_OBEY = False

# Configure the User-Agent.
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Delay downloads to reduce server load and blocking.
DOWNLOAD_DELAY = 2

# Limit concurrent requests.
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# Download timeout.
DOWNLOAD_TIMEOUT = 30

# Retry settings.
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Enable processing pipelines; lower numbers run first: validate, deduplicate, then ingest.
ITEM_PIPELINES = {
    'crawler.pipelines.DataValidationPipeline': 100,
    'crawler.pipelines.DeduplicationPipeline': 200,
    'crawler.pipelines.ICHDataPipeline': 300,
}

# Logging settings.
LOG_LEVEL = 'INFO'
LOG_FILE = 'logs/crawler.log'

# Downloader middleware.
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
}

# Export settings.
FEED_FORMAT = 'json'
FEED_URI = 'data/crawled_data_%(time)s.json'

# Automatic request throttling.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# HTTP cache settings.
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400
HTTPCACHE_DIR = 'data/httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 408, 429]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'
