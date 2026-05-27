from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import Counter
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..ingest.pipeline import run_full_pipeline
from ..ingest import progress as ingest_progress
from ..rag.store import ChromaStore
from ..agent import cache as qa_cache
from ..agent import feedback as fb_store
from ..agent import contact as contact_store
from ..config import get_settings

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
        timeout = get_settings().ingest_timeout_sec
        result = await asyncio.wait_for(run_full_pipeline(force=force), timeout=timeout)
        await qa_cache.clear()
        _state.result = result
        _state.status = "done"
    except asyncio.TimeoutError:
        logger.warning("ingest exceeded %ss timeout", timeout)
        ingest_progress.set_phase("error")
        _state.error = f"timed out after {timeout}s"
        _state.status = "error"
    except Exception as e:
        logger.exception("ingest failed")
        ingest_progress.set_phase("error")
        _state.error = str(e)
        _state.status = "error"
    finally:
        _state.finished_at = time.time()


@router.post("/ingest")
async def ingest(req: IngestRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    started = await start_ingest(req.force, background_tasks=background_tasks)
    if not started:
        return {"status": "already_running", "job_id": _state.job_id}
    return {"status": "started", "job_id": _state.job_id}


async def start_ingest(force: bool, background_tasks: BackgroundTasks | None = None) -> bool:
    """Kick off the ingest job. Returns False if one is already running.

    If background_tasks is provided (HTTP path), the job is scheduled on it.
    Otherwise (scheduler path) it runs as a fire-and-forget asyncio task.
    """
    async with _lock:
        if _state.status == "running":
            return False
        _state.job_id = uuid.uuid4().hex
        _state.started_at = time.time()
        _state.finished_at = None
        _state.result = None
        _state.error = None
        _state.status = "running"
    if background_tasks is not None:
        background_tasks.add_task(_run_job, force)
    else:
        asyncio.create_task(_run_job(force))
    return True


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
        "qa_cache_size": await qa_cache.size(),
        "feedback": await fb_store.stats(),
        "job": {
            "id": _state.job_id,
            "status": _state.status,
            "started_at": _state.started_at,
            "finished_at": _state.finished_at,
            "result": _state.result,
            "error": _state.error,
            "progress": ingest_progress.get_progress().snapshot(),
        },
    }


@router.post("/cache/clear")
async def clear_cache() -> dict[str, int]:
    return {"cleared": await qa_cache.clear()}


class FeedbackRequest(BaseModel):
    question: str
    answer: str
    vote: int  # 1 or -1
    comment: str | None = None


@router.post("/feedback")
async def feedback(req: FeedbackRequest) -> dict[str, Any]:
    row = await fb_store.record(req.question, req.answer, req.vote, req.comment)
    return {"ok": True, "id": row["id"], "vote": row["vote"]}


@router.get("/feedback/stats")
async def feedback_stats() -> dict[str, int]:
    return await fb_store.stats()


@router.get("/feedback/list")
async def feedback_list(limit: int = 50, only: str | None = None) -> dict[str, Any]:
    rows = await fb_store.list_rows(limit=limit, only=only)
    return {"rows": rows, "count": len(rows)}


@router.get("/feedback/export", response_class=PlainTextResponse)
async def feedback_export() -> PlainTextResponse:
    import csv
    import io

    rows = await fb_store.list_rows(limit=10_000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "vote", "created_at", "updated_at", "question", "answer_preview", "comment"])
    for r in rows:
        w.writerow([
            r.get("id", ""),
            r.get("vote", ""),
            r.get("created_at", ""),
            r.get("updated_at", ""),
            r.get("question", ""),
            r.get("answer_preview", ""),
            r.get("comment", "") or "",
        ])
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="feedback.csv"'},
    )


class ContactRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    message: str


@router.post("/contact")
async def contact(req: ContactRequest) -> dict[str, Any]:
    try:
        row = await contact_store.submit(req.name or "", req.email or "", req.message)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "sent": row["sent"], "error": row.get("error")}
