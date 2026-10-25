"""Execute validated agent plans using approved analytics tools."""

from pathlib import Path
from typing import Any

from src.agent.planner_schemas import AgentPlan
from src.tools import analytics_tools


def execute_plan(
    plan: AgentPlan,
    db_path: str | Path = analytics_tools.DB_PATH,
) -> Any:
    """Execute one approved plan against a trusted database path."""

    if plan.tool == "count_total_rows":
        return analytics_tools.count_total_rows(
            db_path=db_path,
        )

    if plan.tool == "count_by_category":
        return analytics_tools.count_by_category(
            category=plan.category,
            db_path=db_path,
        )

    if plan.tool == "count_by_intent":
        return analytics_tools.count_by_intent(
            intent=plan.intent,
            db_path=db_path,
        )

    if plan.tool == "get_top_categories":
        return analytics_tools.get_top_categories(
            limit=plan.limit,
            db_path=db_path,
        )

    if plan.tool == "search_examples":
        return analytics_tools.search_examples(
            keyword=plan.keyword,
            limit=plan.limit,
            db_path=db_path,
        )

    if plan.tool == "get_filtered_examples":
        return analytics_tools.get_filtered_examples(
            category=plan.category,
            intent=plan.intent,
            limit=plan.limit,
            db_path=db_path,
        )

    raise ValueError(f"Unsupported tool: {plan.tool}")