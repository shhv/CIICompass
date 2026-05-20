from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import Counter
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ..ingest.pipeline import run_full_pipeline
from ..rag.store import ChromaStore

logger = logging.getLogger(__name__)

router = APIRouter()


class _JobState:
    def __init__(self) -> None:
        self.job_id: str | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.status: str = "idle"  # idle | running | done | error
        self.result: dict[str, Any] | None = None
        self.error: str | None = None


_state = _JobState()
_lock = asyncio.Lock()


class IngestRequest(BaseModel):
    force: bool = False


async def _run_job(force: bool) -> None:
    try:
        _state.status = "running"
        result = await run_full_pipeline(force=force)
        _state.result = result
        _state.status = "done"
    except Exception as e:
        logger.exception("ingest failed")
        _state.error = str(e)
        _state.status = "error"
    finally:
        _state.finished_at = time.time()


@router.post("/ingest")
async def ingest(req: IngestRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    async with _lock:
        if _state.status == "running":
            return {"status": "already_running", "job_id": _state.job_id}
        _state.job_id = uuid.uuid4().hex
        _state.started_at = time.time()
        _state.finished_at = None
        _state.result = None
        _state.error = None
        _state.status = "running"
    background_tasks.add_task(_run_job, req.force)
    return {"status": "started", "job_id": _state.job_id}


@router.get("/status")
async def status() -> dict[str, Any]:
    store = ChromaStore()
    metas = store.all_metadatas()
    by_cat: Counter[str] = Counter()
    urls: set[str] = set()
    for m in metas:
        if not m:
            continue
        if m.get("url"):
            urls.add(m["url"])
        by_cat[m.get("category", "unknown")] += 1
    return {
        "collection_size": store.count(),
        "pages": len(urls),
        "chunks_by_category": dict(by_cat),
        "job": {
            "id": _state.job_id,
            "status": _state.status,
            "started_at": _state.started_at,
            "finished_at": _state.finished_at,
            "result": _state.result,
            "error": _state.error,
        },
    }
