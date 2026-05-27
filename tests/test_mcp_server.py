"""Tests for the MCP server layer.

Two concerns:
  1. Schema validation — Pydantic models reject bad inputs before the DB is touched.
  2. Wrapper behaviour — each tool delegates to the correct analytics function.

No MCP server process is started; tool functions are called directly as
ordinary Python callables, which FastMCP supports.
"""

from unittest.mock import patch, call

import pytest
from pydantic import ValidationError

from src.mcp.schemas import (
    CountByCategoryInput,
    CountByIntentInput,
    GetTopCategoriesInput,
    SearchExamplesInput,
)
import src.mcp.server as server


# ---------------------------------------------------------------------------
# Schema: CountByCategoryInput
# ---------------------------------------------------------------------------

class TestCountByCategoryInput:
    def test_valid(self):
        m = CountByCategoryInput(category="ORDER")
        assert m.category == "ORDER"

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            CountByCategoryInput(category="")

    def test_whitespace_raises(self):
        with pytest.raises(ValidationError):
            CountByCategoryInput(category="   ")

    def test_missing_raises(self):
        with pytest.raises(ValidationError):
            CountByCategoryInput()


# ---------------------------------------------------------------------------
# Schema: CountByIntentInput
# ---------------------------------------------------------------------------

class TestCountByIntentInput:
    def test_valid(self):
        m = CountByIntentInput(intent="cancel_order")
        assert m.intent == "cancel_order"

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            CountByIntentInput(intent="")

    def test_whitespace_raises(self):
        with pytest.raises(ValidationError):
            CountByIntentInput(intent="   ")

    def test_missing_raises(self):
        with pytest.raises(ValidationError):
            CountByIntentInput()


# ---------------------------------------------------------------------------
# Schema: GetTopCategoriesInput
# ---------------------------------------------------------------------------

class TestGetTopCategoriesInput:
    def test_default_limit(self):
        m = GetTopCategoriesInput()
        assert m.limit == 10

    def test_custom_limit(self):
        m = GetTopCategoriesInput(limit=3)
        assert m.limit == 3

    def test_zero_limit_raises(self):
        with pytest.raises(ValidationError):
            GetTopCategoriesInput(limit=0)

    def test_negative_limit_raises(self):
        with pytest.raises(ValidationError):
            GetTopCategoriesInput(limit=-1)


# ---------------------------------------------------------------------------
# Schema: SearchExamplesInput
# ---------------------------------------------------------------------------

class TestSearchExamplesInput:
    def test_valid(self):
        m = SearchExamplesInput(keyword="cancel")
        assert m.keyword == "cancel"
        assert m.limit == 5

    def test_custom_limit(self):
        m = SearchExamplesInput(keyword="refund", limit=3)
        assert m.limit == 3

    def test_empty_keyword_raises(self):
        with pytest.raises(ValidationError):
            SearchExamplesInput(keyword="")

    def test_whitespace_keyword_raises(self):
        with pytest.raises(ValidationError):
            SearchExamplesInput(keyword="   ")

    def test_missing_keyword_raises(self):
        with pytest.raises(ValidationError):
            SearchExamplesInput()

    def test_zero_limit_raises(self):
        with pytest.raises(ValidationError):
            SearchExamplesInput(keyword="cancel", limit=0)

    def test_negative_limit_raises(self):
        with pytest.raises(ValidationError):
            SearchExamplesInput(keyword="cancel", limit=-2)


# ---------------------------------------------------------------------------
# Wrapper: count_total_rows
# ---------------------------------------------------------------------------

def test_count_total_rows_calls_analytics():
    with patch("src.mcp.server._count_total_rows", return_value=26010) as mock_fn:
        result = server.count_total_rows()
    mock_fn.assert_called_once_with()
    assert result == 26010


# ---------------------------------------------------------------------------
# Wrapper: count_by_category
# ---------------------------------------------------------------------------

def test_count_by_category_calls_analytics():
    with patch("src.mcp.server._count_by_category", return_value=500) as mock_fn:
        result = server.count_by_category(category="ORDER")
    mock_fn.assert_called_once_with("ORDER")
    assert result == 500


def test_count_by_category_rejects_empty():
    with pytest.raises(ValidationError):
        server.count_by_category(category="")


def test_count_by_category_rejects_whitespace():
    with pytest.raises(ValidationError):
        server.count_by_category(category="  ")


# ---------------------------------------------------------------------------
# Wrapper: count_by_intent
# ---------------------------------------------------------------------------

def test_count_by_intent_calls_analytics():
    with patch("src.mcp.server._count_by_intent", return_value=200) as mock_fn:
        result = server.count_by_intent(intent="cancel_order")
    mock_fn.assert_called_once_with("cancel_order")
    assert result == 200


def test_count_by_intent_rejects_empty():
    with pytest.raises(ValidationError):
        server.count_by_intent(intent="")


# ---------------------------------------------------------------------------
# Wrapper: get_top_categories
# ---------------------------------------------------------------------------

def test_get_top_categories_calls_analytics_with_limit():
    expected = [{"category": "ORDER", "count": 500}]
    with patch("src.mcp.server._get_top_categories", return_value=expected) as mock_fn:
        result = server.get_top_categories(limit=5)
    mock_fn.assert_called_once_with(5)
    assert result == expected


def test_get_top_categories_default_limit():
    with patch("src.mcp.server._get_top_categories", return_value=[]) as mock_fn:
        server.get_top_categories()
    mock_fn.assert_called_once_with(10)


def test_get_top_categories_rejects_zero_limit():
    with pytest.raises(ValidationError):
        server.get_top_categories(limit=0)


# ---------------------------------------------------------------------------
# Wrapper: search_examples
# ---------------------------------------------------------------------------

def test_search_examples_calls_analytics():
    expected = [{"flags": "", "instruction": "cancel order", "category": "ORDER", "intent": "cancel_order"}]
    with patch("src.mcp.server._search_examples", return_value=expected) as mock_fn:
        result = server.search_examples(keyword="cancel", limit=3)
    mock_fn.assert_called_once_with("cancel", 3)
    assert result == expected


def test_search_examples_default_limit():
    with patch("src.mcp.server._search_examples", return_value=[]) as mock_fn:
        server.search_examples(keyword="refund")
    mock_fn.assert_called_once_with("refund", 5)


def test_search_examples_rejects_empty_keyword():
    with pytest.raises(ValidationError):
        server.search_examples(keyword="")


def test_search_examples_rejects_zero_limit():
    with pytest.raises(ValidationError):
        server.search_examples(keyword="refund", limit=0)
