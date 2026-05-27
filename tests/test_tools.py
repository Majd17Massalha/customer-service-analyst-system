"""Tests for analytics_tools — deterministic DuckDB layer.

All tests use an isolated tmp_path DuckDB fixture with known data,
so results are fully deterministic and independent of the production DB.
"""

import duckdb
import pytest

from src.tools.analytics_tools import (
    count_by_category,
    count_by_intent,
    count_total_rows,
    get_top_categories,
    search_examples,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

_ROWS = [
    ("B",   "how do I cancel my order?",       "ORDER",    "cancel_order",    "You can cancel via..."),
    ("BQ",  "I want a refund please",           "REFUND",   "get_refund",      "We can process..."),
    ("",    "track my shipment",                "SHIPPING", "track_shipment",  "Your shipment is..."),
    ("B",   "cancel this order now",            "ORDER",    "cancel_order",    "Sure, cancelling..."),
    ("Z",   "refund request for my order 123",  "REFUND",   "get_refund",      "Refund initiated..."),
]


@pytest.fixture()
def test_db(tmp_path):
    db_file = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_file))
    con.execute(
        "CREATE TABLE customer_support_train "
        "(flags VARCHAR, instruction VARCHAR, category VARCHAR, intent VARCHAR, response VARCHAR)"
    )
    con.executemany("INSERT INTO customer_support_train VALUES (?, ?, ?, ?, ?)", _ROWS)
    con.close()
    return db_file


# ---------------------------------------------------------------------------
# count_total_rows
# ---------------------------------------------------------------------------

def test_count_total_rows(test_db):
    assert count_total_rows(db_path=test_db) == 5


# ---------------------------------------------------------------------------
# count_by_category
# ---------------------------------------------------------------------------

def test_count_by_category_order(test_db):
    assert count_by_category("ORDER", db_path=test_db) == 2


def test_count_by_category_refund(test_db):
    assert count_by_category("REFUND", db_path=test_db) == 2


def test_count_by_category_case_insensitive(test_db):
    assert count_by_category("order", db_path=test_db) == 2
    assert count_by_category("Order", db_path=test_db) == 2


def test_count_by_category_no_match_returns_zero(test_db):
    assert count_by_category("NONEXISTENT", db_path=test_db) == 0


def test_count_by_category_empty_string_raises(test_db):
    with pytest.raises(ValueError):
        count_by_category("", db_path=test_db)


def test_count_by_category_whitespace_raises(test_db):
    with pytest.raises(ValueError):
        count_by_category("   ", db_path=test_db)


def test_count_by_category_non_string_raises(test_db):
    with pytest.raises(ValueError):
        count_by_category(42, db_path=test_db)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# count_by_intent
# ---------------------------------------------------------------------------

def test_count_by_intent_known(test_db):
    assert count_by_intent("cancel_order", db_path=test_db) == 2


def test_count_by_intent_case_insensitive(test_db):
    assert count_by_intent("CANCEL_ORDER", db_path=test_db) == 2


def test_count_by_intent_no_match_returns_zero(test_db):
    assert count_by_intent("unknown_intent", db_path=test_db) == 0


def test_count_by_intent_empty_string_raises(test_db):
    with pytest.raises(ValueError):
        count_by_intent("", db_path=test_db)


def test_count_by_intent_whitespace_raises(test_db):
    with pytest.raises(ValueError):
        count_by_intent("  ", db_path=test_db)


def test_count_by_intent_non_string_raises(test_db):
    with pytest.raises(ValueError):
        count_by_intent(None, db_path=test_db)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# get_top_categories
# ---------------------------------------------------------------------------

def test_get_top_categories_returns_list_of_dicts(test_db):
    results = get_top_categories(limit=3, db_path=test_db)
    assert isinstance(results, list)
    assert all({"category", "count"} <= r.keys() for r in results)


def test_get_top_categories_descending_order(test_db):
    results = get_top_categories(limit=10, db_path=test_db)
    counts = [r["count"] for r in results]
    assert counts == sorted(counts, reverse=True)


def test_get_top_categories_limit_respected(test_db):
    assert len(get_top_categories(limit=1, db_path=test_db)) == 1
    assert len(get_top_categories(limit=2, db_path=test_db)) == 2


def test_get_top_categories_covers_all_when_limit_large(test_db):
    # fixture has 3 distinct categories
    results = get_top_categories(limit=100, db_path=test_db)
    assert len(results) == 3


def test_get_top_categories_zero_limit_raises(test_db):
    with pytest.raises(ValueError):
        get_top_categories(limit=0, db_path=test_db)


def test_get_top_categories_negative_limit_raises(test_db):
    with pytest.raises(ValueError):
        get_top_categories(limit=-5, db_path=test_db)


def test_get_top_categories_string_limit_raises(test_db):
    with pytest.raises(ValueError):
        get_top_categories(limit="ten", db_path=test_db)  # type: ignore[arg-type]


def test_get_top_categories_bool_limit_raises(test_db):
    # bool is a subclass of int in Python; True == 1 but should be rejected
    with pytest.raises(ValueError):
        get_top_categories(limit=True, db_path=test_db)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# search_examples
# ---------------------------------------------------------------------------

def test_search_examples_match(test_db):
    results = search_examples("cancel", db_path=test_db)
    assert len(results) >= 1
    assert all("instruction" in r for r in results)


def test_search_examples_case_insensitive(test_db):
    lower = search_examples("cancel", db_path=test_db)
    upper = search_examples("CANCEL", db_path=test_db)
    assert len(lower) == len(upper)


def test_search_examples_no_match_returns_empty(test_db):
    assert search_examples("zzznomatch", db_path=test_db) == []


def test_search_examples_limit_respected(test_db):
    # "order" appears in 3 rows of _ROWS; limit=1 should return exactly 1
    results = search_examples("order", limit=1, db_path=test_db)
    assert len(results) == 1


def test_search_examples_result_fields(test_db):
    results = search_examples("refund", db_path=test_db)
    for r in results:
        assert set(r.keys()) == {"flags", "instruction", "category", "intent"}


def test_search_examples_empty_keyword_raises(test_db):
    with pytest.raises(ValueError):
        search_examples("", db_path=test_db)


def test_search_examples_whitespace_keyword_raises(test_db):
    with pytest.raises(ValueError):
        search_examples("   ", db_path=test_db)


def test_search_examples_invalid_limit_raises(test_db):
    with pytest.raises(ValueError):
        search_examples("cancel", limit=0, db_path=test_db)


def test_search_examples_negative_limit_raises(test_db):
    with pytest.raises(ValueError):
        search_examples("cancel", limit=-1, db_path=test_db)
