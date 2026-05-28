"""Deterministic evaluation metrics for the Customer Service Analyst Agent.

Computes pass rates, route accuracy, and per-category breakdowns from
golden dataset results. No LLM calls. All metrics are computed from
explicit pass_fail annotations set during human review.
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.evaluation.golden_dataset import GoldenEntry


def compute_pass_rate(entries: list["GoldenEntry"]) -> float:
    """Return fraction of evaluated entries that passed (pass_fail=True).

    Skips entries where pass_fail is None (not yet evaluated).
    Returns 0.0 when no entries have been evaluated.
    """
    evaluated = [e for e in entries if e.pass_fail is not None]
    if not evaluated:
        return 0.0
    passed = sum(1 for e in evaluated if e.pass_fail is True)
    return passed / len(evaluated)


def compute_route_accuracy(entries: list["GoldenEntry"]) -> dict[str, float]:
    """Return per-route pass rate for evaluated entries.

    Returns a dict mapping route label to pass_rate (0.0–1.0).
    Only includes routes with at least one evaluated entry.
    """
    buckets: dict[str, list[bool]] = defaultdict(list)
    for e in entries:
        if e.pass_fail is not None:
            buckets[e.expected_route].append(e.pass_fail)
    return {
        route: sum(results) / len(results)
        for route, results in buckets.items()
    }


def compute_per_category_pass_rate(entries: list["GoldenEntry"]) -> dict[str, float]:
    """Return pass rate grouped by entry category taxonomy."""
    buckets: dict[str, list[bool]] = defaultdict(list)
    for e in entries:
        if e.pass_fail is not None and e.category:
            buckets[e.category].append(e.pass_fail)
    return {
        cat: sum(results) / len(results)
        for cat, results in buckets.items()
    }


def compute_average_score(entries: list["GoldenEntry"]) -> float:
    """Return mean human score (1–5) across evaluated entries.

    Returns 0.0 when no scores have been assigned.
    """
    scored = [e for e in entries if e.score is not None]
    if not scored:
        return 0.0
    return sum(e.score for e in scored) / len(scored)


def count_by_status(entries: list["GoldenEntry"]) -> dict[str, int]:
    """Return counts of pass / fail / not-evaluated entries."""
    passed = sum(1 for e in entries if e.pass_fail is True)
    failed = sum(1 for e in entries if e.pass_fail is False)
    pending = sum(1 for e in entries if e.pass_fail is None)
    return {"pass": passed, "fail": failed, "pending": pending, "total": len(entries)}


def summarize_evaluation(entries: list["GoldenEntry"]) -> dict:
    """Compute and return a complete evaluation summary dict."""
    return {
        "status_counts": count_by_status(entries),
        "overall_pass_rate": compute_pass_rate(entries),
        "route_accuracy": compute_route_accuracy(entries),
        "category_pass_rate": compute_per_category_pass_rate(entries),
        "average_score": compute_average_score(entries),
    }


def print_summary(entries: list["GoldenEntry"]) -> None:
    """Print a human-readable evaluation summary to stdout."""
    summary = summarize_evaluation(entries)
    counts = summary["status_counts"]

    print("=== Evaluation Summary ===")
    print(f"Total entries  : {counts['total']}")
    print(f"Evaluated      : {counts['pass'] + counts['fail']}")
    print(f"Pending        : {counts['pending']}")
    print(f"Pass rate      : {summary['overall_pass_rate']:.1%}")
    print(f"Average score  : {summary['average_score']:.2f} / 5.0")

    if summary["route_accuracy"]:
        print("\nPer-route pass rate:")
        for route, rate in sorted(summary["route_accuracy"].items()):
            print(f"  {route:<25} {rate:.1%}")

    if summary["category_pass_rate"]:
        print("\nPer-category pass rate:")
        for cat, rate in sorted(summary["category_pass_rate"].items()):
            print(f"  {cat:<20} {rate:.1%}")
