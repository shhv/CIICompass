from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
APPROX_CHARS_PER_TOKEN = 4  # rough; voyage will count for real


@dataclass
class Chunk:
    text: str
    heading_path: list[str]
    order: int


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // APPROX_CHARS_PER_TOKEN)


def split_by_headings(markdown: str) -> list[tuple[list[str], str]]:
    """Return list of (heading_path, body) sections preserving document order."""
    lines = markdown.splitlines()
    sections: list[tuple[list[str], list[str]]] = []
    stack: list[tuple[int, str]] = []  # (level, text)
    current_body: list[str] = []

    def _flush() -> None:
        if current_body and any(l.strip() for l in current_body):
            sections.append(([t for _, t in stack], list(current_body)))

    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            _flush()
            current_body = []
            level = len(m.group(1))
            text = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
        else:
            current_body.append(line)
    _flush()

    return [(path, "\n".join(body).strip()) for path, body in sections if "\n".join(body).strip()]


def chunk_markdown(
    markdown: str,
    target_tokens: int = 800,
    overlap_tokens: int = 100,
) -> list[Chunk]:
    """Heading-aware chunker. Yields chunks with heading-path prefix."""
    target_chars = target_tokens * APPROX_CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * APPROX_CHARS_PER_TOKEN

    sections = split_by_headings(markdown)
    chunks: list[Chunk] = []
    order = 0

    for heading_path, body in sections:
        prefix = " > ".join(heading_path)
        prefix_block = f"[{prefix}]\n" if prefix else ""

        if len(body) <= target_chars:
            chunks.append(Chunk(text=prefix_block + body, heading_path=heading_path, order=order))
            order += 1
            continue

        # Split long sections on paragraph boundaries with overlap
        paras = re.split(r"\n\s*\n", body)
        buf: list[str] = []
        buf_len = 0
        for para in paras:
            p = para.strip()
            if not p:
                continue
            if buf_len + len(p) + 2 > target_chars and buf:
                text = "\n\n".join(buf).strip()
                chunks.append(Chunk(text=prefix_block + text, heading_path=heading_path, order=order))
                order += 1
                # overlap: keep tail
                tail = text[-overlap_chars:] if overlap_chars > 0 else ""
                buf = [tail, p] if tail else [p]
                buf_len = sum(len(x) for x in buf)
            else:
                buf.append(p)
                buf_len += len(p) + 2
        if buf:
            text = "\n\n".join(buf).strip()
            chunks.append(Chunk(text=prefix_block + text, heading_path=heading_path, order=order))
            order += 1

    return chunks
