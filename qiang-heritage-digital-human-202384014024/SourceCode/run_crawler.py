# Command-line launcher for the heritage Scrapy spiders.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Command-line launcher for Scrapy heritage collection and knowledge ingestion."""
import os
import sys
import subprocess
import argparse
from datetime import datetime


def run_spider(spider_name: str, output_dir: str = 'data'):
    """Run spider_name (ich_news or qiang_heritage) and export results into output_dir."""
    # Ensure the output directory exists.
    os.makedirs(output_dir, exist_ok=True)
    
    # Build the Scrapy command.
    cmd = [
        'scrapy', 'crawl', spider_name,
        '-o', f'{output_dir}/{spider_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
        '-L', 'INFO'
    ]
    
    print(f"{'='*60}")
    print(f"启动爬虫: {spider_name}")
    print(f"输出目录: {output_dir}")
    print(f"{'='*60}")
    
    try:
        # Run the spider.
        result = subprocess.run(cmd, check=True)
        print(f"\n爬虫 {spider_name} 运行完成!")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"\n爬虫运行失败: {e}")
        return e.returncode
    except FileNotFoundError:
        print("\n错误: Scrapy未安装，请先运行: pip install scrapy")
        return 1


def main():
    """Parse command-line options and launch the selected spiders."""
    parser = argparse.ArgumentParser(description='羌智传承非遗问答系统 - 知识库自动更新爬虫')
    parser.add_argument(
        'spider',
        choices=['ich_news', 'qiang_heritage', 'all'],
        help='爬虫名称'
    )
    parser.add_argument(
        '-o', '--output',
        default='data',
        help='输出目录 (默认: data)'
    )
    
    args = parser.parse_args()
    
    if args.spider == 'all':
        # The "all" option runs both spiders one after the other in a fixed order.
        spiders = ['ich_news', 'qiang_heritage']
        for spider in spiders:
            run_spider(spider, args.output)
    else:
        run_spider(args.spider, args.output)


if __name__ == '__main__':
    main()
