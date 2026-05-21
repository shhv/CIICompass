from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()


def _cache_path() -> Path:
    return Path(get_settings().chroma_path).parent / "qa_cache.json"


def _normalize(q: str) -> str:
    q = q.strip().lower()
    q = re.sub(r"\s+", " ", q)
    return q


def _key(question: str) -> str:
    return hashlib.sha256(_normalize(question).encode("utf-8")).hexdigest()


def _load() -> dict[str, Any]:
    p = _cache_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _save(d: dict[str, Any]) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2))


async def get(question: str) -> dict[str, Any] | None:
    async with _lock:
        return _load().get(_key(question))


async def put(question: str, answer: str, citations: list[dict[str, Any]]) -> None:
    if not answer.strip():
        return
    async with _lock:
        d = _load()
        d[_key(question)] = {
            "question": question.strip(),
            "answer": answer,
            "citations": citations,
        }
        _save(d)


async def clear() -> int:
    async with _lock:
        d = _load()
        n = len(d)
        _save({})
        return n


async def size() -> int:
    async with _lock:
        return len(_load())
