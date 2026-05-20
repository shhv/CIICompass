from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    voyage_api_key: str = Field(default="", alias="VOYAGE_API_KEY")

    docs_base_url: str = Field(default="https://docs.oort.io", alias="DOCS_BASE_URL")
    chroma_path: str = Field(default="./data/chroma", alias="CHROMA_PATH")
    raw_path: str = Field(default="./data/raw", alias="RAW_PATH")
    chroma_collection: str = Field(default="cii_docs", alias="CHROMA_COLLECTION")

    crawl_concurrency: int = Field(default=5, alias="CRAWL_CONCURRENCY")
    crawl_rate_per_sec: float = Field(default=1.0, alias="CRAWL_RATE_PER_SEC")
    user_agent: str = Field(default="CII-Assistant-Indexer/0.1", alias="USER_AGENT")

    embed_model: str = Field(default="voyage-3", alias="EMBED_MODEL")
    embed_batch_size: int = Field(default=128, alias="EMBED_BATCH_SIZE")

    reasoning_model: str = Field(default="claude-opus-4-7", alias="REASONING_MODEL")
    light_model: str = Field(default="claude-haiku-4-5", alias="LIGHT_MODEL")

    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def chroma_dir(self) -> Path:
        p = Path(self.chroma_path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def raw_dir(self) -> Path:
        p = Path(self.raw_path)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
