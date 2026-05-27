# Architectural & Engineering Decisions

## Decision 1: Deterministic Analytics Layer

All numerical analytics are computed through DuckDB/Pandas tools rather than direct LLM reasoning.

Reason:
Prevent hallucinated statistics and ensure reproducibility.

---

## Decision 2: FastMCP Tool Server

Deterministic analytics tools are exposed through a dedicated FastMCP server.

Reason:
Separate reusable data tooling from orchestration logic.

---

## Decision 3: LangGraph Orchestration

LangGraph manages routing, reasoning flow, memory, and fallback behavior.

Reason:
The assignment requires a ReAct-style agent with multi-step reasoning.

---

## Decision 4: Lightweight Observability

Telemetry uses Python logging instead of heavy external observability platforms.

Reason:
Provides production-style tracing while minimizing operational complexity.