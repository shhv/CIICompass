from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass
class ProductConfig:
    key: str
    display_name: str
    collection_name: str
    base_urls: list[str]
    allowed_domains: list[str]
    github_repos: list[str] = field(default_factory=list)


PRODUCTS: dict[str, ProductConfig] = {
    "cii": ProductConfig(
        key="cii",
        display_name="CII",
        collection_name="cii_docs",
        base_urls=["https://docs.oort.io"],
        allowed_domains=["docs.oort.io"],
    ),
    "duo": ProductConfig(
        key="duo",
        display_name="Duo",
        collection_name="duo_docs",
        base_urls=["https://duo.com/docs", "https://duo.com/blog", "https://help.duo.com"],
        allowed_domains=["duo.com", "help.duo.com"],
    ),
}


def get_product(product: str) -> ProductConfig:
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product: {product}")
    return PRODUCTS[product]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(default="https://api.anthropic.com", alias="ANTHROPIC_BASE_URL")

    docs_base_url: str = Field(default="https://docs.oort.io", alias="DOCS_BASE_URL")
    chroma_path: str = Field(default="./data/chroma", alias="CHROMA_PATH")
    raw_path: str = Field(default="./data/raw", alias="RAW_PATH")
    chroma_collection: str = Field(default="cii_docs", alias="CHROMA_COLLECTION")

    crawl_concurrency: int = Field(default=5, alias="CRAWL_CONCURRENCY")
    crawl_rate_per_sec: float = Field(default=1.0, alias="CRAWL_RATE_PER_SEC")
    user_agent: str = Field(default="CII-Assistant-Indexer/0.1", alias="USER_AGENT")

    embed_batch_size: int = Field(default=64, alias="EMBED_BATCH_SIZE")

    reasoning_model: str = Field(default="claude-opus-4.7", alias="REASONING_MODEL")
    light_model: str = Field(default="claude-haiku-4.5", alias="LIGHT_MODEL")
    # heuristic | always_opus | always_haiku
    router_mode: str = Field(default="heuristic", alias="ROUTER_MODE")
    # If a Haiku-routed turn is still issuing tool calls after this iteration, escalate to Opus.
    escalate_after_iter: int = Field(default=3, alias="ESCALATE_AFTER_ITER")

    # Hard cap on a single ingest run. Job is failed if it exceeds this.
    ingest_timeout_sec: int = Field(default=3600, alias="INGEST_TIMEOUT_SEC")

    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    # Daily re-index scheduler. Hour is local time, 0-23 (default 01:00, low-traffic window).
    reindex_enabled: bool = Field(default=True, alias="REINDEX_ENABLED")
    reindex_hour: int = Field(default=1, alias="REINDEX_HOUR")
    reindex_on_startup: bool = Field(default=False, alias="REINDEX_ON_STARTUP")

    contact_email_to: str = Field(default="shhv@cisco.com", alias="CONTACT_EMAIL_TO")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")
    smtp_starttls: bool = Field(default=True, alias="SMTP_STARTTLS")

    # GitHub repo sources (comma-separated "owner/repo" slugs)
    github_repos: str = Field(default="", alias="GITHUB_REPOS")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_index_extensions: str = Field(
        default=".md,.txt,.py,.ps1,.psd1,.psm1,.sh,.yml,.yaml,.json,.toml,.cfg,.ini,.rst,.adoc",
        alias="GITHUB_INDEX_EXTENSIONS",
    )
    github_max_file_bytes: int = Field(default=100_000, alias="GITHUB_MAX_FILE_BYTES")
    github_follow_links: bool = Field(default=True, alias="GITHUB_FOLLOW_LINKS")

    webex_bot_token: str = Field(default="", alias="WEBEX_BOT_TOKEN")
    webex_webhook_secret: str = Field(default="", alias="WEBEX_WEBHOOK_SECRET")
    webex_api_base: str = Field(default="https://webexapis.com/v1", alias="WEBEX_API_BASE")
    webex_ack_message: str = Field(
        default="Got it — searching the CII docs, one moment…",
        alias="WEBEX_ACK_MESSAGE",
    )
    webex_max_concurrent: int = Field(default=8, alias="WEBEX_MAX_CONCURRENT")

    @property
    def github_repo_list(self) -> list[str]:
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]

    @property
    def github_extension_set(self) -> set[str]:
        return {e.strip().lower() for e in self.github_index_extensions.split(",") if e.strip()}

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
