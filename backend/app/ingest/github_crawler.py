"""GitHub repository crawler for the CII ingest pipeline."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote

import httpx

from ..config import get_settings
from .crawler import FetchedPage

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

BINARY_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".bmp", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".pyc", ".class", ".o",
}

_GITHUB_REPO_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
)


@dataclass
class GitTreeEntry:
    path: str
    sha: str
    size: int


def _categorize_github_file(path: str) -> str:
    lower = path.lower()
    name = PurePosixPath(lower).name
    ext = PurePosixPath(lower).suffix
    if name == "readme.md":
        return "github-readme"
    if ext in (".md", ".rst", ".adoc"):
        return "github-doc"
    if name in ("license", "licence") or "license" in lower:
        return "github-license"
    return "github-code"


def _wrap_code_as_markdown(content: str, path: str) -> str:
    ext = PurePosixPath(path).suffix.lstrip(".")
    lang_map = {
        "ps1": "powershell", "psd1": "powershell", "psm1": "powershell",
        "py": "python", "sh": "bash", "yml": "yaml", "toml": "toml",
        "json": "json", "cfg": "ini", "ini": "ini",
    }
    lang = lang_map.get(ext, ext)
    return f"# {path}\n\n```{lang}\n{content}\n```"


def _is_text_indexable(path: str, size: int) -> bool:
    settings = get_settings()
    ext = PurePosixPath(path).suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return False
    if size > settings.github_max_file_bytes:
        return False
    allowed = settings.github_extension_set
    if allowed and ext not in allowed:
        return False
    return True


def discover_github_repos_from_pages(pages: list[FetchedPage]) -> set[str]:
    """Scan docs.oort.io page markdown for GitHub repo links."""
    found: set[str] = set()
    for page in pages:
        for m in _GITHUB_REPO_RE.finditer(page.markdown):
            slug = m.group(1).rstrip("/")
            # Strip trailing path segments (blob/tree/issues etc.)
            parts = slug.split("/")
            if len(parts) >= 2:
                repo_slug = f"{parts[0]}/{parts[1]}"
                found.add(repo_slug)
    return found


async def _fetch_repo_tree(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str = "main",
) -> list[GitTreeEntry]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    r = await client.get(url, timeout=30.0)
    if r.status_code == 404:
        # Try "master" as fallback
        url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/master?recursive=1"
        r = await client.get(url, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    entries = []
    for item in data.get("tree", []):
        if item["type"] == "blob":
            entries.append(GitTreeEntry(
                path=item["path"],
                sha=item["sha"],
                size=item.get("size", 0),
            ))
    return entries


async def _fetch_file_content(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
    ref: str = "main",
) -> str | None:
    encoded_path = quote(path, safe="/")
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{encoded_path}"
    headers = {"Accept": "application/vnd.github.raw+json"}
    r = await client.get(url, params={"ref": ref}, headers=headers, timeout=20.0)
    if r.status_code != 200:
        return None
    return r.text


async def crawl_github_repo(owner: str, repo: str) -> list[FetchedPage]:
    from . import progress as _p

    settings = get_settings()
    headers: dict[str, str] = {"User-Agent": settings.user_agent}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    sem = asyncio.Semaphore(settings.crawl_concurrency)

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        try:
            entries = await _fetch_repo_tree(client, owner, repo)
        except httpx.HTTPStatusError as e:
            logger.error("failed to fetch tree for %s/%s: %s", owner, repo, e)
            _p.bump_failed(f"github tree: {e.response.status_code}")
            return []

        indexable = [e for e in entries if _is_text_indexable(e.path, e.size)]
        logger.info("github %s/%s: %d files total, %d indexable", owner, repo, len(entries), len(indexable))

        # Determine default branch (whichever succeeded in _fetch_repo_tree)
        branch = "main"

        async def _fetch_one(entry: GitTreeEntry) -> FetchedPage | None:
            async with sem:
                raw = await _fetch_file_content(client, owner, repo, entry.path, branch)
            if raw is None:
                _p.bump_failed(f"github fetch: {entry.path}")
                return None

            _p.bump_seen()

            blob_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{quote(entry.path, safe='/')}"
            ext = PurePosixPath(entry.path).suffix.lower()

            if ext in (".md", ".rst", ".adoc", ".txt"):
                markdown = raw
            else:
                markdown = _wrap_code_as_markdown(raw, entry.path)

            category = _categorize_github_file(entry.path)
            title = f"{repo}/{entry.path}"
            breadcrumb = [owner, repo] + entry.path.split("/")

            return FetchedPage(
                url=blob_url,
                title=title,
                breadcrumb=breadcrumb,
                last_updated=None,
                markdown=markdown,
                category=category,
                content_hash=entry.sha,
                raw_path="",
            )

        results = await asyncio.gather(*(_fetch_one(e) for e in indexable))
    return [p for p in results if p is not None]


async def crawl_all_github_repos(repo_slugs: list[str]) -> list[FetchedPage]:
    """Crawl a list of GitHub repos (owner/repo slugs)."""
    if not repo_slugs:
        return []

    all_pages: list[FetchedPage] = []
    for slug in repo_slugs:
        parts = slug.split("/")
        if len(parts) != 2:
            logger.warning("invalid github repo slug: %r (expected 'owner/repo')", slug)
            continue
        owner, repo = parts
        pages = await crawl_github_repo(owner, repo)
        all_pages.extend(pages)
        logger.info("github %s: fetched %d pages", slug, len(pages))

    return all_pages
