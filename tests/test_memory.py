"""Tests for short-term session memory and long-term user profile store.

Covers: session ID sanitization, save/load round-trips, default field values,
sensitive-data exclusion, and raw-dataset-row isolation.
All tests use tmp_path to avoid writing to the real outputs/ directory.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.memory.checkpoints import (
    SessionState,
    load_session,
    sanitize_session_id,
    save_session,
)
from src.memory.user_profile import (
    UserProfile,
    load_profile,
    save_profile,
    update_profile_from_state,
)


# ---------------------------------------------------------------------------
# Session ID sanitization
# ---------------------------------------------------------------------------

def test_sanitize_normal_id():
    assert sanitize_session_id("demo_session") == "demo_session"


def test_sanitize_alphanumeric():
    assert sanitize_session_id("Session123") == "Session123"


def test_sanitize_special_chars():
    result = sanitize_session_id("user@email.com")
    assert "@" not in result
    assert "." not in result
    assert "user" in result


def test_sanitize_path_traversal():
    result = sanitize_session_id("../../etc/passwd")
    assert ".." not in result
    assert "/" not in result
    assert "\\" not in result


def test_sanitize_empty_string():
    result = sanitize_session_id("")
    assert result == "default_session"


def test_sanitize_long_id():
    result = sanitize_session_id("a" * 100)
    assert len(result) <= 64


def test_sanitize_preserves_dash_and_underscore():
    assert sanitize_session_id("my-session_v2") == "my-session_v2"


def test_sanitize_spaces_become_underscores():
    result = sanitize_session_id("my session")
    assert " " not in result


# ---------------------------------------------------------------------------
# Session state: save / load round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_session(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        state = SessionState(
            session_id="test_session",
            last_query="How many rows?",
            last_route="structured",
            last_tool="count_total_rows",
        )
        save_session(state)
        loaded = load_session("test_session")

    assert loaded.session_id == "test_session"
    assert loaded.last_query == "How many rows?"
    assert loaded.last_route == "structured"
    assert loaded.last_tool == "count_total_rows"


def test_session_default_values():
    state = SessionState(session_id="fresh")
    assert state.last_query is None
    assert state.last_route is None
    assert state.last_tool is None
    assert state.last_category is None
    assert state.last_intent is None
    assert state.last_keyword is None
    assert state.last_result_offset is None


def test_load_missing_session_returns_fresh(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        loaded = load_session("nonexistent_session")
    assert loaded.session_id == "nonexistent_session"
    assert loaded.last_query is None


def test_session_creates_directory(tmp_path):
    sessions_dir = tmp_path / "sessions"
    with patch("src.memory.checkpoints.SESSIONS_DIR", sessions_dir):
        save_session(SessionState(session_id="dir_test"))
    assert sessions_dir.exists()


def test_session_file_contains_valid_json(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        save_session(SessionState(session_id="json_test", last_route="structured"))
        path = tmp_path / "json_test.json"
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
    assert data["last_route"] == "structured"


def test_session_round_trip_all_fields(tmp_path):
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        state = SessionState(
            session_id="full_test",
            last_query="What is the top category?",
            last_route="structured",
            last_tool="get_top_categories",
            last_category="ORDER",
            last_intent="cancel_order",
            last_keyword="cancel",
            last_result_offset=5,
        )
        save_session(state)
        loaded = load_session("full_test")

    assert loaded.last_category == "ORDER"
    assert loaded.last_intent == "cancel_order"
    assert loaded.last_keyword == "cancel"
    assert loaded.last_result_offset == 5


# ---------------------------------------------------------------------------
# User profile: save / load round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_profile(tmp_path):
    with patch("src.memory.user_profile.PROFILES_DIR", tmp_path):
        profile = UserProfile(
            session_id="prof_test",
            user_name="Alice",
            frequent_categories=["ORDER", "REFUND"],
            frequent_intents=["cancel_order"],
        )
        save_profile(profile)
        loaded = load_profile("prof_test")

    assert loaded.session_id == "prof_test"
    assert loaded.user_name == "Alice"
    assert "ORDER" in loaded.frequent_categories
    assert "cancel_order" in loaded.frequent_intents


def test_profile_default_values():
    profile = UserProfile(session_id="fresh_prof")
    assert profile.user_name is None
    assert profile.preferred_topics == []
    assert profile.frequent_categories == []
    assert profile.frequent_intents == []
    assert profile.preferred_output_style is None


def test_load_missing_profile_returns_fresh(tmp_path):
    with patch("src.memory.user_profile.PROFILES_DIR", tmp_path):
        loaded = load_profile("no_such_profile")
    assert loaded.session_id == "no_such_profile"
    assert loaded.frequent_categories == []


def test_profile_creates_directory(tmp_path):
    profiles_dir = tmp_path / "profiles"
    with patch("src.memory.user_profile.PROFILES_DIR", profiles_dir):
        save_profile(UserProfile(session_id="dir_test"))
    assert profiles_dir.exists()


def test_profile_file_contains_valid_json(tmp_path):
    with patch("src.memory.user_profile.PROFILES_DIR", tmp_path):
        save_profile(UserProfile(session_id="json_prof", user_name="Bob"))
        path = tmp_path / "json_prof.json"
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
    assert data["user_name"] == "Bob"


# ---------------------------------------------------------------------------
# Security: sensitive fields never written to disk
# ---------------------------------------------------------------------------

def test_profile_does_not_store_sensitive_keys(tmp_path):
    with patch("src.memory.user_profile.PROFILES_DIR", tmp_path):
        save_profile(UserProfile(session_id="secure_test"))
        content = (tmp_path / "secure_test.json").read_text()
    for bad_key in ("api_key", "token", "password", "secret", "credential"):
        assert bad_key not in content


def test_session_does_not_store_raw_dataset_rows(tmp_path):
    raw_instruction = "how do I cancel my order"  # verbatim dataset row text
    with patch("src.memory.checkpoints.SESSIONS_DIR", tmp_path):
        save_session(SessionState(session_id="data_test", last_query="How many rows?"))
        content = (tmp_path / "data_test.json").read_text()
    assert raw_instruction not in content


def test_profile_does_not_store_raw_dataset_rows(tmp_path):
    raw_instruction = "I want a refund please"  # verbatim dataset row text
    with patch("src.memory.user_profile.PROFILES_DIR", tmp_path):
        save_profile(UserProfile(session_id="no_raw_data"))
        content = (tmp_path / "no_raw_data.json").read_text()
    assert raw_instruction not in content


# ---------------------------------------------------------------------------
# update_profile_from_state
# ---------------------------------------------------------------------------

def test_update_profile_adds_category():
    profile = UserProfile(session_id="upd_test")
    updated = update_profile_from_state(profile, {"tool_input": {"category": "ORDER"}})
    assert "ORDER" in updated.frequent_categories


def test_update_profile_adds_intent():
    profile = UserProfile(session_id="upd_test")
    updated = update_profile_from_state(profile, {"tool_input": {"intent": "cancel_order"}})
    assert "cancel_order" in updated.frequent_intents


def test_update_profile_no_duplicates():
    profile = UserProfile(session_id="upd_test", frequent_categories=["ORDER"])
    updated = update_profile_from_state(profile, {"tool_input": {"category": "ORDER"}})
    assert updated.frequent_categories.count("ORDER") == 1


def test_update_profile_empty_tool_input():
    profile = UserProfile(session_id="upd_test")
    updated = update_profile_from_state(profile, {"tool_input": {}})
    assert updated.frequent_categories == []
    assert updated.frequent_intents == []


def test_update_profile_missing_tool_input():
    profile = UserProfile(session_id="upd_test")
    updated = update_profile_from_state(profile, {})
    assert updated.frequent_categories == []
    assert updated.frequent_intents == []
