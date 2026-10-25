import pytest
from pydantic import ValidationError

from src.agent.planner_schemas import AgentPlan


def test_valid_filtered_plan():
    plan = AgentPlan(
        tool="get_filtered_examples",
        category="REFUND",
        limit=5,
    )

    assert plan.tool == "get_filtered_examples"
    assert plan.category == "REFUND"
    assert plan.limit == 5


def test_valid_keyword_search():
    plan = AgentPlan(
        tool="search_examples",
        keyword="refund",
    )

    assert plan.keyword == "refund"


def test_unknown_tool_is_rejected():
    with pytest.raises(ValidationError):
        AgentPlan(tool="delete_database")


def test_filtered_examples_requires_filter():
    with pytest.raises(ValidationError):
        AgentPlan(tool="get_filtered_examples")


def test_keyword_search_requires_keyword():
    with pytest.raises(ValidationError):
        AgentPlan(tool="search_examples")


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_invalid_limits_are_rejected(limit):
    with pytest.raises(ValidationError):
        AgentPlan(
            tool="get_filtered_examples",
            category="REFUND",
            limit=limit,
        )


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        AgentPlan(
            tool="count_total_rows",
            sql="DROP TABLE customers",
        )