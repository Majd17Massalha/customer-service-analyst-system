"""Deterministic rule-based query router.

Priority order: out_of_scope → needs_clarification → structured → unstructured → fallback.
No LLM calls are made here.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

RouteLabel = Literal["structured", "unstructured", "out_of_scope", "needs_clarification"]


@dataclass(frozen=True)
class RouteResult:
    route: RouteLabel
    confidence: float
    reason_summary: str
    next_action: str


# ---------------------------------------------------------------------------
# Keyword signal sets
# ---------------------------------------------------------------------------

_STRUCTURED_PHRASES: tuple[str, ...] = (
    "how many",
    "count",
    "number of",
    "total number",
    "how much",
    "distribution of",
    "breakdown",
    "percentage",
    "ratio",
    "top ",
    "average",
    "most common",
    "least common",
    "frequency",
    "list all",
    "what categories",
    "what intents",
    "exists in",
    "how often",
    "per category",
    "per intent",
    "what is the distribution",
    "how many are",
)

_UNSTRUCTURED_PHRASES: tuple[str, ...] = (
    "summarize",
    "summary of",
    "describe",
    "description of",
    "explain",
    "tell me about",
    "give me an overview",
    "how do agents",
    "what do agents",
    "how does",
    "what are the common",
    "what patterns",
    "analyze the",
    "review the",
    "examples of",
    "show examples",
    "how are",
    "what kind of",
)

_OUT_OF_SCOPE_PHRASES: tuple[str, ...] = (
    "champions league",
    "premier league",
    "football",
    "soccer",
    "basketball",
    "baseball",
    "who won",
    "write me a poem",
    "write a poem",
    "poem about",
    "recipe for",
    "weather in",
    "stock market",
    "stock price",
    "movie review",
    "film review",
    "celebrity",
    "politics",
    "election",
    "news about",
    "tell me a joke",
    "write a story",
    "write me a story",
    "what is the capital",
    "solve this equation",
)

_CLARIFICATION_EXACT: frozenset[str] = frozenset({
    "show me more",
    "more",
    "what about that",
    "what about those",
    "give me the last ones",
    "give me more",
    "the last ones",
    "continue",
    "and",
    "next",
    "what else",
    "go on",
    "those",
    "them",
})

_CLARIFICATION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^(show me|give me)?\s*(more|those|them|it|that)\s*$"),
    re.compile(r"\bwhat about (that|those|them|it)\b"),
    re.compile(r"\bthe (previous|last) (ones?|results?|entries)\b"),
)

_TRAILING_PUNCT = re.compile(r"[?.!,;]+$")


def _normalize(query: str) -> str:
    return _TRAILING_PUNCT.sub("", query.lower().strip()).strip()


def _matches_any(text: str, phrases: tuple[str, ...]) -> list[str]:
    matches = []
    for p in phrases:
        pattern = r"\b" + re.escape(p.strip()) + r"\b"
        if re.search(pattern, text):
            matches.append(p)
    return matches


def _is_clarification(norm: str) -> bool:
    if norm in _CLARIFICATION_EXACT:
        return True
    for pattern in _CLARIFICATION_PATTERNS:
        if pattern.search(norm):
            return True
    if len(norm.split()) <= 3:
        has_signal = any(p in norm for p in _STRUCTURED_PHRASES + _UNSTRUCTURED_PHRASES)
        if not has_signal:
            return True
    return False


def route_query(query: str) -> RouteResult:
    """Classify a user query into one of four routes using deterministic keyword rules.

    Returns a RouteResult with operational trace fields only — no chain-of-thought.
    """
    t0 = time.perf_counter()
    norm = _normalize(query)

    oos_hits = _matches_any(norm, _OUT_OF_SCOPE_PHRASES)
    if oos_hits:
        result = RouteResult(
            route="out_of_scope",
            confidence=0.95,
            reason_summary=f"Matched out-of-scope signal(s): {oos_hits[:2]}",
            next_action="Return refusal message explaining agent scope",
        )
        logger.info(
            "router: out_of_scope conf=%.2f reason=%r (%.3fs)",
            result.confidence, result.reason_summary, time.perf_counter() - t0,
        )
        return result

    if _is_clarification(norm):
        result = RouteResult(
            route="needs_clarification",
            confidence=0.85,
            reason_summary="Query is ambiguous or requires prior context to interpret",
            next_action="Ask user to rephrase with more specific context",
        )
        logger.info(
            "router: needs_clarification conf=%.2f reason=%r (%.3fs)",
            result.confidence, result.reason_summary, time.perf_counter() - t0,
        )
        return result

    struct_hits = _matches_any(norm, _STRUCTURED_PHRASES)
    if struct_hits:
        confidence = round(min(0.90 + 0.02 * (len(struct_hits) - 1), 0.99), 2)
        result = RouteResult(
            route="structured",
            confidence=confidence,
            reason_summary=f"Matched analytical signal(s): {struct_hits[:2]}",
            next_action="Dispatch to analytics tool (DuckDB/Pandas)",
        )
        logger.info(
            "router: structured conf=%.2f reason=%r (%.3fs)",
            result.confidence, result.reason_summary, time.perf_counter() - t0,
        )
        return result

    unstruct_hits = _matches_any(norm, _UNSTRUCTURED_PHRASES)
    if unstruct_hits:
        confidence = round(min(0.88 + 0.02 * (len(unstruct_hits) - 1), 0.99), 2)
        result = RouteResult(
            route="unstructured",
            confidence=confidence,
            reason_summary=f"Matched summarization signal(s): {unstruct_hits[:2]}",
            next_action="Dispatch to LLM summarization with dataset samples",
        )
        logger.info(
            "router: unstructured conf=%.2f reason=%r (%.3fs)",
            result.confidence, result.reason_summary, time.perf_counter() - t0,
        )
        return result

    result = RouteResult(
        route="needs_clarification",
        confidence=0.50,
        reason_summary="No clear routing signal detected",
        next_action="Ask user to rephrase or provide more context",
    )
    logger.info(
        "router: needs_clarification/fallback conf=%.2f reason=%r (%.3fs)",
        result.confidence, result.reason_summary, time.perf_counter() - t0,
    )
    return result
