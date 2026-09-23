import requests
from bs4 import BeautifulSoup
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.services.ingestion.url_normalizer import URLNormalizer
url = 'https://www.pccoepune.com/'
content = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).content
soup = BeautifulSoup(content, 'html.parser')
links = soup.find_all(['a', 'area'], href=True)
for link in links[:10]:
    href = link.get('href')
    norm = URLNormalizer.normalize(href, base_url=url)
    print(f"HREF: {href} -> NORM: {norm}")
