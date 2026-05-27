"""FastMCP server — exposes deterministic analytics tools over the MCP protocol.

This layer is intentionally thin:
  - Validates inputs with Pydantic schemas (src.mcp.schemas).
  - Delegates all computation to src.tools.analytics_tools.
  - Never calls an LLM.
"""

import logging

from fastmcp import FastMCP

from src.mcp.schemas import (
    CountByCategoryInput,
    CountByIntentInput,
    GetTopCategoriesInput,
    SearchExamplesInput,
)
from src.tools.analytics_tools import (
    count_by_category as _count_by_category,
    count_by_intent as _count_by_intent,
    count_total_rows as _count_total_rows,
    get_top_categories as _get_top_categories,
    search_examples as _search_examples,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Customer Service Analytics",
    instructions=(
        "Deterministic analytics over the Bitext customer-support training dataset. "
        "All numerical results come from DuckDB queries — no LLM inference."
    ),
)


@mcp.tool()
def count_total_rows() -> int:
    """Return the total number of rows in the customer support training dataset."""
    logger.info("MCP tool: count_total_rows")
    return _count_total_rows()


@mcp.tool()
def count_by_category(category: str) -> int:
    """Return the number of rows whose category matches the given value (case-insensitive).

    Returns 0 when no rows match.
    """
    logger.info("MCP tool: count_by_category(%r)", category)
    CountByCategoryInput(category=category)
    return _count_by_category(category)


@mcp.tool()
def count_by_intent(intent: str) -> int:
    """Return the number of rows whose intent matches the given value (case-insensitive).

    Returns 0 when no rows match.
    """
    logger.info("MCP tool: count_by_intent(%r)", intent)
    CountByIntentInput(intent=intent)
    return _count_by_intent(intent)


@mcp.tool()
def get_top_categories(limit: int = 10) -> list[dict]:
    """Return the top N categories ranked by row count descending.

    Each entry is {"category": str, "count": int}.
    """
    logger.info("MCP tool: get_top_categories(limit=%d)", limit)
    GetTopCategoriesInput(limit=limit)
    return _get_top_categories(limit)


@mcp.tool()
def search_examples(keyword: str, limit: int = 5) -> list[dict]:
    """Return up to N examples whose instruction contains the keyword (case-insensitive).

    Each entry is {"flags": str, "instruction": str, "category": str, "intent": str}.
    Returns an empty list when nothing matches.
    """
    logger.info("MCP tool: search_examples(%r, limit=%d)", keyword, limit)
    SearchExamplesInput(keyword=keyword, limit=limit)
    return _search_examples(keyword, limit)


if __name__ == "__main__":
    mcp.run()
