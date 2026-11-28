# Extract heritage articles using site URL patterns and fallback selectors.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Collect heritage news from configured cultural websites for knowledge ingestion."""
import scrapy
from scrapy.http import Request
from urllib.parse import urljoin
import re
from datetime import datetime


class ICHNewsSpider(scrapy.Spider):
    """General intangible-cultural-heritage news spider."""
    
    name = 'ich_news'
    allowed_domains = ['ihchina.cn', 'sichuan.gov.cn', 'wlt.sc.gov.cn']
    start_urls = [
        'https://www.ihchina.cn/',  # China Intangible Cultural Heritage website.
        'http://wlt.sc.gov.cn/',    # Sichuan Provincial Department of Culture and Tourism.
    ]
    
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 3,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    def parse(self, response):
        """Extract candidate news links from the landing page."""
        # Extract links from the news list.
        news_links = response.css('a::attr(href)').getall()
        
        for link in news_links:
            # Resolve the absolute URL.
            url = urljoin(response.url, link)
            
            # Filter out non-news links so only article-like URLs are followed.
            if self.is_news_url(url):
                yield Request(
                    url=url,
                    callback=self.parse_news,
                    meta={'url': url}
                )
    
    def is_news_url(self, url: str) -> bool:
        """Determine whether a URL resembles a news article."""
        # Exclude static resources.
        if any(ext in url for ext in ['.css', '.js', '.png', '.jpg', '.gif', '.pdf']):
            return False
        
        # Match news URL patterns.
        patterns = [
            r'/news/',
            r'/article/',
            r'/detail/',
            r'/content/',
            r'新闻',
            r'非遗',
            r'传承',
        ]
        
        return any(re.search(pattern, url) for pattern in patterns)
    
    def parse_news(self, response):
        """Parse a news detail page into structured fields."""
        try:
            # Extract the title.
            title = self.extract_title(response)
            
            # Extract the body.
            content = self.extract_content(response)
            
            # Extract the publication date.
            date = self.extract_date(response)
            
            # Extract the category.
            category = self.extract_category(response)
            
            if title and content:
                yield {
                    'title': title.strip(),
                    'content': content.strip(),
                    'date': date,
                    'category': category,
                    'url': response.meta.get('url', response.url),
                    'source': '非遗数据爬虫',
                    'crawl_time': datetime.now().isoformat(),
                }
                
                self.logger.info(f"成功抓取新闻: {title}")
        
        except Exception as e:
            self.logger.error(f"解析新闻失败 {response.url}: {e}")
    
    def extract_title(self, response) -> str:
        """Extract the article title."""
        selectors = [
            'h1::text',
            '.title::text',
            '.article-title::text',
            '.news-title::text',
            'title::text',
        ]
        
        for selector in selectors:
            title = response.css(selector).get()
            if title and title.strip():
                return title.strip()
        
        return ""
    
    def extract_content(self, response) -> str:
        """Extract and normalize article body text."""
        # Try multiple body selectors.
        content_selectors = [
            '.content p::text',
            '.article-content p::text',
            '.news-content p::text',
            '.detail-content p::text',
            'article p::text',
        ]
        
        paragraphs = []
        # Selectors are tried in order; the first one yielding a real article wins.
        for selector in content_selectors:
            paragraphs = response.css(selector).getall()
            if paragraphs and len(paragraphs) > 3:  # Use this selector when it yields more than three paragraphs.
                break
        
        # Fall back to all text when no suitable paragraphs are found.
        if not paragraphs:
            body = response.css('body').get()
            if body:
                # Remove script and style elements.
                body = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', body, flags=re.DOTALL)
                paragraphs = [re.sub(r'<[^>]+>', '', p).strip() 
                            for p in body.split('\n') if p.strip()]
        
        # Clean and merge paragraphs.
        content = '\n\n'.join([p.strip() for p in paragraphs if p.strip() and len(p) > 10])
        
        return content
    
    def extract_date(self, response) -> str:
        """Extract the publication date."""
        selectors = [
            '.date::text',
            '.publish-time::text',
            '.time::text',
            '[datetime]::attr(datetime)',
        ]
        
        for selector in selectors:
            date = response.css(selector).get()
            if date:
                # Normalize by dropping everything except digits and Chinese date markers.
                date = re.sub(r'[^\d\-年月日]', '', date)
                return date.strip()
        
        return datetime.now().strftime('%Y-%m-%d')
    
    def extract_category(self, response) -> str:
        """Extract the article category."""
        selectors = [
            '.category::text',
            '.tag::text',
            '.type::text',
        ]
        
        for selector in selectors:
            category = response.css(selector).get()
            if category:
                return category.strip()
        
        return "非遗新闻"


class QiangHeritageSpider(scrapy.Spider):
    """Spider focused on Qiang heritage topics."""
    
    name = 'qiang_heritage'
    allowed_domains = ['ihchina.cn', 'sichuan.gov.cn']
    start_urls = [
        'https://www.ihchina.cn/',  # China Intangible Cultural Heritage website.
    ]
    
    custom_settings = {
        'DOWNLOAD_DELAY': 3,
        'CONCURRENT_REQUESTS': 2,
    }
    
    def parse(self, response):
        """Build search requests for Qiang-related heritage content."""
        # Search keywords.
        keywords = ['羌绣', '羌笛', '羌族', '羌年', '羌族碉楼']
        
        for keyword in keywords:
            # Construct the search URL; adapt this to the website's actual search interface.
            search_url = f"{response.url}?search={keyword}"
            yield Request(
                url=search_url,
                callback=self.parse_search_results,
                meta={'keyword': keyword}
            )
    
    def parse_search_results(self, response):
        """Parse search results and follow matching links."""
        # Extract relevant links.
        links = response.css('a::attr(href)').getall()
        
        for link in links:
            url = urljoin(response.url, link)
            
            # Check for matching keywords.
            if any(keyword in url for keyword in ['羌', 'qiang']):
                yield Request(
                    url=url,
                    callback=self.parse_news,
                    meta={'url': url}
                )
    
    def parse_news(self, response):
        """Reuse the news article parsing implementation."""
        spider = ICHNewsSpider()
        yield from spider.parse_news(response)
