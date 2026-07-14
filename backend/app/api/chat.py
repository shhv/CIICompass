from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..agent import cache as qa_cache
from ..agent.loop import run_agent

logger = logging.getLogger(__name__)

router = APIRouter()


class FileAttachment(BaseModel):
    filename: str
    media_type: str
    data: str  # base64-encoded


class Message(BaseModel):
    role: str
    content: str
    files: list[FileAttachment] = []


class ChatRequest(BaseModel):
    messages: list[Message]
    product: str = "cii"


IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def _to_anthropic_messages(msgs: list[Message]) -> list[dict[str, Any]]:
    out = []
    for m in msgs:
        if m.role not in ("user", "assistant"):
            continue
        if not m.files or m.role != "user":
            out.append({"role": m.role, "content": m.content})
            continue
        # Build multi-block content for messages with file attachments
        blocks: list[dict[str, Any]] = []
        for f in m.files:
            if f.media_type in IMAGE_TYPES:
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": f.media_type, "data": f.data},
                })
            elif f.media_type == "application/pdf":
                blocks.append({
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": f.data},
                })
            else:
                # Text-based files: decode and inline (cap at 100k chars)
                import base64
                MAX_TEXT_CHARS = 100_000
                try:
                    text = base64.b64decode(f.data).decode("utf-8", errors="replace")
                except Exception:
                    text = "(could not decode file)"
                if len(text) > MAX_TEXT_CHARS:
                    # For log files, keep the tail (recent entries matter more)
                    if f.filename.endswith((".log", ".txt")):
                        text = "[truncated — showing last portion]\n\n" + text[-MAX_TEXT_CHARS:]
                    else:
                        text = text[:MAX_TEXT_CHARS] + "\n\n[truncated — file too large]"
                blocks.append({"type": "text", "text": f"[File: {f.filename}]\n{text}"})
        blocks.append({"type": "text", "text": m.content})
        out.append({"role": "user", "content": blocks})
    return out


def _is_cacheable(msgs: list[Message]) -> str | None:
    """Return the question to cache against, or None if not cacheable.

    Cache only single-turn user questions (no prior context) so we don't serve
    a stale answer for a follow-up that depends on earlier turns.
    """
    user_turns = [m for m in msgs if m.role == "user"]
    if len(msgs) == 1 and len(user_turns) == 1:
        return user_turns[0].content
    return None


async def _replay_cached(entry: dict[str, Any]) -> AsyncIterator[dict[str, str]]:
    yield {"event": "cache_hit", "data": json.dumps({"type": "cache_hit"})}
    for c in entry.get("citations") or []:
        yield {"event": "citation", "data": json.dumps({"type": "citation", **c})}
    yield {"event": "text", "data": json.dumps({"type": "text", "delta": entry.get("answer", "")})}
    yield {"event": "done", "data": json.dumps({"type": "done"})}


@router.post("/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    messages = _to_anthropic_messages(req.messages)
    product = req.product
    cache_q = _is_cacheable(req.messages)

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        if cache_q:
            cached = await qa_cache.get(cache_q)
            if cached:
                async for evt in _replay_cached(cached):
                    yield evt
                return

        # Stream live and accumulate to store on success
        answer_buf: list[str] = []
        citations: list[dict[str, Any]] = []
        had_error = False

        try:
            async for evt in run_agent(messages, product=product):
                if evt["type"] == "text":
                    answer_buf.append(evt.get("delta", ""))
                elif evt["type"] == "citation":
                    citations.append(
                        {k: v for k, v in evt.items() if k != "type"}
                    )
                elif evt["type"] == "error":
                    had_error = True
                yield {"event": evt["type"], "data": json.dumps(evt)}
        except Exception as e:
            logger.exception("chat stream error")
            had_error = True
            yield {"event": "error", "data": json.dumps({"type": "error", "message": str(e)})}

        if cache_q and not had_error:
            await qa_cache.put(cache_q, "".join(answer_buf), citations)

    return EventSourceResponse(event_stream())
