"""Manual review scoring framework for human evaluation.

Provides utilities to record and aggregate human scores on GoldenEntry
objects. No LLM calls. All scoring is performed by a human evaluator.

Scoring rubric (1–5):
  5 — Correct route, correct tool, answer is accurate and well-framed
  4 — Correct route and tool, minor answer formatting issue
  3 — Correct route, wrong tool selection or incomplete answer
  2 — Wrong route or missing refusal; answer contains incorrect data
  1 — Crash, empty response, data leakage, or completely wrong behavior

Pass/fail threshold: score >= 3 counts as pass.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from src.evaluation.golden_dataset import GoldenEntry


PASS_THRESHOLD = 3  # score >= PASS_THRESHOLD → pass


def score_entry(
    entry: GoldenEntry,
    pass_fail: bool,
    score: int,
    notes: str = "",
    evaluator: str = "",
) -> GoldenEntry:
    """Record a human score on a GoldenEntry. Returns the updated entry.

    Args:
        entry:     The GoldenEntry to score.
        pass_fail: True if the agent response was acceptable, False otherwise.
        score:     Integer 1–5 per the rubric above.
        notes:     Free-text observation from the evaluator.
        evaluator: Name or identifier of the human evaluator.
    """
    if score not in range(1, 6):
        raise ValueError(f"score must be 1–5, got {score!r}")
    entry.pass_fail = pass_fail
    entry.score = score
    entry.notes = notes
    entry.evaluator = evaluator
    return entry


def auto_pass_from_score(entry: GoldenEntry) -> GoldenEntry:
    """Set pass_fail based on score >= PASS_THRESHOLD. Mutates entry in place."""
    if entry.score is not None:
        entry.pass_fail = entry.score >= PASS_THRESHOLD
    return entry


def print_review_summary(entries: list[GoldenEntry]) -> None:
    """Print per-entry review status to stdout for quick inspection."""
    evaluated = [e for e in entries if e.pass_fail is not None]
    pending = [e for e in entries if e.pass_fail is None]

    print(f"=== Manual Review Status: {len(evaluated)}/{len(entries)} evaluated ===\n")

    for e in entries:
        status = "PASS" if e.pass_fail is True else ("FAIL" if e.pass_fail is False else "PENDING")
        score_str = f"  score={e.score}/5" if e.score is not None else ""
        print(f"[{status}]{score_str}  [{e.category}]  {e.query[:60]!r}")
        if e.notes:
            print(f"         Note: {e.notes}")

    if pending:
        print(f"\n{len(pending)} entries still pending review.")


def export_review_csv(entries: list[GoldenEntry], path: str | Path) -> None:
    """Export all entries to a CSV file for spreadsheet-based review."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "category", "query", "expected_route", "expected_tool",
        "expected_behavior", "expected_failure_mode",
        "pass_fail", "score", "notes", "evaluator",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for e in entries:
            row = {k: getattr(e, k, "") for k in fieldnames}
            row["pass_fail"] = "" if e.pass_fail is None else ("PASS" if e.pass_fail else "FAIL")
            writer.writerow(row)


def load_review_csv(path: str | Path) -> list[dict]:
    """Load review results from a CSV previously exported by export_review_csv.

    Returns a list of dicts (not GoldenEntry objects) since the CSV may
    contain evaluator annotations not present in the original dataset.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    # Normalize pass_fail field
    for row in rows:
        pf = row.get("pass_fail", "").strip().upper()
        row["pass_fail"] = True if pf == "PASS" else (False if pf == "FAIL" else None)
        score_str = row.get("score", "").strip()
        row["score"] = int(score_str) if score_str.isdigit() else None
    return rows


def export_review_json(entries: list[GoldenEntry], path: str | Path) -> None:
    """Export all entries to JSON for programmatic downstream use."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(e) for e in entries]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
