import pytest
from app.services.ingestion.url_normalizer import URLNormalizer

def test_url_normalization():
    # Test valid domains
    assert URLNormalizer.is_allowed_domain("www.pccoepune.com") is True
    assert URLNormalizer.is_allowed_domain("pccoepune.com") is True
    assert URLNormalizer.is_allowed_domain("computer.pccoepune.com") is True
    
    # Test invalid domains
    assert URLNormalizer.is_allowed_domain("google.com") is False
    assert URLNormalizer.is_allowed_domain("fake-pccoepune.com") is False
    
    # Test normalization logic
    # Absolute URL
    assert URLNormalizer.normalize("https://www.pccoepune.com/about.php") == "https://www.pccoepune.com/about.php"
    
    # URL with fragment
    assert URLNormalizer.normalize("https://www.pccoepune.com/about.php#section1") == "https://www.pccoepune.com/about.php"
    
    # Relative URL with base
    assert URLNormalizer.normalize("/contact.php", "https://www.pccoepune.com/") == "https://www.pccoepune.com/contact.php"
    
    # Invalid external URL returns None
    assert URLNormalizer.normalize("https://www.youtube.com/watch?v=123", "https://www.pccoepune.com/") is None
    
    # Root normalization
    assert URLNormalizer.normalize("https://www.pccoepune.com") == "https://www.pccoepune.com/"

def test_file_type_detection():
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/") == "html"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/page.php") == "html"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/doc.pdf") == "pdf"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/file.docx") == "docx"
    assert URLNormalizer.get_file_type("https://www.pccoepune.com/file.exe") == "unsupported"

def test_category_determination():
    assert URLNormalizer.determine_category("https://www.pccoepune.com/admission.php", "Admissions 2026") == "Admissions"
    assert URLNormalizer.determine_category("https://www.pccoepune.com/computer.php", "Computer Dept") == "Departments"
    assert URLNormalizer.determine_category("https://www.pccoepune.com/random.php", "Unknown") == "College Information"
