from __future__ import annotations

import logging
from functools import lru_cache

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from ..config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _ef() -> ONNXMiniLM_L6_V2:
    # Downloads a small ONNX MiniLM model on first use (~80MB), runs locally on CPU.
    return ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])


class LocalEmbedder:
    """Local ONNX embedder (chromadb's default all-MiniLM-L6-v2, 384-dim).

    No API key required. Compatible with both document and query embeddings —
    MiniLM is symmetric, so input_type is ignored.
    """

    def __init__(self, batch_size: int | None = None) -> None:
        settings = get_settings()
        self.batch_size = batch_size or settings.embed_batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ef = _ef()
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            logger.info(
                "embedding batch %d/%d",
                i // self.batch_size + 1,
                (len(texts) + self.batch_size - 1) // self.batch_size,
            )
            out.extend(ef(batch))
        return out

    def embed_query(self, text: str) -> list[float]:
        return _ef()([text])[0]


# Back-compat alias so existing imports keep working
VoyageEmbedder = LocalEmbedder
