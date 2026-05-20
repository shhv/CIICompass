from __future__ import annotations

import logging
from typing import Literal

import voyageai
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings

logger = logging.getLogger(__name__)

InputType = Literal["document", "query"]


class VoyageEmbedder:
    def __init__(self, model: str | None = None, batch_size: int | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.embed_model
        self.batch_size = batch_size or settings.embed_batch_size
        self.client = voyageai.Client(api_key=settings.voyage_api_key or None)

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=20))
    def _embed_batch(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        result = self.client.embed(texts=texts, model=self.model, input_type=input_type)
        return result.embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            logger.info("embedding batch %d/%d", i // self.batch_size + 1, (len(texts) + self.batch_size - 1) // self.batch_size)
            out.extend(self._embed_batch(batch, "document"))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([text], "query")[0]
