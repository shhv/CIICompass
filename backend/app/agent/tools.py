from __future__ import annotations

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ..config import get_settings
from ..rag.retriever import HybridRetriever
from ..rag.store import ChromaStore

logger = logging.getLogger(__name__)


TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_docs",
        "description": (
            "Search the indexed CII documentation (docs.oort.io). Returns the top "
            "matching chunks with title, URL, snippet, and category. Use this first "
            "for any factual or how-to question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language search query."},
                "category": {
                    "type": "string",
                    "enum": [
                        "product-doc",
                        "config-guide",
                        "api-ref",
                        "release-note",
                        "capability",
                        "feature-announce",
                        "troubleshooting",
                    ],
                    "description": "Optional filter by doc category.",
                },
                "k": {"type": "integer", "default": 8, "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_page",
        "description": (
            "Fetch the full markdown content of a specific docs.oort.io page by URL. "
            "Use when search snippets are insufficient and you need the full page."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full https://docs.oort.io/... URL."}
            },
            "required": ["url"],
        },
    },
    {
        "name": "list_sections",
        "description": (
            "List indexed pages, optionally filtered by category. Useful for overview / "
            "navigation queries like 'what's in the API reference?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "product-doc",
                        "config-guide",
                        "api-ref",
                        "release-note",
                        "capability",
                        "feature-announce",
                        "troubleshooting",
                    ],
                },
                "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200},
            },
        },
    },
]


class ToolExecutor:
    def __init__(self) -> None:
        self.retriever = HybridRetriever()
        self.store = ChromaStore()

    async def run(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "search_docs":
            return await self._search_docs(**args)
        if name == "fetch_page":
            return await self._fetch_page(**args)
        if name == "list_sections":
            return await self._list_sections(**args)
        return {"error": f"unknown tool: {name}"}

    async def _search_docs(self, query: str, category: str | None = None, k: int = 8) -> dict[str, Any]:
        results = self.retriever.search(query=query, k=k, category=category)
        return {
            "results": [
                {
                    "chunk_id": r.id,
                    "url": r.url,
                    "title": r.title,
                    "category": r.category,
                    "score": round(r.score, 4),
                    "snippet": r.snippet,
                }
                for r in results
            ]
        }

    async def _fetch_page(self, url: str) -> dict[str, Any]:
        settings = get_settings()
        if "docs.oort.io" not in url:
            return {"error": "only docs.oort.io URLs are allowed"}
        headers = {"User-Agent": settings.user_agent}
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            try:
                r = await client.get(url, timeout=20.0)
            except Exception as e:
                return {"error": f"fetch failed: {e}"}
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        soup = BeautifulSoup(r.text, "lxml")
        for sel in ["nav", "footer", "script", "style", "header", "aside"]:
            for el in soup.find_all(sel):
                el.decompose()
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = md(str(main), heading_style="ATX")
        # Cap so a giant page doesn't blow context
        if len(text) > 30000:
            text = text[:30000] + "\n\n[truncated]"
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        return {"url": url, "title": title, "markdown": text}

    async def _list_sections(self, category: str | None = None, limit: int = 50) -> dict[str, Any]:
        metas = self.store.all_metadatas()
        seen: dict[str, dict[str, Any]] = {}
        for m in metas:
            if not m:
                continue
            if category and m.get("category") != category:
                continue
            u = m.get("url")
            if not u or u in seen:
                continue
            seen[u] = {
                "url": u,
                "title": m.get("title", ""),
                "category": m.get("category", ""),
                "breadcrumb": m.get("breadcrumb", ""),
            }
            if len(seen) >= limit:
                break
        return {"sections": list(seen.values())}
