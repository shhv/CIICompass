from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from ..config import get_settings
from .prompts import SYSTEM_PROMPT
from .tools import TOOLS, ToolExecutor

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 8
MAX_TOKENS = 4096


def _cached_system() -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _cached_tools() -> list[dict[str, Any]]:
    # Mark the last tool with cache_control so the whole tool block is cached.
    tools = [dict(t) for t in TOOLS]
    tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
    return tools


async def run_agent(
    messages: list[dict[str, Any]],
) -> AsyncIterator[dict[str, Any]]:
    """Run Claude tool-use loop and yield SSE-friendly event dicts.

    Yielded events:
      {"type": "text", "delta": "..."}            partial assistant text
      {"type": "tool_use", "name": "...", "input": {...}}
      {"type": "tool_result", "name": "...", "result": {...}}
      {"type": "citation", "url": "...", "title": "..."}
      {"type": "done"}
      {"type": "error", "message": "..."}
    """
    settings = get_settings()
    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url,
    )
    executor = ToolExecutor()
    convo: list[dict[str, Any]] = list(messages)
    cited_urls: set[str] = set()

    for iteration in range(MAX_ITERATIONS):
        try:
            stream_ctx = client.messages.stream(
                model=settings.reasoning_model,
                max_tokens=MAX_TOKENS,
                system=_cached_system(),
                tools=_cached_tools(),
                thinking={"type": "adaptive"},
                messages=convo,
            )
        except Exception as e:
            yield {"type": "error", "message": f"stream init failed: {e}"}
            return

        try:
            async with stream_ctx as stream:
                async for event in stream:
                    et = getattr(event, "type", None)
                    if et == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        d_type = getattr(delta, "type", None) if delta else None
                        if d_type == "text_delta":
                            yield {"type": "text", "delta": delta.text}
                final = await stream.get_final_message()
        except Exception as e:
            yield {"type": "error", "message": f"stream failed: {e}"}
            return

        # Append assistant turn
        assistant_blocks: list[dict[str, Any]] = []
        tool_uses: list[dict[str, Any]] = []
        for block in final.content:
            b = block.model_dump() if hasattr(block, "model_dump") else dict(block)
            assistant_blocks.append(b)
            if b.get("type") == "tool_use":
                tool_uses.append(b)
        convo.append({"role": "assistant", "content": assistant_blocks})

        if final.stop_reason != "tool_use" or not tool_uses:
            yield {"type": "done"}
            return

        # Execute tools and append results
        tool_results: list[dict[str, Any]] = []
        for tu in tool_uses:
            name = tu.get("name", "")
            args = tu.get("input", {}) or {}
            yield {"type": "tool_use", "name": name, "input": args}
            try:
                result = await executor.run(name, args)
            except Exception as e:
                result = {"error": str(e)}
            yield {"type": "tool_result", "name": name, "result": result}

            # Emit citation events for any new URLs surfaced
            if name == "search_docs":
                for r in result.get("results", []):
                    u = r.get("url")
                    if u and u not in cited_urls:
                        cited_urls.add(u)
                        yield {
                            "type": "citation",
                            "url": u,
                            "title": r.get("title", ""),
                            "category": r.get("category", ""),
                            "snippet": r.get("snippet", ""),
                        }
            elif name == "fetch_page":
                u = result.get("url")
                if u and u not in cited_urls:
                    cited_urls.add(u)
                    yield {"type": "citation", "url": u, "title": result.get("title", "")}

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.get("id"),
                    "content": json.dumps(result)[:50000],
                }
            )

        convo.append({"role": "user", "content": tool_results})

    yield {"type": "error", "message": "max iterations reached"}
