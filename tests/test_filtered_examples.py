import pytest

from src.tools.analytics_tools import get_filtered_examples


def test_refund_category_filter():
    rows = get_filtered_examples(
        category="REFUND",
        limit=5,
    )

    assert rows, "Expected at least one REFUND record"
    assert len(rows) <= 5

    for row in rows:
        assert row["category"] == "REFUND"


def test_cancel_order_intent_filter():
    rows = get_filtered_examples(
        intent="cancel_order",
        limit=5,
    )

    assert rows, "Expected at least one cancel_order record"
    assert len(rows) <= 5

    for row in rows:
        assert row["intent"] == "cancel_order"


def test_unknown_category_returns_empty():
    rows = get_filtered_examples(
        category="NONEXISTENT",
        limit=5,
    )

    assert rows == []


def test_missing_filters_are_rejected():
    with pytest.raises(ValueError):
        get_filtered_examples()


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_invalid_limits_are_rejected(limit):
    with pytest.raises(ValueError):
        get_filtered_examples(
            category="REFUND",
            limit=limit,
        )