import os
import sys
import argparse
import json
import logging

# Add the backend directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database import SessionLocal
from app.services.ingestion.crawler import PCCOECrawler, CrawlerConfig

logging.basicConfig(level=logging.INFO, format='%(message)s')

def main():
    parser = argparse.ArgumentParser(description="PCCOE Knowledge Base Crawler")
    parser.add_argument("--seed", type=str, help="Comma-separated list of seed URLs", default="https://www.pccoepune.com/")
    parser.add_argument("--max-depth", type=int, default=3, help="Maximum recursion depth")
    parser.add_argument("--max-pages", type=int, default=50, help="Maximum number of pages to crawl")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP request timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Crawl without saving to database")
    
    args = parser.parse_args()
    
    seeds = [s.strip() for s in args.seed.split(",") if s.strip()]
    
    config = CrawlerConfig(
        seed_urls=seeds,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        timeout=args.timeout,
        dry_run=args.dry_run
    )
    
    db = SessionLocal()
    
    print("=" * 60)
    print("PCCOE KNOWLEDGE CRAWLER")
    print("=" * 60)
    print(f"Seeds: {seeds}")
    print(f"Max Depth: {config.max_depth}")
    print(f"Max Pages: {config.max_pages}")
    print(f"Dry Run: {config.dry_run}")
    print("-" * 60)
    
    crawler = PCCOECrawler(db, config)
    try:
        report = crawler.crawl()
    finally:
        db.close()
        
    print("-" * 60)
    print("CRAWL REPORT SUMMARY")
    print("-" * 60)
    print(f"Pages Discovered: {report['discovered']}")
    print(f"Pages Crawled:    {report['crawled']}")
    print(f"Pages Imported:   {report['imported']}")
    print(f"Duplicates:       {report['duplicates']}")
    print(f"Pages Skipped:    {report['skipped']}")
    print(f"Failed/Errors:    {report['failed'] + report['errors']}")
    
    # Save full report
    report_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crawl_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"\nDetailed crawl report saved to: {report_path}")

if __name__ == "__main__":
    main()
