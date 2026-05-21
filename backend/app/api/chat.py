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


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


def _to_anthropic_messages(msgs: list[Message]) -> list[dict[str, Any]]:
    return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]


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
            async for evt in run_agent(messages):
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
