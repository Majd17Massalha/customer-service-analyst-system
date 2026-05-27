"""Tests for the deterministic router and LangGraph skeleton.

No LLM calls, no API keys, no database required.
"""
import pytest
from src.agent.router import RouteResult, route_query


# ---------------------------------------------------------------------------
# Structured routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "How many refund requests are in the dataset?",
    "What categories exist in the dataset?",
    "What is the distribution of intents in the ACCOUNT category?",
    "What is the total number of rows?",
    "Give me the top 10 categories",
    "How many rows are there for FEEDBACK?",
    "What is the breakdown by intent?",
    "Count of orders per category",
])
def test_structured_routing(query):
    r = route_query(query)
    assert r.route == "structured", f"Expected structured, got {r.route!r} for: {query!r}"
    assert r.confidence >= 0.85
    assert r.reason_summary
    assert r.next_action


# ---------------------------------------------------------------------------
# Unstructured routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "Summarize the FEEDBACK category.",
    "How do agents respond to cancellation requests?",
    "Tell me about the ACCOUNT category",
    "Give me an overview of the dataset",
    "Explain the intent patterns in the support data",
    "What are the common issues in the REFUND category?",
])
def test_unstructured_routing(query):
    r = route_query(query)
    assert r.route == "unstructured", f"Expected unstructured, got {r.route!r} for: {query!r}"
    assert r.confidence >= 0.80
    assert r.reason_summary
    assert r.next_action


# ---------------------------------------------------------------------------
# Out-of-scope routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "Who won the Champions League?",
    "Write me a poem about customer service.",
    "What is the weather in New York?",
    "What is the stock price of Apple?",
    "Tell me a joke.",
])
def test_out_of_scope_routing(query):
    r = route_query(query)
    assert r.route == "out_of_scope", f"Expected out_of_scope, got {r.route!r} for: {query!r}"
    assert r.confidence >= 0.90
    assert r.reason_summary
    assert r.next_action


# ---------------------------------------------------------------------------
# Needs-clarification routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "Show me more",
    "What about that?",
    "Give me the last ones",
    "more",
    "continue",
    "and?",
])
def test_needs_clarification_routing(query):
    r = route_query(query)
    assert r.route == "needs_clarification", (
        f"Expected needs_clarification, got {r.route!r} for: {query!r}"
    )
    assert r.reason_summary
    assert r.next_action


# ---------------------------------------------------------------------------
# No hidden chain-of-thought
# ---------------------------------------------------------------------------

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
# LangGraph graph integration
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
    assert "PLACEHOLDER" in state["response"]
    assert any("[route_query]" in t for t in state["trace"])


def test_graph_unstructured(app):
    state = app.invoke(_initial_state("Summarize the FEEDBACK category."))
    assert state["route_result"].route == "unstructured"
    assert "PLACEHOLDER" in state["response"]


def test_graph_out_of_scope(app):
    state = app.invoke(_initial_state("Who won the Champions League?"))
    assert state["route_result"].route == "out_of_scope"
    assert "scope" in state["response"].lower()


def test_graph_clarification(app):
    state = app.invoke(_initial_state("Show me more"))
    assert state["route_result"].route == "needs_clarification"
    assert "context" in state["response"].lower()


def test_graph_trace_populated(app):
    state = app.invoke(_initial_state("How many refund requests?"))
    assert len(state["trace"]) >= 2
    assert any("[route_query]" in t for t in state["trace"])
    assert any("[structured]" in t for t in state["trace"])
