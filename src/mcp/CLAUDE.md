# MCP Layer Rules

- This layer exposes deterministic analytics tools via FastMCP.
- MUST NOT call LLMs from this layer.
- MUST use DuckDB/Pandas only.
- MUST validate all inputs before query execution.
- MUST expose typed tool interfaces using Pydantic schemas.
- NEVER generate final natural-language responses here.