"""LangGraph StateGraph for the Customer Service Analyst Agent.

Topology: START → route_query → {structured, unstructured, out_of_scope, clarification} → END
No LLM calls are made here.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from src.agent.nodes import (
    AgentState,
    node_clarification_response,
    node_out_of_scope_response,
    node_route_query,
    node_structured_placeholder,
    node_unstructured_placeholder,
)

logger = logging.getLogger(__name__)


def _select_route(state: AgentState) -> str:
    return state["route_result"].route


def build_graph():
    """Compile and return the routing StateGraph.

    Returns a LangGraph CompiledGraph ready for .invoke() calls.
    """
    g = StateGraph(AgentState)

    g.add_node("route_query", node_route_query)
    g.add_node("structured_placeholder", node_structured_placeholder)
    g.add_node("unstructured_placeholder", node_unstructured_placeholder)
    g.add_node("out_of_scope_response", node_out_of_scope_response)
    g.add_node("clarification_response", node_clarification_response)

    g.add_edge(START, "route_query")
    g.add_conditional_edges(
        "route_query",
        _select_route,
        {
            "structured": "structured_placeholder",
            "unstructured": "unstructured_placeholder",
            "out_of_scope": "out_of_scope_response",
            "needs_clarification": "clarification_response",
        },
    )
    g.add_edge("structured_placeholder", END)
    g.add_edge("unstructured_placeholder", END)
    g.add_edge("out_of_scope_response", END)
    g.add_edge("clarification_response", END)

    return g.compile()
