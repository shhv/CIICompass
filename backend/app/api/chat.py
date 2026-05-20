from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

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


@router.post("/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    messages = _to_anthropic_messages(req.messages)

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        try:
            async for evt in run_agent(messages):
                yield {"event": evt["type"], "data": json.dumps(evt)}
        except Exception as e:
            logger.exception("chat stream error")
            yield {"event": "error", "data": json.dumps({"type": "error", "message": str(e)})}

    return EventSourceResponse(event_stream())
