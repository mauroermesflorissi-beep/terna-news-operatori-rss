import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from feedgen.feed import FeedGenerator

LIST_URL = "https://www.terna.it/it/sistema-elettrico/pubblicazioni/news-operatori"
BASE = "https://www.terna.it"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RSSBot/1.0)",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def extract_date(text: str):
    for m in re.findall(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text):
        try:
            dt = dateparser.parse(m, dayfirst=True)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def main():
    soup = BeautifulSoup(fetch(LIST_URL), "lxml")

    items = []
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        title = a.get_text(" ", strip=True)
        if (
            title
            and "/it/sistema-elettrico/pubblicazioni/news-operatori/dettaglio/" in href
        ):
            items.append((title, urljoin(BASE, href)))

    seen = set()
    clean = []
    for t, u in items:
        if u not in seen:
            seen.add(u)
            clean.append((t, u))

    fg = FeedGenerator()
    fg.title("Terna – News Operatori (RSS automatico)")
    fg.link(href=LIST_URL, rel="alternate")
    fg.link(href="rss.xml", rel="self")
    fg.description("Feed RSS generato automaticamente dalla pagina News Operatori di Terna.")
    fg.language("it")

    now = datetime.now(timezone.utc)

        # Se non ci sono news, aggiungiamo un item "segnaposto" così Inoreader può agganciare il feed
    if not clean:
        fe = fg.add_entry()
        fe.title("Nessuna news disponibile al momento (feed attivo)")
        fe.link(href=LIST_URL)
        fe.guid("placeholder-" + LIST_URL, permalink=False)
        fe.published(now)

    for title, url in clean[:50]:
        pub = None
        try:
            text = BeautifulSoup(fetch(url), "lxml").get_text(" ", strip=True)
            pub = extract_date(text)
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
