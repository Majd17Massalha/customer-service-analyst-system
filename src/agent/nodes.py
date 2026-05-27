"""LangGraph node functions for the Customer Service Analyst Agent.

Each node receives an AgentState and returns a partial state update dict.
No LLM calls are made here.
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from src.agent.router import RouteResult, route_query

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    query: str
    route_result: RouteResult | None
    response: str | None
    trace: list[str]


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


def node_structured_placeholder(state: AgentState) -> dict[str, Any]:
    return {
        "response": (
            "PLACEHOLDER: Structured analytics node reached. "
            "DuckDB/MCP tool execution will be connected in a later task."
        ),
        "trace": state.get("trace", []) + [
            "[structured] Analytics execution layer not yet connected"
        ],
    }


def node_unstructured_placeholder(state: AgentState) -> dict[str, Any]:
    return {
        "response": (
            "PLACEHOLDER: Unstructured summarization node reached. "
            "LLM summarization with dataset samples will be connected in a later task."
        ),
        "trace": state.get("trace", []) + [
            "[unstructured] Summarization execution layer not yet connected"
        ],
    }


def node_out_of_scope_response(state: AgentState) -> dict[str, Any]:
    rr: RouteResult = state["route_result"]
    return {
        "response": (
            "I can only answer questions about the Bitext Customer Support dataset. "
            "Your question appears to be outside that scope. "
            "Try asking about categories, intents, or customer support interactions."
        ),
        "trace": state.get("trace", []) + [
            f"[out_of_scope] refused — {rr.reason_summary}"
        ],
    }


def node_clarification_response(state: AgentState) -> dict[str, Any]:
    rr: RouteResult = state["route_result"]
    return {
        "response": (
            "Could you please provide more context? "
            "For example: 'How many refund requests are in the dataset?' "
            "or 'Summarize the FEEDBACK category.'"
        ),
        "trace": state.get("trace", []) + [
            f"[clarification] requested — {rr.reason_summary}"
        ],
    }
