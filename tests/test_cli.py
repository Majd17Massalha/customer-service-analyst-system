"""Tests for the CLI chat loop layer.

Covers: EXIT_COMMANDS constant, _print_trace output format, _update_session_from_state
field extraction, exit behavior with mocked stdin, empty-input skipping, and
the guarantee that raw dataset rows are never stored in session state.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.cli.chat_loop import EXIT_COMMANDS, _print_trace, _update_session_from_state
from src.memory.checkpoints import SessionState


# ---------------------------------------------------------------------------
# EXIT_COMMANDS
# ---------------------------------------------------------------------------

def test_exit_commands_include_exit():
    assert "exit" in EXIT_COMMANDS


def test_exit_commands_include_quit():
    assert "quit" in EXIT_COMMANDS


def test_exit_commands_include_q():
    assert "q" in EXIT_COMMANDS


def test_exit_commands_case_sensitive():
    assert "EXIT" not in EXIT_COMMANDS
    assert "Quit" not in EXIT_COMMANDS


# ---------------------------------------------------------------------------
# _print_trace output format
# ---------------------------------------------------------------------------

def _mock_route_result(route: str = "structured", confidence: float = 0.92) -> MagicMock:
    rr = MagicMock()
    rr.route = route
    rr.confidence = confidence
    return rr


def test_print_trace_shows_route_and_tool(capsys):
    state = {
        "route_result": _mock_route_result("structured", 0.92),
        "selected_tool": "count_total_rows",
        "tool_input": {},
        "observation": 5,
        "final_answer": "The dataset contains 5 rows.",
    }
    _print_trace(state)
    out = capsys.readouterr().out
    assert "structured" in out
    assert "count_total_rows" in out
    assert "The dataset contains 5 rows." in out


def test_print_trace_shows_tool_input(capsys):
    state = {
        "route_result": _mock_route_result("structured"),
        "selected_tool": "count_by_category",
        "tool_input": {"category": "ORDER"},
        "observation": 2,
        "final_answer": "The ORDER category has 2 rows.",
    }
    _print_trace(state)
    out = capsys.readouterr().out
    assert "ORDER" in out


def test_print_trace_out_of_scope(capsys):
    state = {
        "route_result": _mock_route_result("out_of_scope", 0.95),
        "selected_tool": None,
        "tool_input": {},
        "observation": None,
        "final_answer": "I can only answer questions about the dataset.",
    }
    _print_trace(state)
    out = capsys.readouterr().out
    assert "out_of_scope" in out
    assert "I can only answer" in out


def test_print_trace_truncates_long_observation(capsys):
    long_obs = "x" * 600
    state = {
        "route_result": _mock_route_result("unstructured"),
        "selected_tool": "search_examples",
        "tool_input": {"keyword": "cancel"},
        "observation": long_obs,
        "final_answer": "Based on dataset examples only:",
    }
    _print_trace(state)
    out = capsys.readouterr().out
    obs_lines = [ln for ln in out.splitlines() if "observation" in ln]
    assert len(obs_lines) == 1
    assert len(obs_lines[0]) < 400


def test_print_trace_no_chain_of_thought(capsys):
    state = {
        "route_result": _mock_route_result("structured"),
        "selected_tool": "count_total_rows",
        "tool_input": {},
        "observation": 5,
        "final_answer": "5 rows.",
        "trace": ["[route_query] route=structured", "[structured] tool=count_total_rows"],
    }
    _print_trace(state)
    out = capsys.readouterr().out
    assert "[route_query]" not in out
    assert "[structured]" not in out


def test_print_trace_no_tool_when_none(capsys):
    state = {
        "route_result": _mock_route_result("needs_clarification", 0.85),
        "selected_tool": None,
        "tool_input": {},
        "observation": None,
        "final_answer": "Could you provide more context?",
    }
    _print_trace(state)
    out = capsys.readouterr().out
    assert "tool        :" not in out
    assert "Could you provide more context?" in out


# ---------------------------------------------------------------------------
# _update_session_from_state field extraction
# ---------------------------------------------------------------------------

def test_update_session_stores_route():
    session = SessionState(session_id="s1")
    rr = _mock_route_result("structured")
    updated = _update_session_from_state(
        session,
        {"route_result": rr, "selected_tool": "count_total_rows", "tool_input": {}},
        "How many rows?",
    )
    assert updated.last_route == "structured"


def test_update_session_stores_tool_and_category():
    session = SessionState(session_id="s1")
    rr = _mock_route_result("structured")
    updated = _update_session_from_state(
        session,
        {"route_result": rr, "selected_tool": "count_by_category", "tool_input": {"category": "ORDER"}},
        "How many ORDER rows?",
    )
    assert updated.last_tool == "count_by_category"
    assert updated.last_category == "ORDER"


def test_update_session_stores_intent():
    session = SessionState(session_id="s1")
    rr = _mock_route_result("structured")
    updated = _update_session_from_state(
        session,
        {"route_result": rr, "selected_tool": "count_by_intent", "tool_input": {"intent": "cancel_order"}},
        "How many cancel_order?",
    )
    assert updated.last_intent == "cancel_order"


def test_update_session_stores_keyword():
    session = SessionState(session_id="s1")
    rr = _mock_route_result("unstructured")
    updated = _update_session_from_state(
        session,
        {"route_result": rr, "selected_tool": "search_examples", "tool_input": {"keyword": "cancel", "limit": 5}},
        "Show examples of cancel",
    )
    assert updated.last_keyword == "cancel"


def test_update_session_truncates_long_query():
    session = SessionState(session_id="s1")
    rr = _mock_route_result("needs_clarification")
    updated = _update_session_from_state(
        session,
        {"route_result": rr, "selected_tool": None, "tool_input": {}},
        "A" * 600,
    )
    assert len(updated.last_query) <= 500


def test_update_session_does_not_store_raw_dataset_rows():
    """Observation (raw rows) must not leak into session state fields."""
    session = SessionState(session_id="s1")
    rr = _mock_route_result("unstructured")
    raw_row = "how do I cancel my order"
    updated = _update_session_from_state(
        session,
        {
            "route_result": rr,
            "selected_tool": "search_examples",
            "tool_input": {"keyword": "cancel"},
            "observation": [
                {"instruction": raw_row, "category": "ORDER", "intent": "cancel_order", "flags": "B"}
            ],
        },
        "Show examples of cancel",
    )
    stored = str(vars(updated))
    assert raw_row not in stored


# ---------------------------------------------------------------------------
# run_chat_loop exit / flow behavior (mocked stdin)
# ---------------------------------------------------------------------------

def test_run_chat_loop_exits_on_q(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("src.memory.user_profile.PROFILES_DIR", tmp_path / "profiles"), \
         patch("builtins.input", side_effect=["q"]):
        from src.cli.chat_loop import run_chat_loop
        run_chat_loop(session_id="exit_test_q")


def test_run_chat_loop_exits_on_exit(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("src.memory.user_profile.PROFILES_DIR", tmp_path / "profiles"), \
         patch("builtins.input", side_effect=["exit"]):
        from src.cli.chat_loop import run_chat_loop
        run_chat_loop(session_id="exit_test_exit")


def test_run_chat_loop_exits_on_quit(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("src.memory.user_profile.PROFILES_DIR", tmp_path / "profiles"), \
         patch("builtins.input", side_effect=["quit"]):
        from src.cli.chat_loop import run_chat_loop
        run_chat_loop(session_id="exit_test_quit")


def test_run_chat_loop_skips_empty_input(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("src.memory.user_profile.PROFILES_DIR", tmp_path / "profiles"), \
         patch("builtins.input", side_effect=["", "   ", "q"]):
        from src.cli.chat_loop import run_chat_loop
        run_chat_loop(session_id="empty_test")


def test_run_chat_loop_exits_on_eof(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("src.memory.user_profile.PROFILES_DIR", tmp_path / "profiles"), \
         patch("builtins.input", side_effect=EOFError):
        from src.cli.chat_loop import run_chat_loop
        run_chat_loop(session_id="eof_test")
