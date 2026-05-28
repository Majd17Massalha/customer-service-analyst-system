# Customer Service Analyst Agent

A production-oriented AI analyst agent for the Bitext Customer Support dataset. Answers structured analytical questions (counts, distributions, filters) and open-ended summarization questions deterministically, with explicit refusal for out-of-scope queries and clarification prompts for ambiguous input.

---

## Executive Summary

This system routes natural-language queries to one of four execution paths — structured analytics, unstructured summarization, out-of-scope refusal, or clarification request — using a deterministic keyword-based router with no LLM dependency at the routing or analytics layer. Numerical answers are computed exclusively by DuckDB. The LLM layer is reserved for response formatting and summarization only.

---

## Problem Statement

Customer service analysts need to interrogate large support datasets without writing SQL. Naive LLM-based answers are unreliable for numerical queries: LLMs hallucinate counts, percentages, and distributions. This system enforces a hard boundary: any question with a numerical answer goes through a verified analytics engine, not the language model.

---

## Project Goals

- Deterministic, reproducible analytics over the Bitext support dataset
- Natural-language routing with no external API calls at routing time
- Persistent session and profile memory across conversations
- Structured observability: every route decision and tool call is logged
- Production-style security: parameterized queries, input validation, no data leakage
- Modular, testable architecture with 155 passing tests

---

## Architecture Overview

```
User Input
    │
    ▼
CLI Layer (main.py + src/cli/chat_loop.py)
    │  session memory in / out
    ▼
LangGraph Orchestration (src/agent/graph.py)
    │
    ├─── Deterministic Router (src/agent/router.py)
    │        keyword classification, no LLM
    │
    ├─── structured ──► Analytics Node ──► DuckDB Tools (src/tools/analytics_tools.py)
    ├─── unstructured ► Retrieval Node  ──► DuckDB + extractive summary
    ├─── out_of_scope ► Refusal Node    ──► static refusal message
    └─── clarification ► Clarify Node   ──► ask for more context
    │
    ▼
Trace Contract (route, tool, tool_input, observation, final_answer)
    │
    ▼
CLI Output (operational trace only — no chain-of-thought)
    │
    ├─► Session Memory (src/memory/checkpoints.py)  — short-term, JSON
    └─► User Profile   (src/memory/user_profile.py) — long-term, JSON
```

### MCP Boundary

`src/mcp/server.py` exposes the same DuckDB analytics tools through a FastMCP server. This layer is **independent of the CLI runtime** — it can be started separately to allow external tools, LangChain agents, or IDE integrations to call the analytics functions over the MCP protocol with Pydantic-validated inputs.

### LangGraph Orchestration

The LangGraph `StateGraph` has a single conditional fan-out:

```
START → route_query → {structured | unstructured | out_of_scope | clarification} → END
```

Each branch is a standalone node that populates the full trace contract before returning. No node shares mutable state with another. The graph is compiled once at import time and invoked per query.

---

## Why Deterministic Analytics Over Pure LLM Reasoning

LLMs do not count reliably. Given a corpus of 26,872 rows across multiple intent and category dimensions, a language model asked "how many billing inquiries are there?" will produce a plausible-sounding but unverifiable number. DuckDB with a parameterized `GROUP BY` query is deterministic, fast, and auditable. The architecture enforces this boundary structurally: numerical answers can only originate from analytics tool return values, never from the model's own generation.

---

## Security and Privacy Decisions

| Risk | Mitigation |
|---|---|
| SQL injection via user input | Parameterized DuckDB queries; no string concatenation into SQL |
| Raw dataset rows in long-term memory | `update_profile_from_state()` never reads `observation`; only reads `category`/`intent` from `tool_input` |
| Sensitive user input in profiles | `_NEVER_STORE` set blocks `api_key`, `token`, `password`, `secret`, `credential`, `email`, `phone`, `ssn`, `raw_query`, `dataset_row` |
| Session ID path traversal | `sanitize_session_id()` strips `/`, `\`, `.`, `@`, and all non-alphanumeric chars; caps at 64 chars |
| Long free-text query storage | `last_query` truncated to 500 chars before persistence |
| Chain-of-thought exposure | Internal `trace` list never printed; CLI prints only named operational fields |
| Memory files in git | `outputs/` is in `.gitignore` |

---

## Memory Design

**Short-term (session):** `src/memory/checkpoints.py`
- Stores metadata about the last query: route, tool name, category filter, intent filter, keyword, result offset
- JSON file per session ID under `outputs/memory/sessions/`
- Corrupted files fall back to a fresh state with a warning log entry
- Never stores raw query text beyond 500 chars; never stores observation data

**Long-term (profile):** `src/memory/user_profile.py`
- Stores distilled non-sensitive facts: preferred categories, frequent intents, preferred output style
- JSON file per session ID under `outputs/memory/profiles/`
- Written only from structured `tool_input` fields; never written from free text, observations, or query content

---

## Installation

**Requirements:** Python 3.10+

```bash
git clone <repo-url>
cd customer_service_analyst_agent
pip install -r requirements.txt
```

---

## Ingest the Dataset

Downloads the Bitext Customer Support dataset from Hugging Face and persists it to a local DuckDB file.

```bash
python -m src.data.ingest
```

This creates `outputs/customer_support.duckdb` containing the `customer_support_train` table (26,872 rows).

---

## Run Tests

```bash
pytest tests/ -v
```

All 155 tests run without API keys, external services, or network access. Each test uses an isolated in-memory or `tmp_path` DuckDB fixture.

---

## Start the CLI

```bash
python main.py --session demo
```

Replace `demo` with any alphanumeric session identifier. Session state is persisted across restarts.

---

## Start the MCP Server

```bash
python -m src.mcp.server
```

The FastMCP server starts and exposes the analytics tools over the MCP protocol. The server is independent of the CLI runtime.

---

## Example CLI Session

```
$ python main.py --session analyst1

Route     : structured
Confidence: 0.90
Tool      : count_total_rows
Tool Input: {}
Observation: 26872 (truncated)
Answer    : The dataset contains 26,872 support interactions.

> How many billing queries are there?

Route     : structured
Confidence: 0.90
Tool      : count_by_category
Tool Input: {"category": "billing"}
Observation: 3200 (truncated)
Answer    : There are 3,200 billing queries in the dataset.

> What is the weather in Paris?

Route     : out_of_scope
Confidence: 0.95
Answer    : I can only answer questions about the customer support dataset. That question is outside my scope.

> exit
```

---

## Supported Query Examples

| Query | Route | Tool |
|---|---|---|
| How many total rows are there? | structured | count_total_rows |
| How many billing queries are there? | structured | count_by_category |
| How many cancellation intents exist? | structured | count_by_intent |
| What are the top categories? | structured | get_top_categories |
| Show me examples about refunds | unstructured | search_examples |
| Summarize shipping complaints | unstructured | search_examples |

---

## Refused Query Examples

| Query | Reason |
|---|---|
| What is the weather in Paris? | Out-of-scope domain |
| Write me a poem about returns | Out-of-scope task type |
| What is the stock price of Amazon? | Out-of-scope domain |
| Who won the Champions League? | Out-of-scope domain |

---

## Limitations

- No real-time data: the dataset is a static Bitext snapshot (26,872 synthetic rows)
- No LLM-backed summarization: unstructured answers are extractive, not generative
- No semantic search: keyword search uses substring matching, not embeddings
- No multi-turn conversation: each query is evaluated independently
- No authentication: sessions are identified by user-supplied string IDs
- No horizontal scale: single-process, single-file DuckDB

---

## Future Work

### Smart RAG Extension (Hybrid Architecture)

A future semantic layer would complement the deterministic analytics layer without replacing it:

- **Structured queries** (counts, filters, distributions) → DuckDB exact tools (unchanged)
- **Exploratory/semantic queries** ("what do users complain about most?") → embedding-based retrieval over `instruction` + `response` column content
- Each dataset row becomes one semantic document with metadata fields (`category`, `intent`, `flags`)
- Retrieval gates on a new `unstructured_semantic` route; statistical routes are never replaced by RAG
- Counts and statistics must never use RAG — hallucinated counts are a hard failure mode

### Plan Mode (Multi-Step Execution)

A planner node could be introduced upstream of the current router for complex multi-step queries:
- `planner_node` decomposes a query into a sequence of tool calls
- `executor_node` runs each step against deterministic tools in order
- The planner is constrained to tool calls; it cannot bypass input validation or execute arbitrary code
- All existing security and parameterization guarantees apply unchanged

### Additional Capabilities

- Timestamp-based filtering (requires dataset enrichment)
- Trend analysis across intent distribution over time
- Exportable analytics reports (CSV, JSON)
- Multi-session aggregation for team-level dashboards
