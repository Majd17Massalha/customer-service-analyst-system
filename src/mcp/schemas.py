"""Pydantic input schemas for MCP tool arguments.

Validation mirrors the rules enforced in analytics_tools.py so that
callers get a clear error before hitting the database layer.
"""

from pydantic import BaseModel, Field, field_validator


class CountByCategoryInput(BaseModel):
    category: str = Field(..., description="Category name to filter by (case-insensitive).")

    @field_validator("category")
    @classmethod
    def must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("category must be a non-empty, non-blank string")
        return v


class CountByIntentInput(BaseModel):
    intent: str = Field(..., description="Intent name to filter by (case-insensitive).")

    @field_validator("intent")
    @classmethod
    def must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("intent must be a non-empty, non-blank string")
        return v


class GetTopCategoriesInput(BaseModel):
    limit: int = Field(
        default=10,
        ge=1,
        description="Maximum number of top categories to return (default 10).",
    )


class SearchExamplesInput(BaseModel):
    keyword: str = Field(
        ..., description="Substring to search for in instructions (case-insensitive)."
    )
    limit: int = Field(
        default=5,
        ge=1,
        description="Maximum number of matching examples to return (default 5).",
    )

    @field_validator("keyword")
    @classmethod
    def must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("keyword must be a non-empty, non-blank string")
        return v
