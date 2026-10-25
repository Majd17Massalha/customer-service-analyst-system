"""Business validation guardrails for LLM-generated agent plans."""

from src.agent.planner_schemas import AgentPlan


def validate_plan_filters(
    plan: AgentPlan,
    available_categories: set[str],
    available_intents: set[str],
) -> AgentPlan:
    """Validate category and intent against known dataset values."""

    categories = {
        value.strip().casefold()
        for value in available_categories
    }

    intents = {
        value.strip().casefold()
        for value in available_intents
    }

    if plan.category is not None:
        if plan.category.strip().casefold() not in categories:
            raise ValueError(
                f"Unknown category: {plan.category!r}"
            )

    if plan.intent is not None:
        if plan.intent.strip().casefold() not in intents:
            raise ValueError(
                f"Unknown intent: {plan.intent!r}"
            )

    return plan