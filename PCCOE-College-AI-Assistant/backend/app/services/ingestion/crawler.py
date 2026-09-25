import requests
from bs4 import BeautifulSoup
import hashlib
import json
import logging
from typing import Set, List, Dict, Any, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from app.models.document import Document, DocumentVersion
from app.models.enums import StatusEnum
from app.services.ingestion.url_normalizer import URLNormalizer
from app.services.ingestion.ingestion_service import DocumentIngestionService
from app.services.ingestion.storage import LocalStorageService
from app.services.ingestion.file_validator import FileValidator

logger = logging.getLogger(__name__)

class CrawlerConfig:
    def __init__(
        self,
        seed_urls: List[str] = None,
        max_depth: int = 3,
        max_pages: int = 50,
        timeout: int = 10,
        user_agent: str = "Mozilla/5.0 PCCOE-AI-Bot",
        dry_run: bool = False
    ):
        self.seed_urls = seed_urls or ["https://www.pccoepune.com/"]
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.timeout = timeout
        self.user_agent = user_agent
        self.dry_run = dry_run

class PCCOECrawler:
    def __init__(self, db: Session, config: CrawlerConfig):
        self.db = db
        self.config = config
        self.visited: Set[str] = set()
        self.queue: List[Dict[str, Any]] = []
        
        self.storage = LocalStorageService()
        self.validator = FileValidator(allowed_extensions=['pdf', 'docx', 'txt', 'html'], max_size_mb=10)
        self.ingestion_service = DocumentIngestionService(self.db, storage_service=self.storage, file_validator=self.validator)
        
        self.report = {
            "discovered": 0,
            "crawled": 0,
            "imported": 0,
            "skipped": 0,
            "failed": 0,
            "duplicates": 0,
            "errors": 0,
            "urls": []
        }

    def _hash_content(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _extract_links(self, html_bytes: bytes, base_url: str) -> List[str]:
        try:
            soup = BeautifulSoup(html_bytes, 'html.parser')
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                normalized = URLNormalizer.normalize(href, base_url)
                if normalized and URLNormalizer.get_file_type(normalized) != 'unsupported':
                    links.append(normalized)
            return links
        except Exception as e:
            logger.error(f"Error extracting links from {base_url}: {e}")
            return []
            
    def _extract_title(self, html_bytes: bytes, url: str) -> str:
        try:
            soup = BeautifulSoup(html_bytes, 'html.parser')
            if soup.title and soup.title.string:
                return soup.title.string.strip()
        except:
            pass
        return "PCCOE Document"

    def crawl(self):
        logger.info(f"[CRAWLER] Starting crawl with {len(self.config.seed_urls)} seed URLs. Dry run: {self.config.dry_run}")
        
        for seed in self.config.seed_urls:
            normalized = URLNormalizer.normalize(seed)
            if normalized:
                self.queue.append({"url": normalized, "depth": 0})
                self.report["discovered"] += 1
                
        while self.queue and self.report["crawled"] < self.config.max_pages:
            current = self.queue.pop(0)
            url = current["url"]
            depth = current["depth"]
            
            if url in self.visited:
                continue
                
            self.visited.add(url)
            self.report["crawled"] += 1
            
            logger.info(f"[CRAWLER] Crawling URL (Depth {depth}): {url}")
            
            try:
                headers = {'User-Agent': self.config.user_agent}
                response = requests.get(url, headers=headers, timeout=self.config.timeout)
                response.raise_for_status()
                content = response.content
                
                # We only process if it's HTML (for link extraction) or we just ingest PDFs directly if supported
                # The prompt implies we want to discover internal links and prioritize HTML, but we should also skip images/videos
                file_type = URLNormalizer.get_file_type(url)
                if file_type == 'unsupported':
                    logger.info(f"[CRAWLER] Skipped URL (Unsupported type): {url}")
                    self.report["skipped"] += 1
                    self.report["urls"].append({"url": url, "status": "skipped", "reason": "unsupported type"})
                    continue
                
                title = self._extract_title(content, url) if file_type == 'html' else f"Document: {url.split('/')[-1]}"
                
                content_hash = self._hash_content(content)
                
                if self.config.dry_run:
                    logger.info(f"[CRAWLER] [DRY-RUN] Would import URL: {url} (Title: {title}, Hash: {content_hash})")
                    self.report["imported"] += 1
                    self.report["urls"].append({"url": url, "status": "dry-run-imported", "title": title})
                else:
                    is_duplicate = self._ingest_to_db(url, title, content, content_hash)
                    if is_duplicate:
                        logger.info(f"[CRAWLER] Duplicate URL (Hash unchanged): {url}")
                        self.report["duplicates"] += 1
                        self.report["urls"].append({"url": url, "status": "duplicate"})
                    else:
                        logger.info(f"[CRAWLER] Imported URL: {url}")
                        self.report["imported"] += 1
                        self.report["urls"].append({"url": url, "status": "imported", "title": title})

                # Extract links only if HTML and depth allows
                if file_type == 'html' and depth < self.config.max_depth:
                    links = self._extract_links(content, url)
                    for link in set(links):
                        if link not in self.visited and not any(q['url'] == link for q in self.queue):
                            self.queue.append({"url": link, "depth": depth + 1})
                            self.report["discovered"] += 1
                            logger.info(f"[CRAWLER] Discovered URL: {link}")

            except requests.exceptions.RequestException as e:
                logger.error(f"[CRAWLER] Failed URL (Connection/HTTP error): {url} -> {e}")
                self.report["failed"] += 1
                self.report["urls"].append({"url": url, "status": "failed", "error": str(e)})
            except Exception as e:
                logger.error(f"[CRAWLER] Error processing URL: {url} -> {e}")
                self.report["errors"] += 1
                self.report["urls"].append({"url": url, "status": "error", "error": str(e)})
                
        logger.info(f"[CRAWLER] Completed. Discovered: {self.report['discovered']}, Crawled: {self.report['crawled']}, Imported: {self.report['imported']}, Duplicates: {self.report['duplicates']}, Skipped: {self.report['skipped']}, Failed/Errors: {self.report['failed'] + self.report['errors']}")
        return self.report

    def _ingest_to_db(self, url: str, title: str, content: bytes, content_hash: str) -> bool:
        """
        Returns True if it's an unchanged duplicate, False if it was newly created/updated.
        """
        # Check if Document already exists
        doc = self.db.query(Document).filter(Document.source == url).first()
        
        category = URLNormalizer.determine_category(url, title)
        
        if not doc:
            doc = Document(
                title=title,
                description=f"Official content crawled from {url}",
                category=category,
                source=url,
                status=StatusEnum.DRAFT
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)
        else:
            # Check latest version
            latest_version = self.db.query(DocumentVersion)\
                .filter(DocumentVersion.document_id == doc.id)\
                .order_by(DocumentVersion.version_number.desc())\
                .first()
                
            if latest_version and latest_version.content_hash == content_hash:
                return True # Exact duplicate
                
        # Create new version
        latest_version = self.db.query(DocumentVersion)\
            .filter(DocumentVersion.document_id == doc.id)\
            .order_by(DocumentVersion.version_number.desc())\
            .first()
        next_version_num = latest_version.version_number + 1 if latest_version else 1
        
        ver = DocumentVersion(
            document_id=doc.id,
            version_number=next_version_num,
            status=StatusEnum.DRAFT,
            content_hash=content_hash
        )
        self.db.add(ver)
        self.db.commit()
        self.db.refresh(ver)
        
        # Determine filename based on content type/url
        file_type = URLNormalizer.get_file_type(url)
        if file_type == 'unsupported': file_type = 'html'
        filename = f"crawled_{doc.id}_v{ver.version_number}.{file_type}"
        
        # Let IngestionService handle the rest (saving, extracting, chunking, embedding)
        # We pass file_content and filename, it handles the storage saving and updates the version.
        self.ingestion_service.process_document_version(
            version_id=ver.id,
            filename=filename,
            file_content=content
        )
        
        return False
