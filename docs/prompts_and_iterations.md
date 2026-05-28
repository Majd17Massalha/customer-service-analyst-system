## Task 1 — Dataset Ingestion and Schema Inspection

Results:
- Dataset loaded successfully from Hugging Face
- Split count:
  - train: 26,872 rows
- Columns:
  - flags
  - instruction
  - category
  - intent
  - response

Engineering decisions:
- Persisted dataset into local DuckDB
- Added runtime logging and observability
- Used deterministic persistence layer
- Added safe table naming strategy

Validation:
- Verified DuckDB creation
- Verified row counts
- Verified table existence
- Verified logging output


## Task 5 — LangGraph Execution Layer

Implemented:
- `src/agent/nodes.py`: expanded `AgentState` (trace contract fields + `db_path` injection),
  replaced placeholder nodes with `node_structured_dispatch` and `node_unstructured_retrieval`
- `src/agent/graph.py`: updated node references, same 4-branch topology
- `tests/test_agent_execution.py`: 9 tests covering all routes and trace contract
- `tests/test_router.py`: removed stale PLACEHOLDER assertions from graph integration tests

Architecture decisions:
- `AgentState(total=False)` — partial initial states accepted by LangGraph; nodes use `.get()` for optional fields
- `db_path` field in state — allows tests to inject an isolated DuckDB without patching globals
- Structured dispatch uses pure regex sub-dispatcher (`_detect_structured_tool`) — no DB access before tool call
- Unstructured retrieval uses extractive summary from `search_examples` or `get_top_categories` — no LLM
- All four nodes populate the full trace contract: `selected_tool`, `tool_input`, `observation`, `final_answer`
- Out-of-scope and clarification nodes set `selected_tool=None`, `tool_input={}`, `observation=None`

Trace contract (every graph response):
- `route_result.route` — routing decision
- `selected_tool` — analytics function called (None for refusals)
- `tool_input` — validated parameters passed to tool
- `observation` — raw tool return value
- `final_answer` — human-readable answer grounded in observation

Testing:
- 9/9 pytest tests passed in test_agent_execution.py
- 107/107 total tests passed across all four test files
- No LLM calls, no API keys, isolated DuckDB fixture

## Task 6 — CLI Runtime, Session Memory, and Data Leakage Prevention

### CLI Runtime

Implemented `main.py` as the single entry point:
- Accepts `--session <session_id>` (required)
- Configures logging to `outputs/agent.log` + stderr before importing any project code
- Delegates entirely to `src/cli/chat_loop.py`

`src/cli/chat_loop.py` is a thin I/O layer:
- `EXIT_COMMANDS = {"exit", "quit", "q"}` — matched case-sensitively against `.lower()`
- Empty and whitespace-only inputs are skipped silently
- `EOFError` / `KeyboardInterrupt` terminate the loop gracefully
- Each query invokes `graph.invoke({"query": ..., "trace": []})` from the existing LangGraph graph
- Output is limited to operational trace fields: `route`, `confidence`, `tool`, `tool_input`, `observation` (truncated at 300 chars), `final_answer`
- The internal `trace` list is never printed — no chain-of-thought in CLI output
- Local file paths are never included in user-facing output

### Session Handling (Short-Term Memory)

`src/memory/checkpoints.py`:
- `sanitize_session_id()` — strips all non-alphanumeric characters (except `_` and `-`), caps at 64 chars, returns `"default_session"` for empty input
- `SessionState` dataclass — fields: `session_id`, `last_query`, `last_route`, `last_tool`, `last_category`, `last_intent`, `last_keyword`, `last_result_offset`
- `save_session()` / `load_session()` — JSON persistence to `outputs/memory/sessions/`; corrupted files fall back to a fresh state with a warning log
- `last_query` is truncated to 500 chars maximum before storage to avoid leaking long free-text queries
- `outputs/memory/` is covered by the existing `outputs/` entry in `.gitignore`

### Long-Term Memory Boundaries

`src/memory/user_profile.py`:
- `UserProfile` dataclass — `session_id`, `user_name`, `preferred_topics`, `frequent_categories`, `frequent_intents`, `preferred_output_style`
- `_NEVER_STORE` set — defensive check strips `api_key`, `token`, `password`, `secret`, `credential`, `email`, `phone`, `ssn`, `raw_query`, `dataset_row` before writing
- `update_profile_from_state()` — extracts only `category` and `intent` from `tool_input`; deduplicates; never reads from `observation` (which may contain raw rows)
- Profiles persisted to `outputs/memory/profiles/`

### Data Leakage Prevention Decisions

| Threat | Mitigation |
|---|---|
| Raw dataset rows in session | `_update_session_from_state` reads only `route_result`, `selected_tool`, `tool_input` — never `observation` |
| Long free-text queries in session | `last_query` capped at 500 chars |
| Sensitive user input in profiles | `_NEVER_STORE` defensive strip on save; `update_profile_from_state` never reads query text |
| Chain-of-thought leakage | `trace` list never printed; `_print_trace` prints only named operational fields |
| Path disclosure | No local file paths in `_print_trace` or `final_answer` |
| Session ID path traversal | `sanitize_session_id()` strips `/`, `\`, `.`, `@` and all non-safe chars |
| Memory directory in git | `outputs/` already in `.gitignore` |

### Testing

Added 27 tests in `tests/test_memory.py`:
- 8 sanitization edge cases (normal, special chars, path traversal, empty, length, dash/underscore, spaces)
- 6 session save/load round-trips (directories auto-created, JSON valid, all fields, corrupted fallback)
- 5 profile save/load round-trips
- 3 security tests (no sensitive keys, no raw dataset rows in sessions or profiles)
- 5 `update_profile_from_state` tests (adds, deduplicates, empty/missing tool_input)

Added 21 tests in `tests/test_cli.py`:
- 4 EXIT_COMMANDS constant checks
- 6 `_print_trace` output checks (route/tool shown, tool_input shown, out-of-scope, observation truncation, no chain-of-thought, no tool line when None)
- 6 `_update_session_from_state` field extraction checks (route, tool+category, intent, keyword, query truncation, no raw-row leakage)
- 5 `run_chat_loop` behavior tests (exit/quit/q, empty input skipped, EOF graceful)

Total: 155/155 tests passing across all six test files.

## Task 2 — Deterministic Analytics Layer

Implemented:
- count_total_rows
- count_by_category
- count_by_intent
- get_top_categories
- search_examples

Security decisions:
- Parameterized queries only
- contains() instead of LIKE
- Strict input validation

Testing:
- 31/31 pytest tests passed
- tmp_path isolated DuckDB fixture
- Invalid input edge-case coverage

Observability:
- Tool execution logging
- Latency tracking

---

## Task 7 — Engineering Documentation and Submission Package

### What Was Created

| File | Purpose |
|---|---|
| `README.md` | Full project overview, architecture, setup, examples, limitations, future work |
| `docs/engineering_decisions.md` | Detailed rationale for 11 architectural decisions |
| `docs/testing_strategy.md` | Test categories, intentional gaps, remaining risks, accepted assumptions |
| `docs/failure_modes.md` | Query-level, memory, infrastructure, and behavioral failure modes with mitigations |
| `TASKS.md` | Updated task list reflecting Task 7 completion |

### AI-Assisted Development Reflection

**How Claude Code was used:**

Claude Code was used as the primary implementation agent across all tasks. The prompting approach evolved significantly across the seven tasks:

- **Early tasks (1–3):** Prompts were broad specifications ("implement DuckDB analytics tools with parameterized queries"). Initial outputs required correction for edge cases — for example, the first version of `search_examples` used `LIKE '%keyword%'` string interpolation, which was caught during security review and replaced with `contains()` and parameterized binding.

- **Mid tasks (4–5):** Prompts became more precise as architecture solidified. The LangGraph graph topology was specified explicitly in the prompt (four named branches, START/END topology, trace contract fields). The most significant correction was in the structured dispatch node, which initially attempted to call the wrong tool for "how many X" queries — the regex sub-dispatcher was refined iteratively until all 9 orchestration tests passed.

- **Late tasks (6–7):** Prompts included explicit security requirements and test count targets. The data leakage prevention design (never reading `observation` in session updates) was specified in the prompt after the initial implementation was found to be storing raw DuckDB rows in session files.

**Bugs caught through testing (not trusted blindly):**

1. `search_examples` used `LIKE '%keyword%'` string interpolation (SQL injection risk) → replaced with `contains()` and parameterized binding
2. `_update_session_from_state()` read `observation` instead of `query` for `last_query` field → caught by manual session file inspection, fixed with truncation cap
3. Out-of-scope node was attempting tool dispatch for `None` tool inputs → caught by orchestration test `test_out_of_scope_does_not_call_tool`
4. Router checked structured keywords before out-of-scope keywords, allowing "write me a count" to bypass refusal → routing priority order corrected
5. Session IDs were used in file paths without sanitization → added `sanitize_session_id()` after security review

**Why outputs were verified instead of trusted blindly:**

Every analytics function output was verified against known fixture data. Tests were written before implementation in several cases (TDD approach), which meant the implementation was required to produce specific values rather than values that "looked right." The session file inspection during manual testing caught the raw-row leakage bug that automated tests had not yet covered — which is why `test_no_raw_rows_in_session` was subsequently added as a permanent regression test.

**How prompts evolved:**

The initial task prompts said "implement X." By Task 6, prompts said "implement X with the following security properties, never reading Y from state, storing only Z in profiles, capping field lengths at N characters." Specificity in prompts correlates directly with first-pass correctness. Vague prompts require more correction loops; precise prompts require fewer.

**Examples of incorrect AI behavior that required correction:**

- Task 2: Generated `search_examples` used string concatenation in SQL. Corrected by explicit security requirement in follow-up prompt.
- Task 5: Generated structured dispatch node called `count_total_rows` for all structured queries regardless of keyword. Corrected by adding the `_detect_structured_tool` regex sub-dispatcher.
- Task 6: Generated `_update_session_from_state` stored `observation` text as `last_query`. Corrected after manual inspection of session JSON files.
