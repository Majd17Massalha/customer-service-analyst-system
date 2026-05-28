"""CLI entry point for the Customer Service Analyst Agent.

Usage:
    python main.py --session <session_id>
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _configure_logging() -> None:
    Path("outputs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler("outputs/agent.log", encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Customer Service Analyst Agent — interactive CLI"
    )
    parser.add_argument(
        "--session",
        required=True,
        metavar="SESSION_ID",
        help="Session identifier for this conversation",
    )
    args = parser.parse_args()

    _configure_logging()

    from src.cli.chat_loop import run_chat_loop
    run_chat_loop(session_id=args.session)


if __name__ == "__main__":
    main()
