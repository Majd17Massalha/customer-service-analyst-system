# System Reliability

This document extends `docs/failure_modes.md` with the complete reliability taxonomy required for production operation. Each failure mode specifies detection, mitigation, fallback behavior, and remaining risk.

---

## Infrastructure Failures

### DuckDB Unavailable

**Detection:** `duckdb.connect()` raises `IOException` or `OperationalError`. Any downstream `con.execute()` raises if connection succeeded but table is missing (`CatalogException`).

**Mitigation:** Each analytics function wraps the connection in a `try/finally` to ensure `con.close()` is called. No connection pooling — each call opens and closes independently.

**Fallback:** Exception propagates to `node_structured_dispatch()` or `node_unstructured_retrieval()`. The graph node catches it and can return an error `final_answer`. Currently, the exception propagates to `run_chat_loop()` which catches it with a generic `except Exception` and prints `Error: <message>`.

**Remaining risk:** If DuckDB becomes unavailable mid-session, the user receives a raw exception message. A production deployment should catch `duckdb.IOException` specifically and return a friendly "Database temporarily unavailable" message.

---

### Missing Dataset File

**Detection:** `count_total_rows()` connects successfully (DuckDB creates an empty database) but `SELECT COUNT(*) FROM customer_support_train` raises `CatalogException: Table not found`.

**Mitigation:** `outputs/customer_support.duckdb` is created by `src/data/ingest.py` at setup time. If the file is absent, the ingestion script must be re-run.

**Fallback:** Exception propagates. CLI prints error. Agent remains non-functional until dataset is restored.

**Remaining risk:** No automatic dataset recovery. An operator must manually run `python src/data/ingest.py` to restore.

---

### MCP Server Unavailable

**Detection:** FastMCP server is a separate process. If it crashes or is not started, MCP tool calls from external clients fail. The CLI agent (LangGraph) does not use MCP — it calls analytics tools directly.

**Mitigation:** MCP and CLI are independent. CLI agent remains functional when MCP is down.

**Fallback:** CLI users are unaffected. MCP clients receive connection errors.

**Remaining risk:** MCP server has no health-check endpoint. An external client must implement its own retry logic.

---

### Filesystem Permission Issues

**Detection:** `save_session()` or `save_profile()` raises `PermissionError` when `outputs/memory/` is not writable.

**Mitigation:** `SESSIONS_DIR.mkdir(parents=True, exist_ok=True)` is called before each save. If the directory cannot be created, a `PermissionError` propagates.

**Fallback:** The CLI catches the exception in the `except Exception` block in `run_chat_loop()`. Session is not saved. Next query starts with stale session data.

**Remaining risk:** Persistent permission errors leave the memory layer non-functional silently. An operator-facing alert on repeated session-save failures would improve observability.

---

## Memory Failures

### Corrupted Session JSON

**Detection:** `json.JSONDecodeError` raised in `load_session()`.

**Mitigation:** Wrapped in `try/except`. On failure, logs a warning and returns `SessionState(session_id=session_id)` (fresh state).

**Fallback:** Agent operates without prior session context. User may receive clarification prompts that would have been resolved with valid session data.

**Remaining risk:** Corrupted file is not deleted automatically. A subsequent successful save overwrites it with valid JSON. Until then, the file occupies disk space and confuses manual inspection.

---

### Corrupted Profile JSON

**Detection:** `json.JSONDecodeError` or `TypeError` (unexpected field names) in `load_profile()`.

**Mitigation:** Same as session: returns `UserProfile(session_id=session_id)` on failure. Warning logged.

**Fallback:** Profile starts fresh. Accumulated category/intent preferences are lost.

**Remaining risk:** Same as corrupted session.

---

### Interrupted Write (Partial JSON)

**Scenario:** Process killed mid-write to a session or profile file.

**Detection:** On next load, `json.JSONDecodeError` is raised. Detected by the same fallback path as corrupted JSON.

**Mitigation:** The write is currently a direct `json.dump()` to an open file handle. If interrupted, the file contains a partial write.

**Fallback:** Fresh state loaded on next session start.

**Remaining risk:** No atomic write (write-to-temp + rename). A production deployment should use atomic file replacement to prevent partial writes. The risk in the current single-user local deployment is low.

---

### Session ID Collision

**Scenario:** Two distinct raw session IDs sanitize to the same string (e.g., `user@a` and `user.a` both → `user_a`).

**Detection:** Both users access and overwrite the same file. No error is raised.

**Mitigation:** Each user should choose a globally unique session ID. The system does not enforce uniqueness.

**Remaining risk:** Session context mixing between users. In a multi-user deployment, session isolation must be enforced at a higher layer (e.g., user-ID prefix injected by the authentication layer).

---

## Routing and State Failures

### Malformed AgentState

**Scenario:** `graph.invoke()` receives a state dict missing the required `query` key.

**Detection:** `node_route_query()` calls `state["query"]` which raises `KeyError`.

**Mitigation:** The `AgentState(TypedDict, total=False)` definition means all fields are optional by type, but `query` is required at runtime for the router.

**Fallback:** Exception propagates to the CLI `except Exception` handler. Error printed. Session not updated.

**Remaining risk:** No schema validation at graph entry point. A future version should validate the initial state dict before graph invocation.

---

### Invalid Routing (Unknown Route Label)

**Scenario:** `route_query()` returns an unexpected route label.

**Detection:** The LangGraph conditional edge dispatcher (`route_fn`) would hit the default branch, which does not exist.

**Mitigation:** `route_query()` always returns one of the four known labels (`structured`, `unstructured`, `out_of_scope`, `needs_clarification`). The router has no code path that returns anything else.

**Remaining risk:** If a future code change introduces a fifth route without updating the graph, the default branch raises an unhandled error.

---

### Tool Failure (Runtime Exception in Analytics Tool)

**Scenario:** A valid analytics call fails due to a transient DuckDB error.

**Detection:** Exception propagates from the tool function into the node function.

**Mitigation:** Node functions (`node_structured_dispatch`, `node_unstructured_retrieval`) do not currently catch tool exceptions. The exception propagates to `run_chat_loop()`.

**Fallback:** CLI prints error. Session is not updated. Agent remains available for the next query.

**Remaining risk:** No per-tool retry logic. A transient failure requires the user to re-ask the question. A future version should add a retry wrapper for transient `IOException` from DuckDB.

---

### Empty Observation

**Scenario:** A tool returns an empty list (no keyword matches, no categories in DB).

**Detection:** Returned data is an empty list. Not an error.

**Mitigation:** `_build_extractive_summary()` handles empty data gracefully:
```python
if not data:
    return f"{prefix}\nNo matching examples found in the dataset."
```

**Fallback:** A "no results" message is returned as `final_answer`. Not an error state.

**Remaining risk:** None. Empty results are a valid response, not a failure.

---

### Partial Dataset Ingestion

**Scenario:** `ingest.py` is interrupted after partial write to DuckDB.

**Detection:** `count_total_rows()` returns a lower-than-expected count. No error raised.

**Mitigation:** The ingestion script should be re-run. DuckDB is a single-file database; re-running drops and recreates the table.

**Remaining risk:** No checksum or row-count validation is performed at startup. A future version should verify expected row count (26,872) on startup and warn if the count deviates.

---

## Observability Failures

### Log File Growth

**Scenario:** `outputs/agent.log` grows unbounded over many sessions.

**Detection:** Disk usage monitoring. No internal detection.

**Mitigation:** Log rotation is not currently implemented. In production, configure `logging.handlers.RotatingFileHandler`.

**Remaining risk:** Long-running deployments will exhaust disk space without log rotation.

---

### Repeated Failures (Cascading)

**Scenario:** DuckDB is unavailable; every query fails; log is flooded with errors.

**Detection:** Error log grows rapidly. CLI prints errors on every query.

**Mitigation:** The CLI loop continues after each error. No circuit breaker is implemented.

**Remaining risk:** No exponential backoff or circuit-breaker pattern. A future version should detect repeated failures and surface a "service degraded" state.

---

## Summary

| Failure Mode | Detection | Fallback | Risk Level |
|---|---|---|---|
| DuckDB unavailable | Exception from connect/execute | Error printed to CLI | Medium |
| Missing dataset | CatalogException | CLI error; manual recovery | High |
| MCP unavailable | Connection error (MCP clients only) | CLI unaffected | Low |
| Filesystem permission error | PermissionError on save | Session not saved | Medium |
| Corrupted session JSON | JSONDecodeError on load | Fresh state used | Low |
| Corrupted profile JSON | JSONDecodeError on load | Fresh profile used | Low |
| Interrupted write | JSONDecodeError on next load | Fresh state used | Low |
| Session ID collision | Silent (no detection) | Context mixing | Medium (multi-user) |
| Malformed AgentState | KeyError in node | CLI error | Low (dev-time bug) |
| Invalid route label | Graph dispatch failure | Unhandled exception | Low (dev-time bug) |
| Tool runtime failure | Exception from tool | CLI error | Low |
| Empty observation | Empty list returned | "No results" message | None |
| Partial ingestion | Low row count | Wrong answers | Medium |
| Log file growth | External monitoring | Disk exhaustion | Low (short-term) |
| Repeated failures | Log volume spike | No circuit breaker | Medium |
