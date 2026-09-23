import os
import sys
import argparse
import requests
import urllib.robotparser
import hashlib
import json
import time
from bs4 import BeautifulSoup
from collections import deque
from typing import Dict, List, Set, Any

# Add the backend directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database import SessionLocal
from app.models.department import Department
from app.models.document import Document, DocumentVersion
from app.models.enums import StatusEnum
from app.services.ingestion.url_normalizer import URLNormalizer
from app.services.ingestion.storage import LocalStorageService

# User Agent for our crawler
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PCCOE-College-AI-Assistant/1.0"

class PCCOECrawler:
    def __init__(self, start_url: str, max_pages: int, timeout: int, delay: float):
        self.start_url = start_url
        self.max_pages = max_pages
        self.timeout = timeout
        self.delay = delay
        
        self.visited_urls: Set[str] = set()
        self.to_visit_urls = deque([start_url])
        
        self.storage = LocalStorageService()
        
        self.rp = urllib.robotparser.RobotFileParser()
        self.robot_fetched = False
        
        self.report = {
            "root": start_url,
            "pages_discovered": 0,
            "pages_successfully_fetched": 0,
            "pages_failed": 0,
            "pdfs_discovered": 0,
            "pdfs_downloaded": 0,
            "docx_discovered": 0,
            "docx_downloaded": 0,
            "duplicates_skipped": 0,
            "unchanged_documents": 0,
            "new_documents": 0,
            "new_versions": 0,
            "external_links_skipped": 0,
            "failed_urls": [],
            "categories": {}
        }
        
        self.db = SessionLocal()
        
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def fetch_robots_txt(self, base_url: str):
        if not self.robot_fetched:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
                
                response = self.session.get(robots_url, timeout=self.timeout)
                if response.status_code == 200:
                    self.rp.parse(response.text.splitlines())
            except Exception as e:
                print(f"[WARN] Failed to fetch robots.txt: {e}")
            finally:
                self.robot_fetched = True

    def can_fetch(self, url: str) -> bool:
        if not self.robot_fetched:
            self.fetch_robots_txt(url)
        return self.rp.can_fetch(USER_AGENT, url)
        
    def fetch_with_retry(self, url: str, max_retries=3) -> requests.Response:
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(self.delay * (attempt + 1))
        raise Exception("Fetch failed after retries")

    def hash_content(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
        
    def process_document(self, url: str, content: bytes, file_type: str, title: str = ""):
        content_hash = self.hash_content(content)
        category = URLNormalizer.determine_category(url, title)
        
        if not title:
            title = url.split('/')[-1] or "PCCOE Page"
            
        doc = self.db.query(Document).filter(Document.source == url).first()
        
        if doc:
            # Check latest version
            latest_version = self.db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).order_by(DocumentVersion.version_number.desc()).first()
            if latest_version and latest_version.content_hash == content_hash:
                print(f"  [NO_CHANGE] Content identical for {url}")
                self.report["unchanged_documents"] += 1
                return

            print(f"  [UPDATED] New content for existing document {url}")
            self.report["new_versions"] += 1
            next_version_num = latest_version.version_number + 1 if latest_version else 1
            
            # If creating a new version, old should be archived manually or via workflow? 
            # The workflow says just create new version in DRAFT. The DB keeps old versions.
        else:
            print(f"  [CREATED] New document for {url}")
            self.report["new_documents"] += 1
            doc = Document(
                title=title[:255],
                description=f"Auto-crawled from {url}",
                category=category,
                source=url,
                status=StatusEnum.DRAFT
            )
            self.db.add(doc)
            self.db.flush()
            next_version_num = 1
            
            self.report["categories"][category] = self.report["categories"].get(category, 0) + 1

        ver = DocumentVersion(
            document_id=doc.id,
            version_number=next_version_num,
            status=StatusEnum.DRAFT,
            content_hash=content_hash
        )
        self.db.add(ver)
        self.db.flush()
        
        # Save file
        filename = f"crawl_{doc.id}_v{ver.version_number}.{file_type}"
        file_path = self.storage.save_file(filename, content)
        ver.file_path = file_path
        
        self.db.commit()

    def run(self):
        print(f"Starting crawl at {self.start_url} (Max Pages: {self.max_pages})")
        
        pages_processed = 0
        
        while self.to_visit_urls and pages_processed < self.max_pages:
            url = self.to_visit_urls.popleft()
            
            if url in self.visited_urls:
                continue
                
            self.visited_urls.add(url)
            self.report["pages_discovered"] += 1
            
            if not self.can_fetch(url):
                print(f"  [SKIPPED] robots.txt blocked: {url}")
                continue
                
            print(f"[{pages_processed+1}/{self.max_pages}] Fetching: {url}")
            
            try:
                response = self.fetch_with_retry(url)
                content = response.content
                content_type = response.headers.get('Content-Type', '')
                
                self.report["pages_successfully_fetched"] += 1
                
                file_type = URLNormalizer.get_file_type(url)
                title = ""
                
                print(f"DEBUG: Content type is {content_type}, length is {len(content)}")
                
                if 'text/html' in content_type:
                    soup = BeautifulSoup(content, 'html.parser')
                    if soup.title:
                        title = soup.title.string.strip()
                        
                    # Extract internal links
                    for link in soup.find_all(['a', 'area'], href=True):
                        href = link.get('href')
                        normalized_href = URLNormalizer.normalize(href, base_url=url)
                        
                        if normalized_href:
                            # It's an internal allowed domain
                            if normalized_href not in self.visited_urls:
                                link_type = URLNormalizer.get_file_type(normalized_href)
                                if link_type == 'pdf':
                                    self.report["pdfs_discovered"] += 1
                                elif link_type == 'docx':
                                    self.report["docx_discovered"] += 1
                                    
                                if normalized_href not in self.to_visit_urls:
                                    self.to_visit_urls.append(normalized_href)
                                    print(f"DEBUG ADDED: {normalized_href}")
                        else:
                            self.report["external_links_skipped"] += 1
                            
                    print(f"DEBUG: Found {len(self.to_visit_urls)} urls to visit")
                    
                    # Process HTML Document
                    self.process_document(url, content, 'html', title)
                    
                else:
                    # Non-HTML files (PDF, DOCX)
                    if file_type == 'pdf':
                        self.report["pdfs_downloaded"] += 1
                    elif file_type == 'docx':
                        self.report["docx_downloaded"] += 1
                        
                    self.process_document(url, content, file_type, title)
                    
            except Exception as e:
                print(f"  [ERROR] Failed to fetch {url}: {e}")
                self.report["pages_failed"] += 1
                self.report["failed_urls"].append({"url": url, "error": str(e)})
                
            pages_processed += 1
            time.sleep(self.delay)

        self.db.close()
        self.generate_report()
        
    def generate_report(self):
        print("\n" + "="*40)
        print("PCCOE KNOWLEDGE CRAWL REPORT")
        print("="*40)
        print(f"Root: {self.report['root']}")
        print(f"Pages discovered: {self.report['pages_discovered']}")
        print(f"Pages successfully fetched: {self.report['pages_successfully_fetched']}")
        print(f"Pages failed: {self.report['pages_failed']}")
        print(f"PDFs discovered: {self.report['pdfs_discovered']}")
        print(f"PDFs downloaded: {self.report['pdfs_downloaded']}")
        print(f"DOCX discovered: {self.report['docx_discovered']}")
        print(f"DOCX downloaded: {self.report['docx_downloaded']}")
        print(f"Duplicates skipped (Unchanged): {self.report['unchanged_documents']}")
        print(f"New documents: {self.report['new_documents']}")
        print(f"New versions: {self.report['new_versions']}")
        print(f"External links skipped: {self.report['external_links_skipped']}")
        print("\nCategories discovered:")
        for cat, count in self.report["categories"].items():
            print(f"  {cat}: {count}")
        print("="*40)
        
        with open("crawl_report.json", "w") as f:
            json.dump(self.report, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PCCOE Knowledge Crawler")
    parser.add_argument("--max-pages", type=int, default=1000, help="Maximum pages to crawl")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests in seconds")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout in seconds")
    args = parser.parse_args()
    
    crawler = PCCOECrawler(
        start_url="https://www.pccoepune.com/",
        max_pages=args.max_pages,
        timeout=args.timeout,
        delay=args.delay
    )
    crawler.run()
