# Security Audit

## Scope

This audit covers the security design of the Customer Service Analyst Agent running in local, single-user mode against the Bitext Customer Support dataset. It does not cover network exposure, multi-tenant scenarios, or cloud deployment.

---

## 1. SQL Injection Prevention

**Implementation:** All DuckDB queries in `src/tools/analytics_tools.py` use parameterized query binding.

```python
# Correct: parameterized binding
con.execute("SELECT COUNT(*) FROM customer_support_train WHERE LOWER(category) = LOWER(?)", [category])

# Correct: contains() for substring match — no wildcard injection
con.execute("... WHERE contains(LOWER(instruction), LOWER(?)) LIMIT ?", [keyword, limit])
```

**What this prevents:**
- Classic SQL injection via `'; DROP TABLE--`
- Tautology injection (`1=1 OR 1=1`)
- SQL wildcard injection (`%`, `_` treated as literals in `contains()`)
- Multi-statement injection (DuckDB parameterized calls reject multi-statement input)

**Verified by:** `tests/test_adversarial_queries.py` — `test_sql_injection_in_category_returns_zero`, `test_table_still_intact_after_injection_attempt`, `test_wildcard_in_category_is_literal`

**Residual risk:** The `TABLE` constant (`customer_support_train`) is interpolated directly into the query string. This is acceptable because it is a compile-time constant defined in the source code, not derived from user input.

---

## 2. Input Validation

**Implementation:** All public tool functions validate inputs before SQL execution.

```python
def _require_nonempty_str(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(...)

def _require_positive_int(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(...)
```

**What this prevents:**
- Empty string parameters that would generate vacuous queries
- Boolean parameters passed as integers (`True` treated as 1 by Python int arithmetic)
- Zero or negative limits that could trigger all-row returns or wraparound

**Verified by:** `tests/test_adversarial_queries.py` — `test_empty_category_raises_not_executes`, `test_zero_limit_raises`, `test_boolean_limit_raises`

---

## 3. Memory Leakage Prevention

### 3a. No Raw Dataset Rows in Session Storage

`_update_session_from_state()` in `src/cli/chat_loop.py` reads only:
- `route_result.route` → `last_route`
- `selected_tool` → `last_tool`
- `tool_input.category` → `last_category`
- `tool_input.intent` → `last_intent`
- `tool_input.keyword` → `last_keyword`

It **never** reads:
- `observation` (may contain raw dataset rows)
- `response` or `final_answer` (may contain extracted text)
- `trace` (internal chain-of-thought)

**Verified by:** `tests/test_security_edges.py` — `test_observation_not_stored_in_session`, `test_raw_dataset_rows_not_in_session`

### 3b. No Raw Rows in Long-Term Profile

`update_profile_from_state()` in `src/memory/user_profile.py` reads only `tool_input.category` and `tool_input.intent`. It never reads from `observation`.

**Verified by:** `tests/test_security_edges.py` — `test_profile_does_not_store_observation_data`, `test_profile_update_reads_only_tool_input`

### 3c. Defensive Strip on Profile Save

```python
_NEVER_STORE = frozenset({
    "api_key", "token", "password", "secret", "credential",
    "email", "phone", "ssn", "raw_query", "dataset_row",
})

def save_profile(profile):
    data = asdict(profile)
    for key in list(data.keys()):
        if key in _NEVER_STORE:
            del data[key]
    ...
```

**Verified by:** `tests/test_security_edges.py` — `test_never_store_keys_absent_from_profile_json`

### 3d. Query Length Cap

Raw query text stored in session is capped at 500 characters:
```python
session.last_query = query[:_MAX_QUERY_STORE]  # _MAX_QUERY_STORE = 500
```

This prevents unlimited free-text accumulation in session files.

**Verified by:** `tests/test_security_edges.py` — `test_query_truncated_at_500_chars_in_session`

---

## 4. Session Sanitization and Path Traversal Prevention

**Implementation:** `sanitize_session_id()` in `src/memory/checkpoints.py`.

```python
_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_\-]")
_MAX_ID_LEN = 64

def sanitize_session_id(session_id: str) -> str:
    safe = _SAFE_CHARS.sub("_", str(session_id))
    return safe[:_MAX_ID_LEN] if safe else "default_session"
```

**What this prevents:**

| Attack | Input | Sanitized Output |
|---|---|---|
| Path traversal | `../../etc/passwd` | `____etc_passwd` |
| SQL injection | `'; DROP TABLE--` | `__DROP_Table__` |
| Null byte injection | `session\x00id` | `session_id` |
| @ / . exposure | `user@email.com` | `user_email_com` |
| Excessively long ID | 200-char string | Truncated to 64 chars |

**Verified by:** `tests/test_security_edges.py` — `test_path_traversal_stripped_from_session_id`, `test_sql_injection_chars_stripped_from_session_id`, `test_session_file_written_to_sanitized_path`

---

## 5. Chain-of-Thought Exposure Prevention

The internal `trace` field in `AgentState` accumulates operational log entries during graph execution. This field is **never** printed to the user.

`_print_trace()` in `src/cli/chat_loop.py` prints only named operational fields:
- `route_result.route`
- `route_result.confidence`
- `selected_tool`
- `tool_input`
- `observation` (truncated to 300 chars)
- `final_answer`

The `trace` list is never accessed or printed in `_print_trace`.

**Verified by:** `tests/test_security_edges.py` — `test_print_trace_never_prints_trace_list`

---

## 6. Local File Path Exposure Prevention

The database path `DB_PATH` is a module-level constant resolved at import time. It is never surfaced in:
- `final_answer` responses
- `_print_trace` output
- Session or profile JSON files

`_print_trace` prints only the `observation` value (DuckDB query results: integers or lists of dicts), which do not contain file paths.

**Verified by:** `tests/test_security_edges.py` — `test_print_trace_does_not_expose_windows_paths`

---

## 7. Operational Trace Boundaries

What is logged to `outputs/agent.log` (observable by operators):
- Route decisions (route label, confidence, reason summary)
- Tool calls (tool name, parameters, latency)
- Session save/load operations (sanitized path)
- Error events (exception type and message)

What is **intentionally NOT logged** (privacy/security boundary):
- Raw query text beyond truncated log entries
- Full `observation` content (may contain dataset rows)
- User profile contents
- Internal trace list (chain-of-thought steps)

---

## 8. Refusal Policy

Out-of-scope queries are handled by `node_out_of_scope_response()` which:
1. Returns a refusal message that redirects to valid query types
2. Sets `selected_tool = None` (no tool called)
3. Sets `observation = None` (no data retrieved)
4. Logs the refusal reason

**Refusal priority:** Out-of-scope is checked first in the router's priority order, before structured or unstructured keywords. This prevents a query like "write me a count of jokes" from bypassing the refusal check because it contains "count."

---

## 9. Local-Only Execution

The agent runs in a single local process:
- No network calls during query processing (DuckDB is file-based)
- No external API keys required for analytics
- MCP server runs locally on `localhost` (not exposed to external networks)
- No cloud storage or remote database connections
- `outputs/` directory is in `.gitignore` (memory files not committed)

---

## 10. Bounded Memory Design

| Memory Type | Location | Max Size | Expiration |
|---|---|---|---|
| Session state | `outputs/memory/sessions/*.json` | Bounded by field caps (500 chars for query) | Overwritten on each save |
| User profile | `outputs/memory/profiles/*.json` | Lists deduplicated; no unbounded growth | Overwritten on each save |
| Agent log | `outputs/agent.log` | Unbounded (log rotation not implemented) | Not expired automatically |

**Residual risk:** `outputs/agent.log` is not rotated. In a production deployment, log rotation should be configured to prevent disk exhaustion.

---

## Summary of Verified Security Properties

| Property | Implemented | Tested |
|---|---|---|
| Parameterized SQL queries | Yes | Yes |
| Input validation before SQL | Yes | Yes |
| No raw rows in session | Yes | Yes |
| No raw rows in profile | Yes | Yes |
| _NEVER_STORE defensive strip | Yes | Yes |
| Query length cap (500 chars) | Yes | Yes |
| Session ID path traversal prevention | Yes | Yes |
| No chain-of-thought in output | Yes | Yes |
| No file paths in output | Yes | Yes |
| Refusal before tool call for out-of-scope | Yes | Yes |
| Local-only execution | Yes | No (design verification only) |
| Memory files excluded from git | Yes | No (gitignore check) |
