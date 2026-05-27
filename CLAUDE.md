# Critical Rules

- MUST use deterministic analytics for all numerical answers.
- MUST use DuckDB/Pandas for counts, filters, distributions, and comparisons.
- MUST NOT let the LLM calculate dataset statistics.
- MUST validate all user-derived query inputs.
- MUST use parameterized DuckDB queries.
- MUST keep architecture modular and testable.
- MUST avoid unnecessary dependencies and frameworks.
- MUST log routing decisions, tool calls, latency, and failures.
- NEVER concatenate raw user input into SQL queries.
- NEVER invent unsupported dataset information.
- NEVER answer out-of-scope questions using general LLM knowledge.
- NEVER push directly to main or production.

# Project

Build a production-oriented AI Customer Service Analyst Agent for the Bitext Customer Support dataset.

Required capabilities:
- Structured analytics
- Open-ended summarization
- Out-of-scope refusal
- Multi-step reasoning
- Persistent memory
- MCP tool exposure
- CLI reasoning traces

# Architecture

- DuckDB/Pandas = deterministic analytics layer.
- FastMCP = tool/data server.
- LangGraph = orchestration and ReAct workflow.
- LLM = routing, summarization, and response formatting only.
- Numerical answers must always come from tools.

# Security

- Restrict filters to known categories/intents.
- Validate MCP inputs with Pydantic.
- Reject unsupported query patterns.
- Do not expose secrets or local files.

# Observability

- Use lightweight Python logging only.
- Log route selection, tool calls, latency, errors, and refusal reasons.
- Write logs to outputs/agent.log.