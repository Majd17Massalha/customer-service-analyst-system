"""End-to-end execution tests for the LangGraph agent.

Uses an isolated tmp_path DuckDB fixture — no LLM calls and no API keys required.
All numerical assertions are grounded in known fixture data.
"""
from __future__ import annotations

import duckdb
import pytest

from src.agent.graph import build_graph

# ---------------------------------------------------------------------------
# Fixture: 5 known rows across 3 categories / 3 intents
# ---------------------------------------------------------------------------

_ROWS = [
    ("B",  "how do I cancel my order?",      "ORDER",    "cancel_order",   "You can cancel via..."),
    ("BQ", "I want a refund please",          "REFUND",   "get_refund",     "We can process..."),
    ("",   "track my shipment",               "SHIPPING", "track_shipment", "Your shipment is..."),
    ("B",  "cancel this order now",           "ORDER",    "cancel_order",   "Sure, cancelling..."),
    ("Z",  "refund request for my order 123", "REFUND",   "get_refund",     "Refund initiated..."),
]


@pytest.fixture(scope="module")
def test_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "test.duckdb"
    con = duckdb.connect(str(db_file))
    con.execute(
        "CREATE TABLE customer_support_train "
        "(flags VARCHAR, instruction VARCHAR, category VARCHAR, "
        "intent VARCHAR, response VARCHAR)"
    )
    con.executemany("INSERT INTO customer_support_train VALUES (?, ?, ?, ?, ?)", _ROWS)
    con.close()
    return db_file


@pytest.fixture(scope="module")
def graph():
    return build_graph()


def _invoke(graph, query: str, db_path=None) -> dict:
    state = {"query": query, "trace": [], "db_path": str(db_path) if db_path else None}
    return graph.invoke(state)


# ---------------------------------------------------------------------------
# Structured: total row count
# ---------------------------------------------------------------------------

def test_structured_total_count(graph, test_db):
    result = _invoke(graph, "How many rows are in the dataset?", test_db)
    assert result["route_result"].route == "structured"
    assert result["selected_tool"] == "count_total_rows"
    assert result["tool_input"] == {}
    assert result["observation"] == 5
    assert "5" in result["final_answer"]


# ---------------------------------------------------------------------------
# Structured: count by category
# ---------------------------------------------------------------------------

def test_structured_category_count(graph, test_db):
    result = _invoke(graph, "How many rows are in the ORDER category?", test_db)
    assert result["route_result"].route == "structured"
    assert result["selected_tool"] == "count_by_category"
    assert result["tool_input"]["category"] == "ORDER"
    assert result["observation"] == 2
    assert "2" in result["final_answer"]


# ---------------------------------------------------------------------------
# Structured: count by intent
# ---------------------------------------------------------------------------

def test_structured_intent_count(graph, test_db):
    result = _invoke(graph, "How many rows have the cancel_order intent?", test_db)
    assert result["route_result"].route == "structured"
    assert result["selected_tool"] == "count_by_intent"
    assert result["tool_input"]["intent"] == "cancel_order"
    assert result["observation"] == 2
    assert "2" in result["final_answer"]


# ---------------------------------------------------------------------------
# Structured: top categories
# ---------------------------------------------------------------------------

def test_top_categories(graph, test_db):
    result = _invoke(graph, "What are the top categories?", test_db)
    assert result["route_result"].route == "structured"
    assert result["selected_tool"] == "get_top_categories"
    assert isinstance(result["observation"], list)
    cats = [r["category"] for r in result["observation"]]
    assert "ORDER" in cats
    assert "REFUND" in cats


# ---------------------------------------------------------------------------
# Unstructured: example search (routes via "examples of" signal)
# ---------------------------------------------------------------------------

def test_examples_search(graph, test_db):
    result = _invoke(graph, "Show me examples of cancel", test_db)
    assert result["route_result"].route == "unstructured"
    assert result["selected_tool"] == "search_examples"
    assert result["tool_input"]["keyword"] == "cancel"
    assert isinstance(result["observation"], list)
    assert len(result["observation"]) >= 1
    assert "Based on dataset examples only" in result["final_answer"]


# ---------------------------------------------------------------------------
# Unstructured: dataset summary (routes via "summarize" signal)
# ---------------------------------------------------------------------------

def test_unstructured_summary(graph, test_db):
    result = _invoke(graph, "Summarize the dataset", test_db)
    assert result["route_result"].route == "unstructured"
    assert result["selected_tool"] in ("get_top_categories", "search_examples")
    assert result["observation"] is not None
    assert "Based on dataset examples only" in result["final_answer"]


# ---------------------------------------------------------------------------
# Out-of-scope refusal
# ---------------------------------------------------------------------------

def test_out_of_scope_refusal(graph, test_db):
    result = _invoke(graph, "Who won the football match?", test_db)
    assert result["route_result"].route == "out_of_scope"
    assert result["selected_tool"] is None
    fa = result["final_answer"]
    assert fa is not None
    assert "scope" in fa.lower() or "dataset" in fa.lower()


# ---------------------------------------------------------------------------
# Needs-clarification behavior
# ---------------------------------------------------------------------------

def test_needs_clarification(graph, test_db):
    result = _invoke(graph, "more", test_db)
    assert result["route_result"].route == "needs_clarification"
    assert result["selected_tool"] is None
    fa = result["final_answer"]
    assert fa is not None and len(fa) > 0


# ---------------------------------------------------------------------------
# Trace contract: every response must carry all required fields
# ---------------------------------------------------------------------------

def test_trace_contract(graph, test_db):
    """Verify the operational trace contract for all four route types."""
    scenarios = [
        "How many rows are in the dataset?",   # structured
        "Show me examples of cancel",           # unstructured
        "Summarize the dataset",                # unstructured
        "Who won the football match?",          # out_of_scope
        "more",                                 # needs_clarification
    ]
    for query in scenarios:
        result = _invoke(graph, query, test_db)

        assert result.get("route_result") is not None, (
            f"route_result missing for {query!r}"
        )
        for field in ("selected_tool", "tool_input", "observation", "final_answer"):
            assert field in result, f"{field!r} missing for {query!r}"

        assert isinstance(result["final_answer"], str) and result["final_answer"], (
            f"final_answer must be a non-empty string for {query!r}"
        )
        assert len(result.get("trace", [])) >= 2, (
            f"trace must have >= 2 entries for {query!r}"
        )
