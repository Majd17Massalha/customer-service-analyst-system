"""Typed contracts for LLM-generated agent plans."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ToolName = Literal[
    "search_examples",
    "get_filtered_examples",
    "get_top_categories",
    "count_total_rows",
    "count_by_category",
    "count_by_intent",
]


class AgentPlan(BaseModel):
    """A validated plan describing one approved tool call."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    tool: ToolName
    category: str | None = None
    intent: str | None = None
    keyword: str | None = None
    limit: int = Field(default=5, ge=1, le=100)

    @model_validator(mode="after")
    def validate_tool_arguments(self):
        if self.tool == "search_examples":
            if not self.keyword or not self.keyword.strip():
                raise ValueError(
                    "search_examples requires a non-empty keyword"
                )

        elif self.tool == "get_filtered_examples":
            if not self.category and not self.intent:
                raise ValueError(
                    "get_filtered_examples requires category or intent"
                )

        elif self.tool == "count_by_category":
            if not self.category:
                raise ValueError(
                    "count_by_category requires category"
                )

        elif self.tool == "count_by_intent":
            if not self.intent:
                raise ValueError(
                    "count_by_intent requires intent"
                )

        return self