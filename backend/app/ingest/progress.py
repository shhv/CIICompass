from __future__ import annotations

from dataclasses import dataclass, field, asdict
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


_progress = CrawlProgress()
_lock = Lock()


def get_progress() -> CrawlProgress:
    return _progress


def reset() -> None:
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
    with _lock:
        _progress.phase = phase


def set_discovered(n: int) -> None:
    with _lock:
        _progress.urls_discovered = n


def bump_seen() -> None:
    with _lock:
        _progress.pages_seen += 1


def bump_failed(reason: str = "") -> None:
    with _lock:
        _progress.pages_failed += 1
        if reason:
            _progress.last_error = reason[:300]


def set_indexed(pages: int, skipped: int, chunks: int) -> None:
    with _lock:
        _progress.pages_indexed = pages
        _progress.pages_skipped = skipped
        _progress.chunks_indexed = chunks
