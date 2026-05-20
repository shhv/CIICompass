from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import get_settings


@dataclass
class StoredChunk:
    id: str
    text: str
    metadata: dict[str, Any]
    score: float | None = None


class ChromaStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        self.collection.upsert(
            ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
        )

    def delete_by_url(self, url: str) -> None:
        self.collection.delete(where={"url": url})

    def query(
        self,
        query_embedding: list[float],
        k: int = 8,
        where: dict[str, Any] | None = None,
    ) -> list[StoredChunk]:
        res = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where,
        )
        chunks: list[StoredChunk] = []
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i, _id in enumerate(ids):
            chunks.append(
                StoredChunk(
                    id=_id,
                    text=docs[i],
                    metadata=metas[i] or {},
                    score=1.0 - (dists[i] if i < len(dists) else 0.0),
                )
            )
        return chunks

    def all_metadatas(self) -> list[dict[str, Any]]:
        res = self.collection.get(include=["metadatas"])
        return res.get("metadatas", []) or []

    def all_documents(self, limit: int | None = None) -> tuple[list[str], list[str], list[dict[str, Any]]]:
        res = self.collection.get(include=["documents", "metadatas"], limit=limit)
        return res.get("ids", []), res.get("documents", []), res.get("metadatas", []) or []

    def count(self) -> int:
        return self.collection.count()
