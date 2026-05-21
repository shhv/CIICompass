from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)
_lock = asyncio.Lock()


def _path() -> Path:
    return Path(get_settings().chroma_path).parent / "contact.json"


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


def _send_smtp(name: str, sender: str, message: str) -> tuple[bool, str | None]:
    s = get_settings()
    if not s.smtp_host:
        return False, "SMTP not configured"
    try:
        msg = EmailMessage()
        who = name or sender
        msg["Subject"] = f"[CII Assistant] Feedback from {who}" if who else "[CII Assistant] Feedback"
        msg["From"] = s.smtp_from or s.smtp_user or "cii-assistant@localhost"
        msg["To"] = s.contact_email_to
        if sender:
            msg["Reply-To"] = sender
        body = f"{message}\n"
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as srv:
            if s.smtp_starttls:
                srv.starttls()
            if s.smtp_user:
                srv.login(s.smtp_user, s.smtp_password)
            srv.send_message(msg)
        return True, None
    except Exception as e:
        logger.exception("smtp send failed")
        return False, str(e)


async def submit(name: str, email: str, message: str) -> dict[str, Any]:
    name = (name or "").strip()[:200]
    email = (email or "").strip()[:200]
    message = (message or "").strip()[:8000]
    if not message:
        raise ValueError("message is required")

    loop = asyncio.get_running_loop()
    sent, err = await loop.run_in_executor(None, _send_smtp, name, email, message)

    row = {
        "name": name,
        "email": email,
        "message": message,
        "to": get_settings().contact_email_to,
        "sent": sent,
        "error": err,
        "created_at": time.time(),
    }
    async with _lock:
        rows = _load()
        rows.append(row)
        _save(rows)

    if not sent:
        logger.info("contact form (mail not sent): %s", row)
    return row
