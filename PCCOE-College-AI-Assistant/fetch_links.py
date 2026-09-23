import urllib.request
import re

try:
    with urllib.request.urlopen('https://www.pccoepune.com/') as response:
        html = response.read().decode('utf-8')
        links = set(re.findall(r'href=[\'"]?(https://www\.pccoepune\.com/[^\'" >]+)', html))
        for link in sorted(list(links))[:30]:
            print(link)
except Exception as e:
    print(e)
