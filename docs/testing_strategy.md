# Testing Strategy

## Overview

The test suite enforces a strict no-external-dependencies rule: no API keys, no network calls, no LLM invocations, no running MCP server. Every test is self-contained and reproducible. The 155 tests across six files cover unit behavior, integration behavior, orchestration behavior, security properties, and regression cases from manual validation.

---

## Test Categories

### Unit Tests

**Target:** Individual functions in isolation.

**Files:** `test_tools.py`, `test_memory.py`, `test_cli.py`

Each analytics function in `src/tools/analytics_tools.py` is tested against an isolated DuckDB fixture created at `tmp_path`. Tests verify:
- Correct return type and value for valid inputs
- Correct error type for invalid inputs (empty string, negative limit, wrong type)
- Case-insensitivity of category/intent matching
- Boundary behavior (limit=1, limit=100)

Memory unit tests verify:
- `sanitize_session_id()` output for all character classes
- `SessionState` and `UserProfile` round-trip through JSON save/load
- Field truncation (query capped at 500 chars)
- `_NEVER_STORE` enforcement on profile save

CLI unit tests verify:
- `_print_trace()` output format for each trace variant
- `_update_session_from_state()` field extraction logic
- No chain-of-thought fields appear in output
- Observation truncation at 300 characters

### Integration Tests

**Target:** Module boundary crossings.

**Files:** `test_agent_execution.py`, `test_mcp_server.py`

Agent execution tests invoke `graph.invoke()` end-to-end with an injected `db_path` pointing to an isolated fixture DuckDB. Tests verify:
- The correct route is selected for each query type
- The trace contract fields are all populated
- Structured queries produce a numeric `observation`
- Out-of-scope queries produce the refusal string
- Clarification queries ask for more context

MCP schema tests verify:
- `CountByCategoryInput` rejects empty strings
- `CountByIntentInput` rejects empty strings
- `GetTopCategoriesInput` rejects zero and negative limits
- `SearchExamplesInput` rejects empty keywords and non-positive limits

### Orchestration Tests

**Target:** LangGraph graph topology and routing decisions.

**Files:** `test_router.py`, `test_agent_execution.py`

Router tests verify all four routing outcomes across representative queries. Each test asserts the `route` field and checks that `reason_summary` is populated. Orchestration tests verify the full state transition: `query → route_result → node execution → final_answer`.

### Regression Tests

**Target:** Specific behaviors caught during manual validation that were initially wrong.

These are embedded in the existing test files as named test cases. Examples:
- `test_out_of_scope_does_not_call_tool` — verified after manual session revealed the out-of-scope node was incorrectly attempting a tool dispatch
- `test_observation_not_in_session` — verified after noticing session files contained raw DuckDB result rows during manual inspection
- `test_sanitize_path_traversal` — verified after security review of file path construction

### CLI Validation Tests

**Target:** Interactive loop behavior.

**File:** `test_cli.py`

Tests use `unittest.mock` to inject controlled inputs and capture output. Cases cover:
- `exit`, `quit`, `q` (all three exit commands)
- Empty string and whitespace-only inputs (silently skipped)
- `EOFError` and `KeyboardInterrupt` (graceful termination)
- Multi-query session flow

### Security Validation Tests

**Target:** Data leakage and injection prevention.

**File:** `test_memory.py` (security section)

Tests assert:
- Session JSON files do not contain keys matching `_NEVER_STORE` entries
- Profile JSON files do not contain raw query text or dataset row content
- `sanitize_session_id()` eliminates all path traversal characters
- Profile updates from state never write observation content

### Memory Persistence Validation

**Target:** Correctness of JSON round-trips across restart boundaries.

**File:** `test_memory.py`

Tests save a session, delete the in-memory object, reload from disk, and assert field equality. A separate test writes a corrupted JSON file and asserts that loading it returns a fresh default state with no exception raised.

---

## What Was Intentionally Not Tested

**LLM behavior:** The system makes no LLM calls in the current implementation. There is nothing to test at that boundary yet.

**MCP server startup:** The FastMCP server process itself is not started in tests. Schema validation and tool delegation are tested in isolation.

**Filesystem permissions:** Tests do not assert behavior under restricted permissions (e.g., read-only `outputs/` directory). This is a known gap.

**Concurrent session access:** Tests run sequentially. Race conditions between simultaneous writes to the same session file are not tested.

**Large dataset performance:** Tests use small synthetic fixtures (typically 10–50 rows). Query performance at 26,872 rows is validated manually but not in the automated suite.

**Import-time side effects:** Tests do not verify that importing `src/agent/graph.py` compiles the LangGraph graph exactly once with no repeated compilation.

---

## Remaining Risks

- A session ID collision between two users with the same sanitized ID would cause one to read the other's session state. Currently only relevant in multi-user deployments (not in scope).
- A DuckDB file that is partially written (interrupted write mid-row) may produce inconsistent counts. The ingest script does not use transactions. This is a known limitation of the ingestion layer.
- The `_NEVER_STORE` set blocks keys by exact match. A caller that stores sensitive data under a non-blocked key name (e.g., `auth_token` instead of `token`) would not be caught.

---

## Accepted Assumptions

- The Bitext dataset schema is stable (columns: `flags`, `instruction`, `category`, `intent`, `response` do not change between runs).
- Session IDs provided by the user are user-controlled strings, not system-generated tokens; no session secrecy guarantee is required.
- The DuckDB file is located at the path configured at import time; the system does not support hot-swapping the database at runtime.
- All tests run on a single thread; no concurrency assumptions are made.
