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
    from . import progress
    from .github_crawler import crawl_all_github_repos, discover_github_repos_from_pages

    progress.reset()
    progress.set_phase("discovering")

    # 1. Crawl docs.oort.io
    pages = await crawl_all()

    # 2. Determine GitHub repos to crawl (configured + discovered from docs)
    settings = get_settings()
    repo_slugs = set(settings.github_repo_list)
    if settings.github_follow_links:
        discovered = discover_github_repos_from_pages(pages)
        new_repos = discovered - repo_slugs
        if new_repos:
            logger.info("discovered %d GitHub repos from docs: %s", len(new_repos), new_repos)
        repo_slugs |= discovered

    # 3. Crawl GitHub repos
    if repo_slugs:
        github_pages = await crawl_all_github_repos(sorted(repo_slugs))
        pages.extend(github_pages)
        logger.info("github crawl complete: %d pages from %d repos", len(github_pages), len(repo_slugs))

    progress.set_phase("indexing")
    logger.info("crawl complete: %d total pages", len(pages))
    # offload indexing (CPU + sync IO) to a thread to keep loop responsive
    result = await asyncio.to_thread(index_pages, pages, force)
    progress.set_indexed(
        pages=result.get("pages_indexed", 0),
        skipped=result.get("pages_skipped", 0),
        chunks=result.get("chunks_indexed", 0),
    )
    progress.set_phase("done")
    return result
