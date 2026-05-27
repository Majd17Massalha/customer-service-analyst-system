"""Deterministic DuckDB analytics tools for the customer-support dataset.

All numerical answers come from SQL queries — never from LLM inference.
Each public function is self-contained and MCP-ready (plain args/return types).
"""

import logging
import time
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "outputs" / "customer_support.duckdb"
TABLE = "customer_support_train"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=True)


def _require_nonempty_str(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got: {value!r}")


def _require_positive_int(value: object, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer, got: {value!r}")


# ---------------------------------------------------------------------------
# Public analytics tools
# ---------------------------------------------------------------------------

def count_total_rows(db_path: str | Path = DB_PATH) -> int:
    """Return the total number of rows in the training dataset."""
    t0 = time.perf_counter()
    con = _connect(db_path)
    try:
        result: int = con.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    finally:
        con.close()
    logger.info("count_total_rows → %d (%.3fs)", result, time.perf_counter() - t0)
    return result


def count_by_category(category: str, db_path: str | Path = DB_PATH) -> int:
    """Return the number of rows whose category matches *category* (case-insensitive).

    Returns 0 when no rows match; raises ValueError on invalid input.
    """
    _require_nonempty_str(category, "category")
    t0 = time.perf_counter()
    con = _connect(db_path)
    try:
        result: int = con.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE LOWER(category) = LOWER(?)",
            [category],
        ).fetchone()[0]
    finally:
        con.close()
    logger.info("count_by_category(%r) → %d (%.3fs)", category, result, time.perf_counter() - t0)
    return result


def count_by_intent(intent: str, db_path: str | Path = DB_PATH) -> int:
    """Return the number of rows whose intent matches *intent* (case-insensitive).

    Returns 0 when no rows match; raises ValueError on invalid input.
    """
    _require_nonempty_str(intent, "intent")
    t0 = time.perf_counter()
    con = _connect(db_path)
    try:
        result: int = con.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE LOWER(intent) = LOWER(?)",
            [intent],
        ).fetchone()[0]
    finally:
        con.close()
    logger.info("count_by_intent(%r) → %d (%.3fs)", intent, result, time.perf_counter() - t0)
    return result


def get_top_categories(limit: int = 10, db_path: str | Path = DB_PATH) -> list[dict]:
    """Return the top *limit* categories ranked by row count descending.

    Each entry is ``{"category": str, "count": int}``.
    Raises ValueError when *limit* is not a positive integer.
    """
    _require_positive_int(limit, "limit")
    t0 = time.perf_counter()
    con = _connect(db_path)
    try:
        rows = con.execute(
            f"SELECT category, COUNT(*) AS count FROM {TABLE} "
            "GROUP BY category ORDER BY count DESC LIMIT ?",
            [limit],
        ).fetchall()
    finally:
        con.close()
    result = [{"category": row[0], "count": row[1]} for row in rows]
    logger.info(
        "get_top_categories(limit=%d) → %d categories (%.3fs)",
        limit, len(result), time.perf_counter() - t0,
    )
    return result


def search_examples(
    keyword: str,
    limit: int = 5,
    db_path: str | Path = DB_PATH,
) -> list[dict]:
    """Return up to *limit* examples whose instruction contains *keyword* (case-insensitive).

    Uses a literal substring match (no SQL wildcards) to avoid injection.
    Each entry is ``{"flags": str, "instruction": str, "category": str, "intent": str}``.
    Raises ValueError on invalid inputs; returns ``[]`` when nothing matches.
    """
    _require_nonempty_str(keyword, "keyword")
    _require_positive_int(limit, "limit")
    t0 = time.perf_counter()
    con = _connect(db_path)
    try:
        rows = con.execute(
            f"SELECT flags, instruction, category, intent FROM {TABLE} "
            "WHERE contains(LOWER(instruction), LOWER(?)) LIMIT ?",
            [keyword, limit],
        ).fetchall()
    finally:
        con.close()
    result = [
        {"flags": r[0], "instruction": r[1], "category": r[2], "intent": r[3]}
        for r in rows
    ]
    logger.info(
        "search_examples(%r, limit=%d) → %d rows (%.3fs)",
        keyword, limit, len(result), time.perf_counter() - t0,
    )
    return result
