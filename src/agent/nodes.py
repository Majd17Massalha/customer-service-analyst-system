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
    get_filtered_examples,
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
    """Select a deterministic analytics tool for a structured query.

    Specific category and intent filters take precedence over
    general dataset counts. Pure function with no side effects.
    """
    q = query.lower().strip()

    count_request = any(
        phrase in q
        for phrase in ("how many", "count", "number of")
    )

    category_dimension = bool(
        re.search(r"\bcategor(?:y|ies)\b", q)
    )

    distribution_request = bool(
        re.search(r"\b(distribution|breakdown)\b", q)
    )

    ranking_request = bool(
        re.search(
            r"\b(?:most common|most frequent|most frequently|"
            r"highest frequency|largest category|"
            r"category with the most)\b",
            q,
        )
    )

    # 1. Category distribution and ranking
    if category_dimension and (
        distribution_request or ranking_request
    ):
        limit = (
            1
            if ranking_request and not distribution_request
            else 100
        )
        return "get_top_categories", {"limit": limit}

    # 2. Top N categories
    if re.search(r"\btop\b", q) and category_dimension:
        match = re.search(r"\btop\s+(\d+)\b", q)
        limit = int(match.group(1)) if match else 10
        return "get_top_categories", {"limit": limit}

    # 3. Explicit category filter
    # Examples:
    # "How many rows are in the ORDER category?"
    # "How many rows are in the NONEXISTENT category?"
    if category_dimension and count_request:
        match = re.search(
            r"\b(?:in|for|within)\s+(?:the\s+)?"
            r"([a-z_][a-z0-9_]*)\s+categor(?:y|ies)\b"
            r"|\b([a-z_][a-z0-9_]*)\s+categor(?:y|ies)\b",
            q,
        )

        if match:
            category = (
                match.group(1) or match.group(2)
            ).upper()

            return "count_by_category", {
                "category": category
            }

    # 4. Explicit intent filter
    # Example:
    # "How many rows have the cancel_order intent?"
    if re.search(r"\bintents?\b", q) and count_request:
        match = re.search(
            r"\b(?:the|with(?:\s+the)?)\s+"
            r"([a-z_][a-z0-9_]*)\s+intent\b"
            r"|\b([a-z_][a-z0-9_]*)\s+intent\b",
            q,
        )

        if match:
            intent = match.group(1) or match.group(2)

            return "count_by_intent", {
                "intent": intent
            }

    # 5. General dataset count
    # Must come AFTER explicit category/intent filters.
    global_count_pattern = (
        r"\b(?:total number of|total count of|"
        r"number of|how many|count of)\s+"
        r"(?:customer support records|support records|"
        r"dataset records|dataset rows|"
        r"rows|records|entries)\b"
    )

    if re.search(global_count_pattern, q):
        return "count_total_rows", {}

    # 6. Generic category count
    # Example: "How many ORDER requests are there?"
    count_generic = frozenset({
        "rows", "records", "entries", "items",
        "total", "all", "there", "are",
        "the", "a", "an", "in", "of",
        "customer", "support", "dataset",
    })

    if count_request:
        match = re.search(
            r"\b(?:how many|count(?:\s+of)?|number of)"
            r"\s+([a-z_][a-z0-9_]*)\b",
            q,
        )

        if match:
            candidate = match.group(1)

            if candidate not in count_generic:
                return "count_by_category", {
                    "category": candidate.upper()
                }

    # 7. Existing fallback behavior
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

    # 1. Explicit examples about a topic -> keyword search
    m = re.search(r"\bexamples?\s+(?:about|for|on)\s+(\w+)", q)
    if m:
        return "search_examples", {
            "keyword": m.group(1),
            "limit": 5,
        }

    # 2. Specific business intents
    if re.search(
        r"\b(order cancellation|cancel_order|cancel an? order)\b",
        q,
    ):
        return "get_filtered_examples", {
            "intent": "cancel_order",
            "limit": 5,
        }

    # 3. Refund category
    if re.search(r"\brefunds?\b", q):
        return "get_filtered_examples", {
            "category": "REFUND",
            "limit": 5,
        }

    # 4. Other explicit examples -> keyword search
    m = re.search(r"\bexamples?\s+of\s+(\w+)", q)
    if m:
        return "search_examples", {
            "keyword": m.group(1),
            "limit": 5,
        }

    # 5. Category / intent mention
    m = re.search(r"(?:the\s+)?(\w+)\s+(?:category|intent|pattern)", q)
    if m:
        kw = m.group(1)
        if kw not in _STOPWORDS:
            return "search_examples", {
                "keyword": kw,
                "limit": 5,
            }

    # 6. General summarization
    m = re.search(
        r"(?:summarize|describe|analyze|explain|review)\s+(\w+)",
        q,
    )
    if m:
        kw = m.group(1)
        if kw not in _STOPWORDS:
            return "search_examples", {
                "keyword": kw,
                "limit": 5,
            }

    # 7. Fallback
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
    if tool in ("search_examples", "get_filtered_examples"):
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
        obs = search_examples(
            params["keyword"], limit=params.get("limit", 5), db_path=db
        )
    elif tool_name == "get_filtered_examples":
        obs = get_filtered_examples(
            category=params.get("category"),
            intent=params.get("intent"),
            limit=params.get("limit", 5),
            db_path=db,
        )
    elif tool_name == "get_top_categories":
        obs = get_top_categories(limit=params.get("limit", 10), db_path=db)
    else:
        raise ValueError(f"Unsupported unstructured tool: {tool_name}")

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
