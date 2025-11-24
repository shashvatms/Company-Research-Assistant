import requests
from bs4 import BeautifulSoup

def scrape_url(url):
    try:
        headers = {"User-Agent": "ResearchAgent/1.0"}
        r = requests.get(url, headers=headers, timeout=8)
        html = r.text

        soup = BeautifulSoup(html, "html.parser")
        for s in soup(["script", "style", "noscript"]):
            s.decompose()

        text = " ".join(p.get_text(strip=True) for p in soup.find_all(["p", "li"]))

        return {"url": url, "text": text[:3000]}
    except:
        return {"url": url, "text": ""}
