"""Long-term user profile store.

Persists only distilled, non-sensitive facts about the user to
outputs/memory/profiles/<safe_id>.json.
Never stores raw queries, dataset rows, API keys, or any PII.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from src.memory.checkpoints import sanitize_session_id

logger = logging.getLogger(__name__)

PROFILES_DIR = Path("outputs/memory/profiles")

_NEVER_STORE: frozenset[str] = frozenset({
    "api_key", "token", "password", "secret", "credential",
    "email", "phone", "ssn", "raw_query", "dataset_row",
})


@dataclass
class UserProfile:
    session_id: str
    user_name: Optional[str] = None
    preferred_topics: list[str] = field(default_factory=list)
    frequent_categories: list[str] = field(default_factory=list)
    frequent_intents: list[str] = field(default_factory=list)
    preferred_output_style: Optional[str] = None


def _profile_path(session_id: str) -> Path:
    return PROFILES_DIR / f"{sanitize_session_id(session_id)}.json"


def save_profile(profile: UserProfile) -> None:
    """Persist user profile to JSON. Strips any field in _NEVER_STORE (defensive)."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = _profile_path(profile.session_id)
    data = asdict(profile)
    for key in list(data.keys()):
        if key in _NEVER_STORE:
            del data[key]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.debug("profile saved: %s", path)


def load_profile(session_id: str) -> UserProfile:
    """Load user profile from JSON, or return a fresh profile if not found."""
    path = _profile_path(session_id)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            logger.debug("profile loaded: %s", path)
            return UserProfile(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("corrupted profile %s: %s — returning fresh profile", path, e)
    return UserProfile(session_id=session_id)


def update_profile_from_state(profile: UserProfile, agent_state: dict) -> UserProfile:
    """Update profile with non-sensitive analytics metadata from agent state."""
    tool_input = agent_state.get("tool_input") or {}

    category = tool_input.get("category")
    if category and isinstance(category, str) and category not in profile.frequent_categories:
        profile.frequent_categories.append(category)

    intent = tool_input.get("intent")
    if intent and isinstance(intent, str) and intent not in profile.frequent_intents:
        profile.frequent_intents.append(intent)

    return profile
