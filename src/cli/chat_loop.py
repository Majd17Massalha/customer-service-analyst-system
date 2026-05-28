"""Interactive CLI chat loop.

Thin input/output layer only — all logic lives in agent and memory modules.
Prints operational trace fields (route, tool, observation, final_answer).
Never prints chain-of-thought, local paths, or raw dataset rows.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.agent.graph import build_graph
from src.memory.checkpoints import SessionState, load_session, save_session
from src.memory.user_profile import load_profile, save_profile, update_profile_from_state

logger = logging.getLogger(__name__)

EXIT_COMMANDS: frozenset[str] = frozenset({"exit", "quit", "q"})
_MAX_QUERY_STORE = 500
_MAX_OBS_DISPLAY = 300


def _print_trace(state: dict) -> None:
    """Print operational trace. No chain-of-thought, no local paths."""
    route_result = state.get("route_result")
    if route_result:
        print(f"  route       : {route_result.route}")
        print(f"  confidence  : {route_result.confidence:.2f}")

    selected_tool = state.get("selected_tool")
    if selected_tool:
        print(f"  tool        : {selected_tool}")

    tool_input = state.get("tool_input")
    if tool_input:
        print(f"  tool_input  : {tool_input}")

    observation = state.get("observation")
    if observation is not None:
        obs_str = str(observation)
        if len(obs_str) > _MAX_OBS_DISPLAY:
            obs_str = obs_str[:_MAX_OBS_DISPLAY] + " ..."
        print(f"  observation : {obs_str}")

    final_answer = state.get("final_answer") or state.get("response")
    if final_answer:
        print(f"\nAnswer: {final_answer}")


def _update_session_from_state(session: SessionState, state: dict, query: str) -> SessionState:
    """Extract non-sensitive routing metadata into session. Never stores raw dataset rows."""
    session.last_query = query[:_MAX_QUERY_STORE]

    route_result = state.get("route_result")
    if route_result:
        session.last_route = route_result.route

    session.last_tool = state.get("selected_tool")

    tool_input = state.get("tool_input") or {}
    session.last_category = tool_input.get("category")
    session.last_intent = tool_input.get("intent")
    session.last_keyword = tool_input.get("keyword")

    return session


def run_chat_loop(session_id: str, db_path: Optional[str] = None) -> None:
    """Start an interactive chat loop for the given session ID."""
    graph = build_graph()
    session = load_session(session_id)
    profile = load_profile(session_id)

    print("Customer Service Analyst Agent")
    print(f"Session: {session_id}")
    print("Type 'exit', 'quit', or 'q' to stop.\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not query:
            continue

        if query.lower() in EXIT_COMMANDS:
            print("Session ended.")
            break

        logger.info("session=%s route=pending query_len=%d", session_id, len(query))

        print("---")
        try:
            initial_state: dict = {"query": query, "trace": []}
            if db_path:
                initial_state["db_path"] = db_path

            result = graph.invoke(initial_state)
            _print_trace(result)

            session = _update_session_from_state(session, result, query)
            save_session(session)

            profile = update_profile_from_state(profile, result)
            save_profile(profile)

        except Exception as e:
            logger.error("session=%s error=%s", session_id, e)
            print(f"Error: {e}")

        print("---\n")
