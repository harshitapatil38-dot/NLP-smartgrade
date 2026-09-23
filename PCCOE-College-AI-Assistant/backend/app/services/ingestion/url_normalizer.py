import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Optional, Tuple

class URLNormalizer:
    ALLOWED_DOMAINS = {"www.pccoepune.com", "pccoepune.com"}
    ALLOWED_SUBDOMAIN_PATTERNS = [re.compile(r".*\.pccoepune\.com$")]
    
    SUPPORTED_EXTENSIONS = {
        'html': 'html', 'htm': 'html', 'php': 'html',
        'pdf': 'pdf',
        'doc': 'docx', 'docx': 'docx',
        'txt': 'txt'
    }

    @classmethod
    def is_allowed_domain(cls, domain: str) -> bool:
        if not domain:
            return False
        domain = domain.lower()
        if domain in cls.ALLOWED_DOMAINS:
            return True
        for pattern in cls.ALLOWED_SUBDOMAIN_PATTERNS:
            if pattern.match(domain):
                return True
        return False

    @classmethod
    def normalize(cls, url: str, base_url: str = "") -> Optional[str]:
        """
        Normalizes a URL by resolving it against a base_url (if relative),
        removing fragments, and ensuring it belongs to an allowed domain.
        Returns the normalized URL or None if it's invalid/external.
        """
        if not url:
            return None

        # Resolve relative URLs
        if base_url:
            resolved_url = urljoin(base_url, url)
        else:
            resolved_url = url

        parsed = urlparse(resolved_url)
        
        # We only support http and https
        if parsed.scheme not in ('http', 'https'):
            return None

        domain = parsed.netloc.split(':')[0]  # Remove port if any
        if not cls.is_allowed_domain(domain):
            return None

        # Remove fragment and normalize trailing slash if it's just a root or directory
        # Also clean up the URL
        path = parsed.path
        if not path:
            path = "/"
            
        # Reconstruct URL without fragment
        normalized = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ''))
        return normalized

    @classmethod
    def get_file_type(cls, url: str) -> str:
        """
        Returns the supported file type (e.g. 'html', 'pdf', 'docx', 'txt') or 'unsupported'
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        if not path or path.endswith('/'):
            return 'html'
            
        ext = path.split('.')[-1]
        if ext in cls.SUPPORTED_EXTENSIONS:
            return cls.SUPPORTED_EXTENSIONS[ext]
            
        # If there's no extension, it's typically an HTML route
        if '.' not in path.split('/')[-1]:
            return 'html'
            
        return 'unsupported'

    @classmethod
    def determine_category(cls, url: str, title: str) -> str:
        """
        Attempts to determine category based on URL path and title.
        """
        url_lower = url.lower()
        title_lower = title.lower() if title else ""
        
        if "admission" in url_lower or "admission" in title_lower:
            return "Admissions"
        elif "department" in url_lower or "computer" in url_lower or "mechanical" in url_lower or "civil" in url_lower or "it" in url_lower or "entc" in url_lower or "mca" in url_lower:
            return "Departments"
        elif "club" in url_lower or "nss" in url_lower or "art" in url_lower:
            return "Clubs/student activities"
        elif "library" in url_lower:
            return "Library"
        elif "contact" in url_lower:
            return "Contact information"
        elif "exam" in url_lower:
            return "Examinations"
        elif "facilit" in url_lower or "hostel" in url_lower:
            return "Facilities"
        elif "scholarship" in url_lower:
            return "Student services"
        elif "welfare" in url_lower or "student" in url_lower:
            return "Student services"
        elif "syllab" in url_lower or "program" in url_lower or "course" in url_lower:
            return "Programs/courses"
        elif "placement" in url_lower or "recruit" in url_lower:
            return "Placements"
        
        return "College Information"
