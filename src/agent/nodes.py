"""LangGraph node functions for the Customer Service Analyst Agent.

Each node receives an AgentState and returns a partial state update dict.
No LLM calls are made here.
"""
from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from src.agent.router import RouteResult, route_query
from src.tools.analytics_tools import (
    DB_PATH,
    count_by_category,
    count_by_intent,
    count_total_rows,
    get_top_categories,
    search_examples,
)

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    query: str
    route_result: RouteResult | None
    response: str | None
    trace: list[str]
    selected_tool: str | None
    tool_input: dict | None
    observation: Any | None
    final_answer: str | None
    db_path: str | None  # Injected by tests; production code leaves this None


def _effective_db(state: AgentState):
    return state.get("db_path") or DB_PATH


# ---------------------------------------------------------------------------
# Structured sub-dispatcher
# ---------------------------------------------------------------------------

def _detect_structured_tool(query: str) -> tuple[str, dict]:
    """Return (tool_name, params) for a structured query. Pure, no side effects."""
    q = query.lower().strip()

    # Top categories
    if re.search(r"\btop\b", q) and "categor" in q:
        m = re.search(r"\btop\s+(\d+)\b", q)
        limit = int(m.group(1)) if m else 10
        return "get_top_categories", {"limit": limit}

    # Category count — extract category name appearing before "category"
    if "categor" in q and any(x in q for x in ("how many", "count", "number of")):
        m = re.search(
            r"(?:in\s+(?:the\s+)?|for\s+(?:the\s+)?)(\w+)\s+categor|(\w+)\s+categor",
            q,
        )
        if m:
            cat = (m.group(1) or m.group(2)).upper()
            return "count_by_category", {"category": cat}

    # Intent count — extract intent name appearing before "intent"
    if "intent" in q and any(x in q for x in ("how many", "count", "number of")):
        m = re.search(
            r"(?:the\s+|with\s+(?:the\s+)?)(\w+)\s+intent|(\w+)\s+intent",
            q,
        )
        if m:
            intent = m.group(1) or m.group(2)
            return "count_by_intent", {"intent": intent}

    # Default: total row count
    return "count_total_rows", {}


# ---------------------------------------------------------------------------
# Unstructured sub-dispatcher
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "the", "a", "an", "in", "of", "for", "with", "and", "or",
    "is", "are", "about", "its", "how", "what", "tell", "give",
})


def _detect_unstructured_action(query: str) -> tuple[str, dict]:
    """Return (tool_name, params) for an unstructured query. Pure, no side effects."""
    q = query.lower().strip()

    # Explicit "examples of X" pattern
    m = re.search(r"\bexamples?\s+of\s+(\w+)", q)
    if m:
        return "search_examples", {"keyword": m.group(1), "limit": 5}

    # Category / intent keyword mention → search by keyword
    m = re.search(r"(?:the\s+)?(\w+)\s+(?:category|intent|pattern)", q)
    if m:
        kw = m.group(1)
        if kw not in _STOPWORDS:
            return "search_examples", {"keyword": kw, "limit": 5}

    # Default: top-categories overview
    return "get_top_categories", {"limit": 10}


# ---------------------------------------------------------------------------
# Extractive summary builder
# ---------------------------------------------------------------------------

def _build_extractive_summary(data: Any, tool: str) -> str:
    prefix = "Based on dataset examples only:"
    if tool == "get_top_categories":
        if not data:
            return f"{prefix}\nNo categories found in the dataset."
        lines = [f"- {d['category']}: {d['count']} rows" for d in data]
        return prefix + "\n" + "\n".join(lines)
    if tool == "search_examples":
        if not data:
            return f"{prefix}\nNo matching examples found in the dataset."
        lines = [
            f"- [{r['category']}/{r['intent']}] {r['instruction']}" for r in data
        ]
        return prefix + "\n" + "\n".join(lines)
    return f"{prefix}\nNo data available."


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def node_route_query(state: AgentState) -> dict[str, Any]:
    result = route_query(state["query"])
    trace_entry = (
        f"[route_query] route={result.route} "
        f"conf={result.confidence:.2f} "
        f"reason={result.reason_summary!r}"
    )
    return {
        "route_result": result,
        "trace": state.get("trace", []) + [trace_entry],
    }


def node_structured_dispatch(state: AgentState) -> dict[str, Any]:
    db = _effective_db(state)
    tool_name, params = _detect_structured_tool(state["query"])

    if tool_name == "count_total_rows":
        obs = count_total_rows(db_path=db)
        answer = f"The dataset contains {obs} rows."
    elif tool_name == "count_by_category":
        obs = count_by_category(params["category"], db_path=db)
        answer = f"The {params['category']} category has {obs} rows."
    elif tool_name == "count_by_intent":
        obs = count_by_intent(params["intent"], db_path=db)
        answer = f"The {params['intent']} intent has {obs} rows."
    elif tool_name == "get_top_categories":
        obs = get_top_categories(limit=params.get("limit", 10), db_path=db)
        cats = ", ".join(f"{d['category']} ({d['count']})" for d in obs)
        answer = f"Top categories by row count: {cats}."
    else:
        obs = None
        answer = "Unsupported structured query."

    return {
        "selected_tool": tool_name,
        "tool_input": params,
        "observation": obs,
        "final_answer": answer,
        "response": answer,
        "trace": state.get("trace", []) + [
            f"[structured] tool={tool_name} params={params} obs={obs!r}"
        ],
    }


def node_unstructured_retrieval(state: AgentState) -> dict[str, Any]:
    db = _effective_db(state)
    tool_name, params = _detect_unstructured_action(state["query"])

    if tool_name == "search_examples":
        obs = search_examples(params["keyword"], limit=params.get("limit", 5), db_path=db)
    else:
        obs = get_top_categories(limit=params.get("limit", 10), db_path=db)

    summary = _build_extractive_summary(obs, tool_name)

    return {
        "selected_tool": tool_name,
        "tool_input": params,
        "observation": obs,
        "final_answer": summary,
        "response": summary,
        "trace": state.get("trace", []) + [
            f"[unstructured] tool={tool_name} params={params}"
        ],
    }


def node_out_of_scope_response(state: AgentState) -> dict[str, Any]:
    rr: RouteResult = state["route_result"]
    answer = (
        "I can only answer questions about the Bitext Customer Support dataset. "
        "Your question appears to be outside that scope. "
        "Try asking about categories, intents, or customer support interactions."
    )
    return {
        "selected_tool": None,
        "tool_input": {},
        "observation": None,
        "final_answer": answer,
        "response": answer,
        "trace": state.get("trace", []) + [
            f"[out_of_scope] refused — {rr.reason_summary}"
        ],
    }


def node_clarification_response(state: AgentState) -> dict[str, Any]:
    rr: RouteResult = state["route_result"]
    answer = (
        "Could you please provide more context? "
        "For example: 'How many refund requests are in the dataset?' "
        "or 'Summarize the FEEDBACK category.'"
    )
    return {
        "selected_tool": None,
        "tool_input": {},
        "observation": None,
        "final_answer": answer,
        "response": answer,
        "trace": state.get("trace", []) + [
            f"[clarification] requested — {rr.reason_summary}"
        ],
    }
