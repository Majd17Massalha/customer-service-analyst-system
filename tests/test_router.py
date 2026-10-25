
# ---------------------------------------------------------------------------
# No hidden chain-of-thought
# ---------------------------------------------------------------------------
"""Tests for deterministic routing and LangGraph integration.

Routing unit tests do not require a database.
Graph integration tests for data routes require DuckDB.
No external LLM calls or API keys are required.
"""

import pytest

from src.agent.router import RouteResult, route_query
from src.agent.nodes import _detect_structured_tool

@pytest.mark.parametrize("query", [
    "How many refund requests?",
    "Who won the Champions League?",
    "Summarize FEEDBACK",
    "more",
])
def test_no_chain_of_thought(query):
    r = route_query(query)
    assert isinstance(r, RouteResult)
    assert len(r.reason_summary) < 300
    for val in (r.reason_summary, r.next_action):
        assert "<think>" not in val.lower()
        assert "step 1:" not in val.lower()
        assert "chain of thought" not in val.lower()


# ---------------------------------------------------------------------------
# RouteResult contract
# ---------------------------------------------------------------------------

def test_route_result_contract():
    r = route_query("How many refund requests?")
    assert r.route in ("structured", "unstructured", "out_of_scope", "needs_clarification")
    assert 0.0 <= r.confidence <= 1.0
    assert isinstance(r.reason_summary, str) and r.reason_summary
    assert isinstance(r.next_action, str) and r.next_action


# ---------------------------------------------------------------------------
# Regression: correct structured tool selection (database-free)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "What is the total number of customer support records?",
    "What is the total number of rows?",
    "How many rows are in the dataset?",
])
def test_total_dataset_count_tool_selection(query):
    assert route_query(query).route == "structured"
    tool, params = _detect_structured_tool(query)
    assert (tool, params) == ("count_total_rows", {})


@pytest.mark.parametrize("query", [
    "Give me the distribution of support requests by category.",
    "Show the breakdown by category.",
    "What is the distribution of requests by category?",
])
def test_category_distribution_tool_selection(query):
    assert route_query(query).route == "structured"
    tool, params = _detect_structured_tool(query)
    assert tool == "get_top_categories"
    assert isinstance(params.get("limit"), int)
    assert params["limit"] >= 1


@pytest.mark.parametrize("query", [
    "Which customer support category appears most frequently?",
    "What is the most common category?",
    "Which category has the highest frequency?",
])
def test_most_frequent_category_tool_selection(query):
    assert route_query(query).route == "structured"
    tool, params = _detect_structured_tool(query)
    assert (tool, params) == ("get_top_categories", {"limit": 1})


def test_existing_order_category_count_tool_selection():
    query = "How many ORDER requests are there?"
    assert route_query(query).route == "structured"
    assert _detect_structured_tool(query) == (
        "count_by_category", {"category": "ORDER"}
    )


def test_existing_top_five_categories_tool_selection():
    query = "Give me the top 5 categories"
    assert route_query(query).route == "structured"
    assert _detect_structured_tool(query) == (
        "get_top_categories", {"limit": 5}
    )


# ---------------------------------------------------------------------------
# LangGraph graph integration (requires initialized DuckDB for data routes)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    from src.agent.graph import build_graph
    return build_graph()


def _initial_state(query: str) -> dict:
    return {"query": query, "route_result": None, "response": None, "trace": []}


def test_graph_structured(app):
    state = app.invoke(_initial_state("How many refund requests?"))
    assert state["route_result"].route == "structured"
    assert state["final_answer"] is not None
    assert any("[route_query]" in t for t in state["trace"])


def test_graph_unstructured(app):
    state = app.invoke(_initial_state("Summarize the FEEDBACK category."))
    assert state["route_result"].route == "unstructured"
    assert state["final_answer"] is not None


def test_graph_out_of_scope(app):
    state = app.invoke(_initial_state("Who won the Champions League?"))
    assert state["route_result"].route == "out_of_scope"
    assert "scope" in state["response"].lower()


def test_graph_clarification(app):
    state = app.invoke(_initial_state("Show me more"))
    assert state["route_result"].route == "needs_clarification"
    assert "context" in state["response"].lower()


def test_graph_trace_populated(app):
    state = app.invoke(
        _initial_state("How many refund requests?")
    )

    assert len(state["trace"]) >= 2
    assert any("[route_query]" in t for t in state["trace"])
    assert any("[structured]" in t for t in state["trace"])
