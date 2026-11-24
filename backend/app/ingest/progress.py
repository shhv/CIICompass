from __future__ import annotations

from dataclasses import dataclass, field, asdict
from contextvars import ContextVar
from threading import Lock


@dataclass
class CrawlProgress:
    urls_discovered: int = 0
    pages_seen: int = 0
    pages_failed: int = 0
    pages_indexed: int = 0
    pages_skipped: int = 0
    chunks_indexed: int = 0
    phase: str = "idle"  # idle | discovering | fetching | indexing | done | error
    last_error: str = ""

    def snapshot(self) -> dict:
        return asdict(self)


# One tracker per product so concurrent ingests (e.g. duo + cii) don't share counters.
# The running pipeline binds its product via use_product(); asyncio tasks and
# asyncio.to_thread copy the context, so crawler/indexer updates land on the right one.
_trackers: dict[str, CrawlProgress] = {}
_current: ContextVar[str] = ContextVar("ingest_product", default="cii")
_lock = Lock()


def use_product(product: str) -> None:
    _current.set(product)


def get_progress(product: str | None = None) -> CrawlProgress:
    key = product or _current.get()
    with _lock:
        if key not in _trackers:
            _trackers[key] = CrawlProgress()
        return _trackers[key]


def reset() -> None:
    _progress = get_progress()
    with _lock:
        for f in (
            "urls_discovered",
            "pages_seen",
            "pages_failed",
            "pages_indexed",
            "pages_skipped",
            "chunks_indexed",
        ):
            setattr(_progress, f, 0)
        _progress.phase = "idle"
        _progress.last_error = ""


def set_phase(phase: str) -> None:
    _progress = get_progress()
    with _lock:
        _progress.phase = phase


def set_discovered(n: int) -> None:
    _progress = get_progress()
    with _lock:
        _progress.urls_discovered = n


def bump_seen() -> None:
    _progress = get_progress()
    with _lock:
        _progress.pages_seen += 1


def bump_failed(reason: str = "") -> None:
    _progress = get_progress()
    with _lock:
        _progress.pages_failed += 1
        if reason:
            _progress.last_error = reason[:300]


def set_indexed(pages: int, skipped: int, chunks: int) -> None:
    _progress = get_progress()
    with _lock:
        _progress.pages_indexed = pages
        _progress.pages_skipped = skipped
        _progress.chunks_indexed = chunks
