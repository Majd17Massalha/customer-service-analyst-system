from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.agent.planner_executor import execute_plan
from src.agent.planner_schemas import AgentPlan


def test_llm_cannot_set_database_path():
    with pytest.raises(ValidationError):
        AgentPlan(
            tool="count_total_rows",
            db_path="unauthorized.duckdb",
        )


def test_executor_uses_trusted_database_path():
    plan = AgentPlan(
        tool="count_by_category",
        category="REFUND",
    )

    with patch(
        "src.agent.planner_executor.analytics_tools.count_by_category",
        return_value=12,
    ) as mock_tool:

        result = execute_plan(
            plan,
            db_path="trusted_test.duckdb",
        )

    assert result == 12

    mock_tool.assert_called_once_with(
        category="REFUND",
        db_path="trusted_test.duckdb",
    )


def test_executor_does_not_forward_irrelevant_fields():
    plan = AgentPlan(
        tool="search_examples",
        keyword="refund",
        category="SHIPPING",
        limit=5,
    )

    with patch(
        "src.agent.planner_executor.analytics_tools.search_examples",
        return_value=[],
    ) as mock_tool:

        execute_plan(
            plan,
            db_path="trusted_test.duckdb",
        )

    mock_tool.assert_called_once_with(
        keyword="refund",
        limit=5,
        db_path="trusted_test.duckdb",
    )