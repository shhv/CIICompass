from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


class WebexClient:
    """Thin async wrapper around the Webex REST API using the bot token."""

    def __init__(self) -> None:
        s = get_settings()
        self._base = s.webex_api_base.rstrip("/")
        self._token = s.webex_bot_token
        self._bot_id: str | None = None
        self._bot_emails: set[str] = set()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _request(self, method: str, path: str, **kw: Any) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.request(method, f"{self._base}{path}", headers=self._headers(), **kw)
            r.raise_for_status()
            return r.json() if r.content else {}

    async def me(self) -> dict[str, Any]:
        if self._bot_id is None:
            data = await self._request("GET", "/people/me")
            self._bot_id = data.get("id")
            self._bot_emails = set(data.get("emails") or [])
        return {"id": self._bot_id, "emails": list(self._bot_emails)}

    async def get_message(self, message_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/messages/{message_id}")

    async def post_message(
        self,
        room_id: str,
        markdown: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"roomId": room_id, "markdown": markdown}
        if parent_id:
            payload["parentId"] = parent_id
        return await self._request("POST", "/messages", json=payload)

    def is_self(self, person_id: str | None, person_email: str | None) -> bool:
        if person_id and self._bot_id and person_id == self._bot_id:
            return True
        if person_email and person_email in self._bot_emails:
            return True
        return False

    def strip_mention(self, text: str) -> str:
        """Best-effort: drop the bot's display name / email from the start of a mention."""
        if not text:
            return text
        t = text.strip()
        for email in self._bot_emails:
            local = email.split("@", 1)[0]
            for token in (email, local):
                if t.lower().startswith(token.lower()):
                    t = t[len(token):].lstrip(" ,:")
                    break
        return t
