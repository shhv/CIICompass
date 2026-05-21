from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from ..config import get_settings

_lock = asyncio.Lock()


def _path() -> Path:
    return Path(get_settings().chroma_path).parent / "feedback.json"


def _load() -> list[dict[str, Any]]:
    p = _path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _save(rows: list[dict[str, Any]]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=2))


def _row_id(question: str, answer: str) -> str:
    return hashlib.sha256(f"{question.strip()}\n--\n{answer.strip()}".encode("utf-8")).hexdigest()[:16]


async def record(question: str, answer: str, vote: int, comment: str | None = None) -> dict[str, Any]:
    if vote not in (-1, 1):
        raise ValueError("vote must be -1 or 1")
    rid = _row_id(question, answer)
    async with _lock:
        rows = _load()
        for r in rows:
            if r.get("id") == rid:
                r["vote"] = vote
                r["updated_at"] = time.time()
                if comment is not None:
                    r["comment"] = comment.strip()[:2000]
                _save(rows)
                return r
        row = {
            "id": rid,
            "question": question.strip()[:1000],
            "answer_preview": answer.strip()[:500],
            "vote": vote,
            "comment": (comment or "").strip()[:2000] or None,
            "created_at": time.time(),
        }
        rows.append(row)
        _save(rows)
        return row


async def stats() -> dict[str, int]:
    async with _lock:
        rows = _load()
    up = sum(1 for r in rows if r.get("vote") == 1)
    down = sum(1 for r in rows if r.get("vote") == -1)
    return {"up": up, "down": down, "total": len(rows)}


async def list_rows(limit: int = 50, only: str | None = None) -> list[dict[str, Any]]:
    async with _lock:
        rows = _load()
    if only == "down":
        rows = [r for r in rows if r.get("vote") == -1]
    elif only == "up":
        rows = [r for r in rows if r.get("vote") == 1]
    rows.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or 0, reverse=True)
    return rows[:limit]
