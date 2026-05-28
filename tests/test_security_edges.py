"""Security edge case tests for the Customer Service Analyst Agent.

Tests that security boundaries are enforced: no data leakage into session
or profile storage, no path traversal via session IDs, no SQL injection
through parameterized queries, and no chain-of-thought exposure in CLI
trace output. All tests are deterministic — no LLM calls.
"""
from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

from src.agent.nodes import node_clarification_response, node_out_of_scope_response
from src.agent.router import route_query
from src.cli.chat_loop import _print_trace, _update_session_from_state
from src.memory.checkpoints import (
    SessionState,
    load_session,
    sanitize_session_id,
    save_session,
)
from src.memory.user_profile import (
    UserProfile,
    _NEVER_STORE,
    load_profile,
    save_profile,
    update_profile_from_state,
)
from src.tools.analytics_tools import count_by_category, count_total_rows, search_examples

_SAFE_CHAR_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")

# ---------------------------------------------------------------------------
# Shared isolated DuckDB fixture
# ---------------------------------------------------------------------------

_ROWS = [
    ("B",  "cancel my order",  "ORDER",  "cancel_order",  "You can cancel..."),
    ("BQ", "need refund",      "REFUND", "get_refund",    "We can process..."),
]


@pytest.fixture(scope="module")
def sec_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("sec") / "sec.duckdb"
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
# Session ID sanitization security
# ---------------------------------------------------------------------------

def test_path_traversal_stripped_from_session_id():
    """Path traversal sequences must not survive session ID sanitization."""
    result = sanitize_session_id("../../etc/passwd")
    assert ".." not in result
    assert "/" not in result
    assert "\\" not in result


def test_sql_injection_chars_stripped_from_session_id():
    """SQL injection characters must be replaced in session ID."""
    result = sanitize_session_id("'; DROP TABLE sessions; --")
    assert "'" not in result
    assert ";" not in result


def test_null_byte_stripped_from_session_id():
    """Null bytes must be stripped from session ID."""
    result = sanitize_session_id("session\x00id")
    assert "\x00" not in result


def test_session_id_length_capped_at_64():
    """Session ID must be capped at 64 characters."""
    result = sanitize_session_id("a" * 200)
    assert len(result) <= 64


def test_empty_session_id_becomes_default():
    """Empty session ID must become 'default_session'."""
    assert sanitize_session_id("") == "default_session"


def test_sanitized_session_id_has_only_safe_chars():
    """All returned session IDs must contain only alphanumeric, dash, underscore."""
    for raw in ["user@host", "my-session", "abc 123", "../../root", "'; DROP TABLE"]:
        result = sanitize_session_id(raw)
        if result != "default_session":
            assert _SAFE_CHAR_PATTERN.match(result), (
                f"Unsafe chars in sanitized ID {result!r} from input {raw!r}"
            )


# ---------------------------------------------------------------------------
# Data leakage prevention — session storage
# ---------------------------------------------------------------------------

def test_observation_not_stored_in_session():
    """_update_session_from_state must never copy observation content into session."""
    sensitive = "SENSITIVE_OBSERVATION_DATA_99999"
    session = SessionState(session_id="leak_test")
    state = {
        "route_result": type("R", (), {"route": "structured"})(),
        "selected_tool": "count_by_category",
        "tool_input": {"category": "ORDER"},
        "observation": sensitive,
        "final_answer": "The ORDER category has rows.",
    }
    updated = _update_session_from_state(session, state, "how many order rows?")
    session_dict = dataclasses.asdict(updated)
    for field_name, field_value in session_dict.items():
        if isinstance(field_value, str):
            assert sensitive not in field_value, (
                f"Sensitive observation leaked into session field {field_name!r}"
            )


def test_query_truncated_at_500_chars_in_session():
    """Queries longer than 500 chars must be truncated when stored in session."""
    long_query = "how many " + "x" * 1000
    session = SessionState(session_id="trunc_test")
    state = {
        "route_result": type("R", (), {"route": "structured"})(),
        "selected_tool": None,
        "tool_input": {},
        "observation": None,
        "final_answer": "answer",
    }
    updated = _update_session_from_state(session, state, long_query)
    assert updated.last_query is not None
    assert len(updated.last_query) <= 500


def test_raw_dataset_rows_not_in_session(sec_db, tmp_path):
    """Session JSON file must not contain raw dataset instruction text."""
    # Run a real search to get observations that include raw instruction text
    results = search_examples("cancel", db_path=sec_db)
    assert results  # ensure we got some data

    raw_instruction = results[0]["instruction"]  # actual dataset row

    # Session update from a state that would include this in observation
    session = SessionState(session_id="no_raw_rows")
    state = {
        "route_result": type("R", (), {"route": "unstructured"})(),
        "selected_tool": "search_examples",
        "tool_input": {"keyword": "cancel", "limit": 5},
        "observation": results,   # contains raw rows
        "final_answer": "Based on dataset examples only:\n- ...",
    }
    updated = _update_session_from_state(session, state, "examples of cancel")

    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        save_session(updated)
        session_file = tmp_path / "no_raw_rows.json"
        content = session_file.read_text(encoding="utf-8")

    assert raw_instruction not in content, (
        "Raw dataset instruction text found in session JSON file"
    )


# ---------------------------------------------------------------------------
# Data leakage prevention — profile storage
# ---------------------------------------------------------------------------

def test_never_store_keys_absent_from_profile_json(tmp_path):
    """Saved profile JSON must not contain any _NEVER_STORE key names."""
    profile = UserProfile(session_id="never_store_test")
    with patch("src.memory.user_profile.PROFILES_DIR", tmp_path):
        save_profile(profile)
        content = (tmp_path / "never_store_test.json").read_text(encoding="utf-8")

    for key in _NEVER_STORE:
        assert f'"{key}"' not in content, (
            f"Sensitive key {key!r} found in profile JSON"
        )


def test_profile_does_not_store_observation_data():
    """update_profile_from_state must never read from observation."""
    profile = UserProfile(session_id="obs_profile_test")
    state = {
        "tool_input": {"category": "ORDER"},
        "observation": ["sensitive", "raw", "data", "from", "dataset"],
    }
    updated = update_profile_from_state(profile, state)
    assert "sensitive" not in updated.frequent_categories
    assert "sensitive" not in updated.preferred_topics
    assert "raw" not in updated.frequent_categories


def test_profile_update_reads_only_tool_input():
    """Profile update must only read category and intent from tool_input."""
    profile = UserProfile(session_id="tool_input_test")
    state = {
        "tool_input": {"category": "REFUND", "intent": "get_refund"},
        "observation": [{"instruction": "I want a refund"}],
        "query": "how many refund rows?",
    }
    updated = update_profile_from_state(profile, state)
    assert "REFUND" in updated.frequent_categories
    assert "get_refund" in updated.frequent_intents
    assert "I want a refund" not in str(updated.frequent_categories)


# ---------------------------------------------------------------------------
# SQL injection prevention
# ---------------------------------------------------------------------------

def test_sql_injection_in_category_safe(sec_db):
    """SQL injection in category parameter must return 0 and not execute injected SQL."""
    result = count_by_category(
        "'; DROP TABLE customer_support_train; --", db_path=sec_db
    )
    assert result == 0
    # Verify table survives injection attempt
    total = count_total_rows(db_path=sec_db)
    assert total == 2  # Both original rows intact


def test_sql_injection_in_keyword_safe(sec_db):
    """SQL injection in search keyword must return a list safely."""
    result = search_examples("'; DROP TABLE--", db_path=sec_db)
    assert isinstance(result, list)
    # Verify table survives
    total = count_total_rows(db_path=sec_db)
    assert total == 2


# ---------------------------------------------------------------------------
# Chain-of-thought / trace boundary
# ---------------------------------------------------------------------------

def test_print_trace_never_prints_trace_list(capsys):
    """_print_trace must never expose the internal trace list (chain-of-thought)."""
    state = {
        "route_result": type("R", (), {"route": "structured", "confidence": 0.9})(),
        "selected_tool": "count_total_rows",
        "tool_input": {},
        "observation": 42,
        "final_answer": "The dataset has 42 rows.",
        "trace": ["INTERNAL_COT_STEP_1", "INTERNAL_COT_STEP_2"],
    }
    _print_trace(state)
    captured = capsys.readouterr()
    assert "INTERNAL_COT_STEP_1" not in captured.out
    assert "INTERNAL_COT_STEP_2" not in captured.out


def test_print_trace_does_not_expose_windows_paths(capsys):
    """_print_trace must not print Windows absolute path patterns."""
    state = {
        "route_result": type("R", (), {"route": "structured", "confidence": 0.9})(),
        "selected_tool": "count_total_rows",
        "tool_input": {},
        "observation": 10,
        "final_answer": "10 rows found.",
        "trace": [],
    }
    _print_trace(state)
    captured = capsys.readouterr()
    assert "C:\\" not in captured.out
    assert "\\Users\\" not in captured.out


def test_out_of_scope_node_exposes_no_dataset_data():
    """Out-of-scope refusal must not include any dataset observation."""
    result_route = route_query("Who won the Champions League?")
    state = {
        "route_result": result_route,
        "query": "Who won the Champions League?",
        "trace": [],
    }
    result = node_out_of_scope_response(state)
    assert result["selected_tool"] is None
    assert result["observation"] is None


def test_clarification_node_exposes_no_dataset_data():
    """Clarification response must not include any dataset observation."""
    result_route = route_query("those")
    state = {
        "route_result": result_route,
        "query": "those",
        "trace": [],
    }
    result = node_clarification_response(state)
    assert result["selected_tool"] is None
    assert result["observation"] is None


# ---------------------------------------------------------------------------
# Filesystem security
# ---------------------------------------------------------------------------

def test_session_file_written_to_sanitized_path(tmp_path):
    """Session file must be written using the sanitized ID, not raw user input."""
    raw_id = "../../injected_session"
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        state = SessionState(session_id=raw_id)
        save_session(state)

    # Must NOT create a file via path traversal
    assert not (tmp_path / ".." / ".." / "injected_session.json").exists()
    # Must create a safe file inside SESSIONS_DIR
    safe_files = list(tmp_path.glob("*.json"))
    assert len(safe_files) == 1
    # Filename must contain only safe chars (no ../ or /)
    assert ".." not in safe_files[0].name
    assert "/" not in safe_files[0].name
