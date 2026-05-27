# Agent Layer Rules

- LangGraph is responsible for routing and orchestration.
- The agent must distinguish:
  - structured queries
  - unstructured queries
  - out-of-scope queries
- MUST use MCP tools for numerical analytics.
- MUST support multi-step reasoning.
- MUST support graceful fallback on max iterations.
- NEVER invent tool outputs.