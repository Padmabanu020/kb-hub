import json
import os
import re
import threading

import requests
from bs4 import BeautifulSoup
from django.conf import settings

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}
# Set SCRAPE_BROWSER=1 in .env (and install playwright) to retry blocked / JavaScript-only pages in a real browser.
USE_BROWSER = os.environ.get("SCRAPE_BROWSER", "0") == "1"
_browser_slots = threading.Semaphore(2)
DROP = ["script", "style", "noscript", "svg", "iframe", "nav", "footer", "form", "template"]
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCK = HEADINGS | {"p", "li", "td", "th", "dt", "dd", "blockquote", "div", "section",
                    "article", "tr", "ul", "ol", "table", "address", "figcaption"}
CANDIDATES = HEADINGS | {"p", "li", "td", "th", "dt", "dd", "blockquote", "div", "address", "figcaption"}


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\x00", " ")).strip()


def _jsonld(soup):
    items = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                if "@graph" in d:
                    stack.extend(d["@graph"])
                items.append(d)
            elif isinstance(d, list):
                stack.extend(d)
    return items


def parse_html(html, url=""):
    soup = BeautifulSoup(html, "html.parser")
    meta = {}
    for m in soup.find_all("meta"):
        key = (m.get("name") or m.get("property") or "").lower()
        if key in {"description", "keywords", "author", "og:title", "og:description",
                   "og:site_name", "og:type", "og:image", "twitter:title"} and m.get("content"):
            meta[key] = clean(m["content"])[:1000]
    canon = soup.find("link", rel="canonical")
    if canon and canon.get("href"):
        meta["canonical"] = canon["href"]
    if soup.html and soup.html.get("lang"):
        meta["lang"] = soup.html["lang"]

    ld = _jsonld(soup)
    persons = []
    for d in ld:
        types = d.get("@type")
        types = types if isinstance(types, list) else [types]
        if "Person" in types and d.get("name"):
            persons.append({k: (v if isinstance(v, (str, int)) else json.dumps(v)[:300])
                            for k, v in d.items()
                            if k in {"name", "jobTitle", "description", "worksFor", "email", "url"}})
    meta["json_ld_types"] = sorted({str(t) for d in ld for t in (d.get("@type") if isinstance(d.get("@type"), list) else [d.get("@type")]) if t})
    if persons:
        meta["persons_json_ld"] = persons[:50]

    title = clean(soup.title.string if soup.title and soup.title.string else "")
    if not title:
        h1 = soup.find("h1")
        title = clean(h1.get_text(" ")) if h1 else meta.get("og:title", "")
    headings = [clean(h.get_text(" ")) for h in soup.find_all(["h1", "h2", "h3"])][:40]
    meta["headings"] = [h for h in headings if h]
    meta["link_count"] = len(soup.find_all("a"))

    for t in soup(DROP):
        t.decompose()

    lines, last = [], None
    for el in soup.find_all(CANDIDATES):
        if el.name not in HEADINGS and el.find(BLOCK):
            continue  # container: its children are visited separately
        text = clean(el.get_text(" "))
        if len(text) < 2 or text == last:
            continue
        lines.append(("# " if el.name in HEADINGS else "") + text)
        last = text
    if sum(len(x) for x in lines) < 200:  # unusual markup: fall back to plain text
        lines = [clean(x) for x in soup.get_text("\n").split("\n") if len(clean(x)) > 1]
    meta["word_count"] = sum(len(x.split()) for x in lines)
    return title[:500], "\n".join(lines), meta


def _empty():
    return {"final_url": "", "http_status": None, "content_type": "", "raw": "",
            "text": "", "title": "", "metadata": {}, "error": ""}


def _fetch_requests(url):
    """Plain HTTP fetch. Never raises."""
    out = _empty()
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        r = session.get(url, timeout=settings.SCRAPE_TIMEOUT, allow_redirects=True)
        if r.status_code in (403, 429, 503):  # one polite retry, as if arriving from a search engine
            r = session.get(url, timeout=settings.SCRAPE_TIMEOUT, allow_redirects=True,
                            headers={"Referer": "https://www.google.com/", "Sec-Fetch-Site": "cross-site"})
        ctype = r.headers.get("Content-Type", "")
        out.update(http_status=r.status_code, final_url=r.url[:2000], content_type=ctype[:200])
        low = ctype.lower()
        if not low or any(k in low for k in ("html", "xml", "text")):
            if "charset" not in low:
                r.encoding = r.apparent_encoding
            html = r.text[: settings.SCRAPE_MAX_CHARS].replace("\x00", "")
            title, text, meta = parse_html(html, r.url)
            meta["response_headers"] = {k: r.headers[k][:200] for k in ("Server", "Last-Modified", "Content-Language")
                                        if k in r.headers}
            meta["elapsed_ms"] = int(r.elapsed.total_seconds() * 1000)
            out.update(raw=html, text=text.replace("\x00", ""), title=title, metadata=meta)
        else:
            out["error"] = f"Unsupported content type: {ctype}"
    except requests.RequestException as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    except Exception as exc:  # parsing problems must not kill the batch
        out["error"] = f"Parse error: {exc}"[:1000]
    return out


def _fetch_browser(url):
    """Render the page in headless Chromium (handles JavaScript pages and some bot checks). None if unavailable."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    out = _empty()
    try:
        with _browser_slots, sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(user_agent=BROWSER_UA, locale="en-US", viewport={"width": 1366, "height": 900})
            page = ctx.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=settings.SCRAPE_TIMEOUT * 2000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            html = page.content()
            status, final = (resp.status if resp else None), page.url
            browser.close()
        html = html[: settings.SCRAPE_MAX_CHARS].replace("\x00", "")
        title, text, meta = parse_html(html, final)
        meta["fetched_with"] = "browser"
        out.update(http_status=status, final_url=final[:2000], content_type="text/html", raw=html,
                   text=text.replace("\x00", ""), title=title, metadata=meta)
    except Exception as exc:
        out["error"] = f"Browser fetch failed: {type(exc).__name__}: {exc}"[:1000]
    return out


def fetch_url(url):
    """Never raises. Returns a dict describing the result."""
    out = _fetch_requests(url)
    needs_browser = out["http_status"] in (None, 403, 429, 503) or \
        (out["http_status"] and out["http_status"] < 400 and len(out["text"]) < 300)
    if USE_BROWSER and needs_browser:
        rendered = _fetch_browser(url)
        if rendered and rendered["http_status"] and \
                (rendered["http_status"] < 400 or len(rendered["text"]) > len(out["text"])):
            return rendered
    return out