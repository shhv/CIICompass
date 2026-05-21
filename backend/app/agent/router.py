from __future__ import annotations

import re
from typing import Any

from ..config import Settings

# Phrases that signal multi-step reasoning, comparison, or synthesis.
# Routed to the heavy model.
_HEAVY_PATTERNS = re.compile(
    r"\b("
    r"why|how (?:should|do|would|can) (?:i|we|you)|"
    r"compare|difference between|tradeoff|trade-off|"
    r"explain|walk me through|step[- ]by[- ]step|"
    r"design|architect|architecture|"
    r"recommend|best (?:way|approach|practice)|"
    r"debug|troubleshoot|root cause|"
    r"plan|strategy"
    r")\b",
    re.IGNORECASE,
)

# Short factual lookup signals — keep on the light model.
_LIGHT_PATTERNS = re.compile(
    r"^\s*(what is|what's|define|where (?:is|can)|when (?:is|was)|who|list|show me)\b",
    re.IGNORECASE,
)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts: list[str] = []
            for block in c:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            if parts:
                return "\n".join(parts)
    return ""


def choose_model(messages: list[dict[str, Any]], settings: Settings) -> tuple[str, str]:
    """Pick (model_id, reason) for this turn.

    Reason is a short tag suitable for logging / SSE.
    """
    mode = (settings.router_mode or "heuristic").lower()
    if mode == "always_opus":
        return settings.reasoning_model, "forced:opus"
    if mode == "always_haiku":
        return settings.light_model, "forced:haiku"

    text = _last_user_text(messages).strip()
    # Long inputs or long histories → heavier model
    word_count = len(text.split())
    user_turns = sum(1 for m in messages if m.get("role") == "user")

    if word_count >= 40 or user_turns >= 4:
        return settings.reasoning_model, "heuristic:long"
    if _HEAVY_PATTERNS.search(text):
        return settings.reasoning_model, "heuristic:keywords"
    if _LIGHT_PATTERNS.search(text) or word_count <= 15:
        return settings.light_model, "heuristic:lookup"
    # Default: light model — escalation in the loop covers misclassification.
    return settings.light_model, "heuristic:default"
