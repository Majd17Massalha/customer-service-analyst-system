"""Failure mode tests for the Customer Service Analyst Agent.

Tests graceful degradation under corrupted files, missing resources,
invalid inputs, and infrastructure failures. All tests use isolated
fixtures — no LLM calls, no external APIs.
"""
from __future__ import annotations

import duckdb
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.memory.checkpoints import SessionState, load_session, save_session
from src.memory.user_profile import UserProfile, load_profile, save_profile
from src.tools.analytics_tools import (
    count_by_category,
    count_by_intent,
    count_total_rows,
    get_top_categories,
    search_examples,
)
from src.agent.graph import build_graph

# ---------------------------------------------------------------------------
# Shared isolated DuckDB fixture
# ---------------------------------------------------------------------------

_ROWS = [
    ("B",  "cancel my order",  "ORDER",  "cancel_order",  "You can cancel..."),
    ("BQ", "need refund",      "REFUND", "get_refund",    "We can process..."),
]


@pytest.fixture(scope="module")
def fail_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("fail") / "fail.duckdb"
    con = duckdb.connect(str(db_file))
    con.execute(
        "CREATE TABLE customer_support_train "
        "(flags VARCHAR, instruction VARCHAR, category VARCHAR, "
        "intent VARCHAR, response VARCHAR)"
    )
    con.executemany("INSERT INTO customer_support_train VALUES (?, ?, ?, ?, ?)", _ROWS)
    con.close()
    return db_file


# ---------------------------------------------------------------------------
# Memory failure modes
# ---------------------------------------------------------------------------

def test_corrupted_session_json_falls_back(tmp_path):
    """Corrupted session JSON must return a fresh state without raising."""
    session_file = tmp_path / "bad_session.json"
    session_file.write_text("{ not valid json }", encoding="utf-8")

    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        state = load_session("bad_session")

    assert isinstance(state, SessionState)


def test_corrupted_profile_json_falls_back(tmp_path):
    """Corrupted profile JSON must return a fresh profile without raising."""
    profile_file = tmp_path / "bad_profile.json"
    profile_file.write_text("{ broken json", encoding="utf-8")

    with patch("src.memory.user_profile.PROFILES_DIR", tmp_path):
        profile = load_profile("bad_profile")

    assert isinstance(profile, UserProfile)


def test_missing_session_file_returns_fresh_state(tmp_path):
    """Missing session file must return a fresh default state, not raise."""
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        state = load_session("nonexistent_session_xyz_12345")
    assert isinstance(state, SessionState)
    assert state.last_query is None


def test_missing_profile_file_returns_fresh_profile(tmp_path):
    """Missing profile file must return a fresh profile, not raise."""
    with patch("src.memory.user_profile.PROFILES_DIR", tmp_path):
        profile = load_profile("nonexistent_profile_xyz_12345")
    assert isinstance(profile, UserProfile)


def test_session_save_creates_parent_dirs(tmp_path):
    """save_session must create the sessions directory if it does not exist."""
    subdir = tmp_path / "deeply" / "nested" / "sessions"
    assert not subdir.exists()
    with patch("src.memory.checkpoints.SESSIONS_DIR", subdir):
        state = SessionState(session_id="autocreate_test")
        save_session(state)
    assert (subdir / "autocreate_test.json").exists()


def test_corrupted_session_overwritten_on_save(tmp_path):
    """After loading a corrupt session, a subsequent save must produce valid JSON."""
    session_file = tmp_path / "corrupt_then_save.json"
    session_file.write_text("INVALID_JSON_CONTENT", encoding="utf-8")

    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        state = load_session("corrupt_then_save")
        state.last_query = "a valid query"
        save_session(state)

    content = session_file.read_text(encoding="utf-8")
    data = json.loads(content)  # must be valid JSON now
    assert data["last_query"] == "a valid query"


# ---------------------------------------------------------------------------
# Analytics tool failure modes
# ---------------------------------------------------------------------------

def test_missing_duckdb_raises(tmp_path):
    """Non-existent DuckDB path must raise an exception (not silently return 0)."""
    fake_path = tmp_path / "does_not_exist.duckdb"
    with pytest.raises(Exception):
        count_total_rows(db_path=fake_path)


def test_empty_category_raises_value_error(fail_db):
    """Empty string category must raise ValueError before any SQL is executed."""
    with pytest.raises(ValueError):
        count_by_category("", db_path=fail_db)


def test_whitespace_only_category_raises_value_error(fail_db):
    """Whitespace-only category string must raise ValueError."""
    with pytest.raises(ValueError):
        count_by_category("   ", db_path=fail_db)


def test_empty_intent_raises_value_error(fail_db):
    """Empty intent must raise ValueError."""
    with pytest.raises(ValueError):
        count_by_intent("", db_path=fail_db)


def test_zero_limit_raises_value_error(fail_db):
    """Limit of 0 must raise ValueError for get_top_categories."""
    with pytest.raises(ValueError):
        get_top_categories(0, db_path=fail_db)


def test_negative_limit_raises_value_error(fail_db):
    """Negative limit must raise ValueError."""
    with pytest.raises(ValueError):
        get_top_categories(-5, db_path=fail_db)


def test_boolean_limit_raises_value_error(fail_db):
    """Boolean limit must raise ValueError (booleans are excluded)."""
    with pytest.raises(ValueError):
        get_top_categories(True, db_path=fail_db)


def test_empty_keyword_raises_value_error(fail_db):
    """Empty search keyword must raise ValueError."""
    with pytest.raises(ValueError):
        search_examples("", db_path=fail_db)


def test_nonexistent_category_returns_zero(fail_db):
    """Category with no matching rows must return 0, not raise."""
    result = count_by_category("NONEXISTENT_CATEGORY_XYZ", db_path=fail_db)
    assert result == 0


def test_nonexistent_intent_returns_zero(fail_db):
    """Intent with no matching rows must return 0, not raise."""
    result = count_by_intent("nonexistent_intent_xyz_999", db_path=fail_db)
    assert result == 0


def test_nonexistent_keyword_returns_empty_list(fail_db):
    """Keyword with no matching rows must return an empty list, not raise."""
    result = search_examples("xyznonexistentxyz_unique_999", db_path=fail_db)
    assert result == []


def test_count_by_category_returns_correct_count(fail_db):
    """Sanity check: correct category returns correct count."""
    result = count_by_category("ORDER", db_path=fail_db)
    assert result == 1


def test_search_examples_returns_correct_type(fail_db):
    """search_examples must always return a list of dicts."""
    result = search_examples("cancel", db_path=fail_db)
    assert isinstance(result, list)
    for row in result:
        assert isinstance(row, dict)
        assert "instruction" in row
        assert "category" in row


# ---------------------------------------------------------------------------
# Graph-level failure modes
# ---------------------------------------------------------------------------

def test_out_of_scope_route_has_no_tool(fail_db):
    """Out-of-scope route must set selected_tool=None and observation=None."""
    graph = build_graph()
    result = graph.invoke({
        "query": "Who won the Champions League?",
        "trace": [],
        "db_path": str(fail_db),
    })
    assert result["route_result"].route == "out_of_scope"
    assert result["selected_tool"] is None
    assert result["observation"] is None


def test_clarification_route_has_no_tool(fail_db):
    """Clarification route must set selected_tool=None and observation=None."""
    graph = build_graph()
    result = graph.invoke({
        "query": "those",
        "trace": [],
        "db_path": str(fail_db),
    })
    assert result["route_result"].route == "needs_clarification"
    assert result["selected_tool"] is None
    assert result["observation"] is None


def test_structured_with_unknown_category_returns_zero(fail_db):
    """Structured query for a nonexistent category must return 0, not crash."""
    graph = build_graph()
    result = graph.invoke({
        "query": "How many rows are in the NONEXISTENT category?",
        "trace": [],
        "db_path": str(fail_db),
    })
    assert result["route_result"].route == "structured"
    assert result["observation"] == 0


def test_out_of_scope_final_answer_is_refusal(fail_db):
    """Out-of-scope final_answer must be a non-empty refusal message."""
    graph = build_graph()
    result = graph.invoke({
        "query": "What is the weather in Paris?",
        "trace": [],
        "db_path": str(fail_db),
    })
    assert result["final_answer"]
    assert len(result["final_answer"]) > 10  # Not empty


def test_empty_query_routes_to_clarification(fail_db):
    """Empty query sent directly to graph must route to clarification."""
    graph = build_graph()
    result = graph.invoke({
        "query": "",
        "trace": [],
        "db_path": str(fail_db),
    })
    assert result["route_result"].route == "needs_clarification"
    assert result["selected_tool"] is None
