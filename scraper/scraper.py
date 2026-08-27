import time
import logging
import html
import feedparser
import requests
from bs4 import BeautifulSoup
from config import SITES, ARTICLES_PER_SITE
from database import insert_article


def clean_text(s):
    s = html.unescape(html.unescape(str(s or "")))
    return " ".join(s.split())

log = logging.getLogger("scraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_full_text(url, max_chars=8000):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        text = "\n\n".join(p for p in paragraphs if len(p) > 60)
        return text[:max_chars]
    except Exception as e:
        log.warning("full-text fetch failed for %s: %s", url, e)
        return ""


def scrape_site(name, rss_url, per_site, lang="en"):
    feed = feedparser.parse(rss_url)
    added = 0
    for entry in feed.entries[:per_site]:
        url = entry.get("link")
        title = clean_text(entry.get("title", ""))
        if not url or not title:
            continue
        summary_html = entry.get("summary", "")
        summary_text = clean_text(BeautifulSoup(summary_html, "html.parser").get_text())
        full_text = fetch_full_text(url)
        body = full_text or summary_text
        image_url = None
        media = entry.get("media_content") or entry.get("media_thumbnail")
        if media:
            image_url = media[0].get("url")
        if len(body) < 200:
            continue
        if insert_article(name, url, title, body, image_url, lang):
            added += 1
        time.sleep(1)
    log.info("%s: %d new articles", name, added)
    return added


def collect_all(lang=None):
    total = 0
    for site in SITES:
        if lang and site.get("lang", "en") != lang:
            continue
        try:
            total += scrape_site(site["name"], site["rss"], ARTICLES_PER_SITE, site.get("lang", "en"))
        except Exception as e:
            log.error("site %s failed: %s", site["name"], e)
        time.sleep(2)
    return total
