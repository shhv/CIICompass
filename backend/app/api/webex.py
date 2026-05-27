from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from ..agent.loop import run_agent
from ..config import get_settings
from ..webex.client import WebexClient

logger = logging.getLogger(__name__)

router = APIRouter()

_client: WebexClient | None = None
_semaphore: asyncio.Semaphore | None = None
_busy_message = "⏳ Busy answering other questions — your message is queued."


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().webex_max_concurrent)
    return _semaphore


def _get_client() -> WebexClient:
    global _client
    if _client is None:
        _client = WebexClient()
    return _client


def _verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not secret:
        return True  # verification disabled
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _handle_message_created(payload: dict[str, Any]) -> None:
    """Background task: fetch message, run agent, post reply."""
    client = _get_client()
    try:
        await client.me()  # ensure identity cached
    except Exception:
        logger.exception("webex /people/me failed")
        return

    data = payload.get("data") or {}
    message_id = data.get("id")
    room_id = data.get("roomId")
    person_id = data.get("personId")
    person_email = data.get("personEmail")
    if not message_id or not room_id:
        logger.warning("webex webhook missing message_id or room_id")
        return
    if client.is_self(person_id, person_email):
        return  # ignore our own messages

    try:
        msg = await client.get_message(message_id)
    except Exception:
        logger.exception("webex get_message failed")
        return

    text = msg.get("text") or msg.get("markdown") or ""
    text = client.strip_mention(text).strip()
    if not text:
        return

    settings = get_settings()
    try:
        await client.post_message(room_id, settings.webex_ack_message, parent_id=message_id)
    except Exception:
        logger.exception("webex ack post failed")

    sem = _get_semaphore()
    if sem.locked():
        try:
            await client.post_message(room_id, _busy_message, parent_id=message_id)
        except Exception:
            logger.exception("webex busy-notice post failed")

    final_chunks: list[str] = []
    citations: list[dict[str, Any]] = []
    async with sem:
        try:
            async for ev in run_agent([{"role": "user", "content": text}]):
                t = ev.get("type")
                if t == "text":
                    final_chunks.append(ev.get("delta", ""))
                elif t == "tool_use":
                    # Discard preamble text emitted before this tool call;
                    # keep only the final answer after the last tool round.
                    final_chunks.clear()
                elif t == "citation":
                    citations.append(ev)
                elif t == "error":
                    final_chunks.append(f"\n\n_error: {ev.get('message','')}_")
                    break
        except Exception as e:
            logger.exception("webex agent run failed")
            final_chunks.append(f"\n\n_internal error: {e}_")

    answer = "".join(final_chunks).strip() or "_(no answer produced)_"
    if citations:
        lines = ["", "---", "**Sources**"]
        for i, c in enumerate(citations, 1):
            title = c.get("title") or c.get("url", "")
            url = c.get("url", "")
            lines.append(f"{i}. [{title}]({url})")
        answer = answer + "\n" + "\n".join(lines)

    try:
        await client.post_message(room_id, answer, parent_id=message_id)
    except Exception:
        logger.exception("webex final post failed")


@router.post("/webex/webhook")
async def webex_webhook(
    request: Request,
    x_spark_signature: str | None = Header(default=None, alias="X-Spark-Signature"),
) -> dict[str, str]:
    body = await request.body()
    settings = get_settings()
    if not _verify_signature(settings.webex_webhook_secret, body, x_spark_signature):
        raise HTTPException(status_code=401, detail="bad signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    resource = payload.get("resource")
    event = payload.get("event")
    if resource == "messages" and event == "created":
        asyncio.create_task(_handle_message_created(payload))
    return {"status": "ok"}
