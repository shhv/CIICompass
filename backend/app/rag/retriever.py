from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Okapi

from ..ingest.embedder import VoyageEmbedder
from .store import ChromaStore, StoredChunk

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class RetrievedChunk:
    id: str
    text: str
    url: str
    title: str
    category: str
    score: float
    snippet: str


class HybridRetriever:
    """Vector retrieval from Chroma + BM25 rerank over the candidate pool."""

    def __init__(self, store: ChromaStore | None = None, embedder: VoyageEmbedder | None = None):
        self.store = store or ChromaStore()
        self.embedder = embedder or VoyageEmbedder()

    def search(
        self,
        query: str,
        k: int = 8,
        candidate_k: int = 30,
        category: str | None = None,
    ) -> list[RetrievedChunk]:
        where = {"category": category} if category else None
        q_emb = self.embedder.embed_query(query)
        candidates: list[StoredChunk] = self.store.query(q_emb, k=candidate_k, where=where)
        if not candidates:
            return []

        corpus = [_tokenize(c.text) for c in candidates]
        bm25 = BM25Okapi(corpus)
        bm_scores = bm25.get_scores(_tokenize(query))

        max_bm = max(bm_scores) if len(bm_scores) and max(bm_scores) > 0 else 1.0
        results: list[tuple[float, StoredChunk]] = []
        for c, bm in zip(candidates, bm_scores):
            vec_s = c.score or 0.0
            bm_n = bm / max_bm
            blended = 0.6 * vec_s + 0.4 * bm_n
            results.append((blended, c))
        results.sort(key=lambda x: x[0], reverse=True)

        out: list[RetrievedChunk] = []
        for score, c in results[:k]:
            md = c.metadata or {}
            snippet = c.text[:400].strip().replace("\n", " ")
            out.append(
                RetrievedChunk(
                    id=c.id,
                    text=c.text,
                    url=str(md.get("url", "")),
                    title=str(md.get("title", "")),
                    category=str(md.get("category", "")),
                    score=score,
                    snippet=snippet,
                )
            )
        return out
