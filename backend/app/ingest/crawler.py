from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ..config import get_settings

logger = logging.getLogger(__name__)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass
class FetchedPage:
    url: str
    title: str
    breadcrumb: list[str]
    last_updated: str | None
    markdown: str
    category: str
    content_hash: str
    raw_path: str


def url_hash(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _same_base(url: str, base: str) -> bool:
    """Check if url starts with the base URL (host + path prefix)."""
    u = urlparse(url)
    b = urlparse(base)
    if u.netloc != b.netloc:
        return False
    base_path = b.path.rstrip("/")
    if not base_path:
        return True
    return u.path == base_path or u.path.startswith(base_path + "/")


def same_host(url: str, base: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc


def categorize(url: str, breadcrumb: list[str]) -> str:
    u = url.lower()
    bc = " > ".join(breadcrumb).lower()
    if "release" in u or "changelog" in u or "release" in bc:
        return "release-note"
    if "api" in u or "reference" in u or "api" in bc:
        return "api-ref"
    if "troubleshoot" in u or "faq" in u or "error" in u:
        return "troubleshooting"
    if "config" in u or "setup" in u or "install" in u:
        return "config-guide"
    if "announce" in u or "what-s-new" in u or "whats-new" in u:
        return "feature-announce"
    if "capability" in u or "capabilities" in u:
        return "capability"
    return "product-doc"


class RateLimiter:
    def __init__(self, rate_per_sec: float):
        self.interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        if self.interval <= 0:
            return
        async with self._lock:
            now = asyncio.get_event_loop().time()
            delay = self._last + self.interval - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = asyncio.get_event_loop().time()


async def discover_urls(client: httpx.AsyncClient, base_url: str) -> list[str]:
    """Fetch sitemap.xml; fall back to recursive link crawl if missing."""
    sitemap_url = urljoin(base_url.rstrip("/") + "/", "sitemap.xml")
    try:
        r = await client.get(sitemap_url, timeout=20.0)
        if r.status_code == 200 and ("<urlset" in r.text or "<sitemapindex" in r.text):
            entries = _parse_sitemap(r.text, base_url)
            urls: list[str] = []
            for entry in entries:
                if entry.endswith(".xml"):
                    try:
                        sub = await client.get(entry, timeout=20.0)
                        if sub.status_code == 200:
                            urls.extend(_parse_sitemap(sub.text, base_url))
                    except Exception as e:
                        logger.warning("sub-sitemap fetch %s failed: %s", entry, e)
                else:
                    urls.append(entry)
            if urls:
                return urls
    except Exception as e:
        logger.warning("sitemap fetch failed: %s", e)
    return await _link_crawl(client, base_url)


def _parse_sitemap(xml_text: str, base_url: str) -> list[str]:
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("sitemap parse error: %s", e)
        return urls
    tag = root.tag.split("}", 1)[-1]
    if tag == "sitemapindex":
        for loc in root.findall(".//sm:sitemap/sm:loc", SITEMAP_NS):
            if loc.text:
                urls.append(loc.text.strip())
    else:
        for loc in root.findall(".//sm:url/sm:loc", SITEMAP_NS):
            if loc.text and same_host(loc.text.strip(), base_url):
                urls.append(loc.text.strip())
    return urls


async def _link_crawl(client: httpx.AsyncClient, base_url: str, max_pages: int = 500) -> list[str]:
    seen: set[str] = set()
    queue: list[str] = [base_url]
    out: list[str] = []
    sem = asyncio.Semaphore(10)

    async def _fetch_one(url: str) -> list[str]:
        async with sem:
            try:
                r = await client.get(url, timeout=20.0)
            except Exception as e:
                logger.warning("link-crawl fetch %s failed: %s", url, e)
                return []
            if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
                return []
            out.append(url)
            soup = BeautifulSoup(r.text, "lxml")
            found: list[str] = []
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"]).split("#", 1)[0]
                if same_host(href, base_url) and href not in seen:
                    seen.add(href)
                    found.append(href)
            return found

    seen.add(base_url)
    while queue and len(out) < max_pages:
        batch = queue[:20]
        queue = queue[20:]
        results = await asyncio.gather(*(_fetch_one(u) for u in batch))
        for links in results:
            queue.extend(links)
    return out


async def _extract_main(
    html: str,
    page_url: str = "",
    anthropic_client=None,
    image_semaphore=None,
) -> tuple[str, list[str], str | None, str]:
    """Return (title, breadcrumb, last_updated, markdown_text)."""
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    breadcrumb: list[str] = []
    crumb_el = soup.find(attrs={"class": re.compile(r"breadcrumb", re.I)})
    if crumb_el:
        for item in crumb_el.find_all(["li", "a", "span"]):
            t = item.get_text(strip=True)
            if t and t not in breadcrumb:
                breadcrumb.append(t)

    last_updated: str | None = None
    time_el = soup.find("time")
    if time_el:
        last_updated = time_el.get("datetime") or time_el.get_text(strip=True)

    for sel in ["script", "style", "noscript"]:
        for el in soup.find_all(sel):
            el.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    # Strip layout chrome only WITHIN main
    for sel in ["nav", "footer", "header", "aside"]:
        for el in main.find_all(sel):
            el.decompose()
    # Remove skip-links, banner alerts, and top-nav remnants
    for el in main.find_all("a", href="#main-content"):
        el.decompose()
    for el in main.find_all(attrs={"class": re.compile(r"banner|alert|notification|skip", re.I)}):
        el.decompose()

    # Extract text from images via vision API before markdownify
    from .image_extractor import extract_images_from_soup
    await extract_images_from_soup(main, page_url, anthropic_client, image_semaphore)

    markdown_text = md(str(main), heading_style="ATX")
    markdown_text = re.sub(r"\n{3,}", "\n\n", markdown_text).strip()
    # Strip leading nav cruft before the first heading
    heading_match = re.search(r"^#{1,3}\s+", markdown_text, re.MULTILINE)
    if heading_match and heading_match.start() > 0:
        markdown_text = markdown_text[heading_match.start():]
    return title, breadcrumb, last_updated, markdown_text


async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    limiter: RateLimiter,
    raw_dir: Path,
    anthropic_client=None,
    image_semaphore=None,
) -> FetchedPage | None:
    await limiter.wait()
    try:
        r = await client.get(url, timeout=15.0)
    except Exception as e:
        from . import progress as _p
        _p.bump_failed(repr(e))
        logger.warning("fetch %s failed: %s", url, repr(e))
        return None
    if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
        from . import progress as _p
        _p.bump_failed(f"status={r.status_code} ct={r.headers.get('content-type','')[:40]}")
        return None

    raw_file = raw_dir / f"{url_hash(url)}.html"
    raw_file.write_text(r.text, encoding="utf-8")

    title, breadcrumb, last_updated, markdown_text = await _extract_main(
        r.text, page_url=url, anthropic_client=anthropic_client, image_semaphore=image_semaphore
    )
    if not markdown_text:
        from . import progress as _p
        _p.bump_failed("empty markdown")
        return None

    from . import progress as _p
    _p.bump_seen()
    category = categorize(url, breadcrumb)
    return FetchedPage(
        url=url,
        title=title or url,
        breadcrumb=breadcrumb,
        last_updated=last_updated,
        markdown=markdown_text,
        category=category,
        content_hash=content_hash(markdown_text),
        raw_path=str(raw_file),
    )


async def crawl_all(base_url: str | None = None) -> list[FetchedPage]:
    settings = get_settings()
    base = base_url or settings.docs_base_url
    raw_dir = settings.raw_dir
    limiter = RateLimiter(settings.crawl_rate_per_sec)
    headers = {"User-Agent": settings.user_agent}
    sem = asyncio.Semaphore(settings.crawl_concurrency)

    # Vision extraction resources
    anthropic_client = None
    image_semaphore = None
    if settings.extract_images and settings.anthropic_api_key:
        import anthropic
        anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )
        image_semaphore = asyncio.Semaphore(5)

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        urls = await discover_urls(client, base)
        urls = sorted(set(u for u in urls if _same_base(u, base)))
        logger.info("discovered %d urls", len(urls))
        from . import progress as _p
        _p.set_discovered(len(urls))
        _p.set_phase("fetching")

        async def _one(u: str) -> FetchedPage | None:
            async with sem:
                return await fetch_page(client, u, limiter, raw_dir, anthropic_client, image_semaphore)

        results = await asyncio.gather(*(_one(u) for u in urls))
    return [p for p in results if p is not None]
