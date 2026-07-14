"""Vision-based image text extraction for the ingest pipeline."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

import anthropic
from bs4 import Tag

from ..config import get_settings

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = (
    "Extract all visible text, labels, and descriptions from this UI screenshot. "
    "Return them as a bulleted list. If there is no meaningful text, respond with EMPTY."
)

_CACHE_DIR: Path | None = None


def _cache_dir() -> Path:
    global _CACHE_DIR
    if _CACHE_DIR is None:
        _CACHE_DIR = Path(get_settings().raw_path).parent / "image_cache"
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def _img_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _is_decorative(img: Tag) -> bool:
    alt = img.get("alt", None)
    if alt == "":
        return True
    if img.get("role") == "presentation":
        return True
    for attr in ("width", "height"):
        val = img.get(attr)
        if val and str(val).isdigit() and int(val) < 40:
            return True
    return False


def _get_img_url(img: Tag, page_url: str) -> str | None:
    src = img.get("src")
    if not src:
        return None
    if src.startswith("data:"):
        if len(src) < 500:
            return None
        return None
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        from urllib.parse import urlparse
        p = urlparse(page_url)
        return f"{p.scheme}://{p.netloc}{src}"
    if src.startswith("http"):
        return src
    from urllib.parse import urljoin
    return urljoin(page_url, src)


async def extract_images_from_soup(
    soup_main: Tag,
    page_url: str,
    client: anthropic.AsyncAnthropic | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> int:
    """Find images in soup, extract text via vision, replace in-place. Returns count."""
    settings = get_settings()
    if not settings.extract_images:
        return 0

    imgs = soup_main.find_all("img")
    qualifying = []
    for img in imgs:
        if _is_decorative(img):
            continue
        url = _get_img_url(img, page_url)
        if url:
            qualifying.append((img, url))

    if not qualifying:
        return 0

    if client is None:
        client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )

    if semaphore is None:
        semaphore = asyncio.Semaphore(5)

    async def _process_one(img: Tag, img_url: str) -> None:
        cache_file = _cache_dir() / f"{_img_url_hash(img_url)}.txt"
        if cache_file.exists():
            text = cache_file.read_text().strip()
        else:
            text = await _call_vision(client, img_url, semaphore)
            cache_file.write_text(text)

        if not text or text == "EMPTY":
            img.decompose()
            return

        from bs4 import BeautifulSoup
        replacement = BeautifulSoup(
            f'<div class="image-extracted">[Screenshot content: {text}]</div>',
            "html.parser",
        )
        img.replace_with(replacement)

    await asyncio.gather(*(_process_one(img, url) for img, url in qualifying))
    return len(qualifying)


async def _call_vision(
    client: anthropic.AsyncAnthropic,
    img_url: str,
    semaphore: asyncio.Semaphore,
) -> str:
    async with semaphore:
        try:
            settings = get_settings()
            resp = await client.messages.create(
                model=settings.light_model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "url", "url": img_url},
                            },
                            {"type": "text", "text": EXTRACT_PROMPT},
                        ],
                    }
                ],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            logger.warning("vision extraction failed for %s: %s", img_url, e)
            return ""
