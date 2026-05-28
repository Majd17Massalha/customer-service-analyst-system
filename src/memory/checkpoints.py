"""Short-term session state store.

Persists lightweight routing metadata per session_id to
outputs/memory/sessions/<safe_id>.json.
Never stores raw dataset rows, full query text beyond a safe limit,
or any secrets / credentials.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path("outputs/memory/sessions")

_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_\-]")
_MAX_ID_LEN = 64


def sanitize_session_id(session_id: str) -> str:
    """Return a filesystem-safe session ID (alphanumeric, dash, underscore; max 64 chars)."""
    safe = _SAFE_CHARS.sub("_", str(session_id))
    return safe[:_MAX_ID_LEN] if safe else "default_session"


@dataclass
class SessionState:
    session_id: str
    last_query: Optional[str] = None
    last_route: Optional[str] = None
    last_tool: Optional[str] = None
    last_category: Optional[str] = None
    last_intent: Optional[str] = None
    last_keyword: Optional[str] = None
    last_result_offset: Optional[int] = None


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{sanitize_session_id(session_id)}.json"


def save_session(state: SessionState) -> None:
    """Persist session state to JSON. Does not store raw dataset rows."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_path(state.session_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(state), f, indent=2)
    logger.debug("session saved: %s", path)


def load_session(session_id: str) -> SessionState:
    """Load session state from JSON, or return a fresh state if not found."""
    path = _session_path(session_id)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            logger.debug("session loaded: %s", path)
            return SessionState(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("corrupted session %s: %s — returning fresh state", path, e)
    return SessionState(session_id=session_id)
