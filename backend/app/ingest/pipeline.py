from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from pathlib import Path

from ..config import get_settings
from ..rag.store import ChromaStore
from .chunker import chunk_markdown
from .crawler import FetchedPage, crawl_all, url_hash
from .embedder import VoyageEmbedder

logger = logging.getLogger(__name__)


def _hash_map_path() -> Path:
    settings = get_settings()
    return Path(settings.chroma_path).parent / "url_hashes.json"


def _load_hashes() -> dict[str, str]:
    p = _hash_map_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_hashes(h: dict[str, str]) -> None:
    p = _hash_map_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(h, indent=2))


def _chunk_id(url: str, order: int) -> str:
    return f"{url_hash(url)}-{order}"


def index_pages(pages: list[FetchedPage], force: bool = False) -> dict[str, int]:
    """Chunk → embed → upsert into Chroma. Returns counts."""
    store = ChromaStore()
    embedder = VoyageEmbedder()
    prior = _load_hashes()

    to_process: list[FetchedPage] = []
    skipped = 0
    for p in pages:
        if not force and prior.get(p.url) == p.content_hash:
            skipped += 1
            continue
        to_process.append(p)

    logger.info("indexing %d pages (skipped %d unchanged)", len(to_process), skipped)

    total_chunks = 0
    for page in to_process:
        # replace existing chunks for this URL
        try:
            store.delete_by_url(page.url)
        except Exception as e:
            logger.warning("delete_by_url(%s) failed: %s", page.url, e)

        chunks = chunk_markdown(page.markdown)
        if not chunks:
            continue
        texts = [c.text for c in chunks]
        embeddings = embedder.embed_documents(texts)
        ids = [_chunk_id(page.url, c.order) for c in chunks]
        metadatas = [
            {
                "url": page.url,
                "title": page.title,
                "category": page.category,
                "breadcrumb": " > ".join(page.breadcrumb),
                "last_updated": page.last_updated or "",
                "heading_path": " > ".join(c.heading_path),
                "order": c.order,
            }
            for c in chunks
        ]
        store.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        prior[page.url] = page.content_hash
        total_chunks += len(chunks)

    _save_hashes(prior)
    return {
        "pages_indexed": len(to_process),
        "pages_skipped": skipped,
        "chunks_indexed": total_chunks,
        "collection_size": store.count(),
    }


async def run_full_pipeline(force: bool = False) -> dict[str, int]:
    pages = await crawl_all()
    logger.info("crawl complete: %d pages", len(pages))
    # offload indexing (CPU + sync IO) to a thread to keep loop responsive
    return await asyncio.to_thread(index_pages, pages, force)
