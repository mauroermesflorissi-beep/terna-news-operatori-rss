import re
import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from feedgen.feed import FeedGenerator

LIST_URL = "https://www.terna.it/it/sistema-elettrico/pubblicazioni/news-operatori"
BASE = "https://www.terna.it"

# <<< METTI QUI IL TUO FEED URL PUBBLICO (GitHub Pages) >>>
FEED_URL = "https://mauroermesflorissi-beep.github.io/terna-news-operatori-rss/rss.xml"

HEADERS = {
    # User-Agent “crawler” per ottenere spesso HTML già renderizzato
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    r.raise_for_status()
    return r.text

def extract_date(text: str):
    # cerca date tipo 07/01/2026
    for m in re.findall(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text):
        try:
            dt = dateparser.parse(m, dayfirst=True)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def extract_items_from_html(html: str):
    soup = BeautifulSoup(html, "lxml")

    # 1) tentativo: link HTML “normali”
    items = []
    for a in soup.select('a[href*="/it/sistema-elettrico/pubblicazioni/news-operatori/dettaglio/"]'):
        href = a.get("href", "").strip()
        title = a.get_text(" ", strip=True)
        if title and href:
            items.append((title, urljoin(BASE, href)))

    # 2) fallback: JSON-LD (spesso presente per SEO)
    if not items:
        for s in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(s.get_text(strip=True))
            except Exception:
                continue

            # il JSON-LD può essere dict o list
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                # cerca ItemList -> itemListElement -> url/name
                if isinstance(node, dict) and node.get("@type") == "ItemList":
                    for el in node.get("itemListElement", []):
                        if isinstance(el, dict):
                            it = el.get("item") or el
                            if isinstance(it, dict):
                                u = it.get("url")
                                n = it.get("name")
                                if u and n and "/news-operatori/dettaglio/" in u:
                                    items.append((n.strip(), urljoin(BASE, u.strip())))

    # dedup per URL
    seen = set()
    clean = []
    for t, u in items:
        if u not in seen:
            seen.add(u)
            clean.append((t, u))

    return clean

def main():
    html = fetch(LIST_URL)
    clean = extract_items_from_html(html)

    fg = FeedGenerator()
    fg.title("Terna – News Operatori (RSS automatico)")
    fg.link(href=LIST_URL, rel="alternate")
    fg.link(href=FEED_URL, rel="self")
    fg.description("Feed RSS generato automaticamente dalla pagina News Operatori di Terna.")
    fg.language("it")

    now = datetime.now(timezone.utc)

    # Se non troviamo nulla, mettiamo un placeholder (ma SOLO finché non ci sono items)
    if not clean:
        fe = fg.add_entry()
        fe.title("Nessuna news disponibile al momento (feed attivo)")
        fe.link(href=LIST_URL)
        fe.guid("placeholder-" + LIST_URL, permalink=False)
        fe.published(now)
    else:
        for title, url in clean[:50]:
            pub = None
            try:
                detail_text = BeautifulSoup(fetch(url), "lxml").get_text(" ", strip=True)
                pub = extract_date(detail_text)
            except Exception:
                pass

            fe = fg.add_entry()
            fe.title(title)
            fe.link(href=url)
            fe.guid(url, permalink=True)
            fe.published(pub or now)

    fg.rss_file("rss.xml")

if __name__ == "__main__":
    main()
