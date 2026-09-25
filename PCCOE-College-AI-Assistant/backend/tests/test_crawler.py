import pytest
import requests
from app.services.ingestion.crawler import PCCOECrawler, CrawlerConfig
from app.services.ingestion.url_normalizer import URLNormalizer
from app.models.document import Document, DocumentVersion

def test_url_normalization():
    # URL normalization
    base = "https://www.pccoepune.com"
    
    assert URLNormalizer.normalize("https://www.pccoepune.com/") == "https://www.pccoepune.com/"
    assert URLNormalizer.normalize("/about.php", base) == "https://www.pccoepune.com/about.php"
    assert URLNormalizer.normalize("about.php#section", base) == "https://www.pccoepune.com/about.php"
    
    # External rejection
    assert URLNormalizer.normalize("https://google.com", base) is None
    assert URLNormalizer.normalize("http://www.google.com/test", base) is None
    
    # Fragments removed
    assert URLNormalizer.normalize("https://www.pccoepune.com/admission.php#fees") == "https://www.pccoepune.com/admission.php"

def test_unsupported_extensions():
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/image.jpg") == "unsupported"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/video.mp4") == "unsupported"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/script.js") == "unsupported"
    
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/doc.pdf") == "pdf"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/page.html") == "html"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/page.php") == "html"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/") == "html"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/about") == "html"

def test_crawler_dry_run(db_session, monkeypatch):
    class MockResponse:
        def __init__(self, content):
            self.content = content
        def raise_for_status(self):
            pass

    # Provide a page with an internal link
    def mock_get(url, **kwargs):
        if url == "https://www.pccoepune.com/":
            return MockResponse(b"<html><body><a href='/internal.php'>Internal</a><a href='https://google.com'>External</a></body></html>")
        elif url == "https://www.pccoepune.com/internal.php":
            return MockResponse(b"<html><body>Internal page</body></html>")
        return MockResponse(b"")

    monkeypatch.setattr(requests, "get", mock_get)

    config = CrawlerConfig(
        seed_urls=["https://www.pccoepune.com/"],
        max_depth=1,
        max_pages=10,
        dry_run=True
    )
    
    crawler = PCCOECrawler(db_session, config)
    report = crawler.crawl()
    
    # 2 pages discovered and crawled
    assert report["discovered"] == 2
    assert report["crawled"] == 2
    assert report["imported"] == 2 # "imported" count increments in dry-run, but no DB changes occur
    
    # Verify no DB records created
    docs = db_session.query(Document).all()
    assert len(docs) == 0

def test_crawler_max_depth(db_session, monkeypatch):
    class MockResponse:
        def __init__(self, content):
            self.content = content
        def raise_for_status(self):
            pass

    # Chain of links
    def mock_get(url, **kwargs):
        if url == "https://www.pccoepune.com/0":
            return MockResponse(b"<html><body><a href='/1'>Next</a></body></html>")
        elif url == "https://www.pccoepune.com/1":
            return MockResponse(b"<html><body><a href='/2'>Next</a></body></html>")
        elif url == "https://www.pccoepune.com/2":
            return MockResponse(b"<html><body><a href='/3'>Next</a></body></html>")
        return MockResponse(b"<html><body>End</body></html>")

    monkeypatch.setattr(requests, "get", mock_get)

    # Max depth 1 means it crawls seed (depth 0) and the links on seed (depth 1), but doesn't follow links on depth 1
    config = CrawlerConfig(
        seed_urls=["https://www.pccoepune.com/0"],
        max_depth=1,
        max_pages=10,
        dry_run=True
    )
    
    crawler = PCCOECrawler(db_session, config)
    report = crawler.crawl()
    
    # Discovers /0 and /1. Crawls /0 and /1. Stops before discovering /2 because /1 was processed at depth 1.
    assert report["discovered"] == 2
    assert report["crawled"] == 2
    assert report["urls"][-1]["url"] == "https://www.pccoepune.com/1"

def test_crawler_max_pages(db_session, monkeypatch):
    class MockResponse:
        def __init__(self, content):
            self.content = content
        def raise_for_status(self):
            pass

    def mock_get(url, **kwargs):
        # A page with 5 links
        return MockResponse(b"<html><body><a href='/1'>1</a><a href='/2'>2</a><a href='/3'>3</a><a href='/4'>4</a><a href='/5'>5</a></body></html>")

    monkeypatch.setattr(requests, "get", mock_get)

    config = CrawlerConfig(
        seed_urls=["https://www.pccoepune.com/"],
        max_depth=1,
        max_pages=3, # Limit to 3 pages
        dry_run=True
    )
    
    crawler = PCCOECrawler(db_session, config)
    report = crawler.crawl()
    
    assert report["crawled"] == 3
