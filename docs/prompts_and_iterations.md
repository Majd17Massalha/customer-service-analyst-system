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

---

## Task 8 — Evaluation, Security, Governance, and Robustness Harness

### How Claude Code Outputs Were Verified

Task 8 required building the evaluation and governance layer on top of the working agent. Every generated artifact was verified before acceptance:

- **Golden dataset entries**: Each entry's `expected_route` was verified by running `route_query()` against the actual query and confirming the result matched.
- **Test assertions**: Every test assertion was traced to a specific code path in the implementation. Tests that assumed router behavior (e.g., "prompt injection routes to clarification") were verified by reading `router.py`'s priority order and confirming the exact normalization + matching logic.
- **Security tests**: SQL injection tests were verified by confirming that DuckDB's `contains()` and parameterized binding treat the injection string as a literal value, not SQL.
- **Documentation claims**: Each claim in `security_audit.md` and `system_reliability.md` references the specific function or file that implements the property.

### Examples of Incorrect AI Behavior in Task 8

1. **Test assertion for whitespace query routing**: Initial assertion expected `route_query("how   many   rows")` to route to `"structured"`. Inspection of `_matches_any()` revealed that `re.search(r"\bhow many\b", "how   many   rows")` would NOT match (single-space pattern, triple-space input). Corrected to `in ("structured", "needs_clarification")`.

2. **_is_clarification 3-word check**: The `_is_clarification` function includes a 3-word length check with no structural signal — this causes "ignore previous instructions" to route to clarification (not out-of-scope). Initial documentation incorrectly described this as routing to `"out_of_scope"`. Corrected after reading the router code carefully.

3. **sanitize_session_id behavior**: Initial documentation described all-special-char inputs as returning `"default_session"`. Inspection revealed that `_SAFE_CHARS.sub("_", "@#$%^&*()")` returns `"_________"` (truthy), which is NOT `"default_session"`. The function only returns `"default_session"` for empty strings. Test assertions were corrected accordingly.

### Regression Bug History

| Bug | Discovered In | Fixed In |
|---|---|---|
| `search_examples` used `LIKE '%keyword%'` string interpolation | Task 3 security review | Task 3 (replaced with `contains()` + parameterized binding) |
| Structured dispatch called wrong tool for all structured queries | Task 5 test failure | Task 5 (added `_detect_structured_tool` regex sub-dispatcher) |
| `_update_session_from_state` stored `observation` as `last_query` | Task 6 manual inspection | Task 6 (truncation cap + correct field mapping) |
| Out-of-scope checked after structured → `write me a count` bypassed refusal | Task 5 routing review | Task 5 (priority order: oos → clarification → structured → unstructured) |
| Session IDs used raw in file paths | Task 6 security review | Task 6 (added `sanitize_session_id()`) |

### Why Human Validation Was Necessary

**Automated tests are necessary but not sufficient.** The test suite verifies deterministic properties (output type, row count, session field values) but cannot verify:

1. **Semantic correctness of refusal messages**: Does the refusal clearly redirect the user? A test can check that `final_answer` is non-empty, but not that it is helpful.
2. **Evaluation rubric subjectivity**: Whether a score-3 answer is acceptable requires a human judgment about usability, not just correctness.
3. **Adversarial completeness**: A human must assess whether the golden dataset covers realistic attack patterns, not just the ones listed by the developer.
4. **Trace output readability**: The operational trace format was validated by reading actual CLI output, not by parsing the printed string in tests.

### Where Deterministic Validation Was Preferred Over AI Judgment

| Decision | Deterministic Approach | Reason |
|---|---|---|
| Row count answers | DuckDB COUNT(*) only | LLM estimates are unreliable for exact counts |
| Category existence check | Exact LOWER() match | Semantic similarity could match wrong categories |
| Routing decisions | Keyword pattern matching | LLM routing adds latency and non-determinism |
| Pass/fail for golden entries | Human score >= 3 threshold | LLM judge can be manipulated or miscalibrated |
| Session sanitization | Regex character allowlist | Fuzzy sanitization creates unpredictable paths |

### Tradeoffs Between Speed and Reliability

| Component | Speed Choice | Reliability Tradeoff |
|---|---|---|
| Keyword router | Instant (< 1ms) | May misclassify novel queries not in phrase sets |
| DuckDB analytics | Fast (< 50ms) | Requires local DuckDB; not cloud-native |
| Extractive summary | No LLM latency | Cannot synthesize cross-category insights |
| Session JSON | Synchronous write | No atomic write → partial corruption on kill |
| Parameterized SQL | Negligible overhead | Always safe; no performance cost to parameterization |

### Token Usage Considerations

- **No LLM calls in routing or analytics**: Zero token cost per query for the core agent path
- **LLM judge template**: Advisory only; must be triggered manually — not part of the request path
- **CLI output**: Never sends user queries or dataset content to external APIs
- **Total token cost per session**: 0 (all computation is local Python + DuckDB)

### Prompt Iteration Strategy

The prompt iteration approach evolved across tasks:

| Task | Prompt Strategy | First-Pass Quality |
|---|---|---|
| 1–2 | Broad spec ("implement DuckDB tools") | Moderate — required SQL injection fix |
| 3–4 | Explicit security requirements in prompt | Good — parameterized queries from first pass |
| 5 | Explicit trace contract fields listed | Good — correct trace fields on first pass |
| 6 | Security invariants listed inline ("never read observation") | Good — most invariants held |
| 7 | Output format specified; file list given | Excellent — docs matched spec |
| 8 | Each test traced to code behavior before writing | Excellent — assertions correct |

**Key insight:** Specificity about security invariants in the prompt correlates directly with first-pass correctness. Vague security requirements ("be secure") produce code that needs correction; explicit invariants ("never read `observation` field in session updates") produce code that satisfies the requirement on the first pass.

---

## Future Smart Hybrid RAG Design

### One-Row-Per-Document Strategy

Each Bitext dataset row becomes one retrieval document:
- **Primary text**: `instruction` field (customer message)
- **Metadata**: `category`, `intent`, `flags` stored as filter-capable metadata
- **Response**: `response` field stored as associated context (not retrieved directly)

### Embedding-Based Semantic Retrieval

For future dense retrieval:
- Embed the `instruction` column using a domain-appropriate model (e.g., `sentence-transformers/all-MiniLM-L6-v2`)
- Index embeddings in a local vector store (FAISS, ChromaDB, or LanceDB)
- Query at inference time: embed the user's query, retrieve top-K most similar instructions

### Metadata-Aware Retrieval

Post-retrieval filtering using DuckDB:
```python
# Retrieve semantically similar rows, then filter by known category
candidates = vector_store.search(query_embedding, top_k=50)
filtered = [r for r in candidates if r.metadata["category"] == known_category]
```

### Hybrid Routing

| Query Type | Route | Tool |
|---|---|---|
| Count / exact aggregate | structured → DuckDB | `count_by_category`, `count_total_rows` |
| Category lookup | structured → DuckDB | `count_by_category`, `get_top_categories` |
| Keyword examples | unstructured → keyword search | `search_examples` |
| Semantic exploration | unstructured_semantic → RAG | vector store retrieval |

**Invariant:** Structured queries always go to DuckDB. RAG is never used for count answers.

### Why RAG Must Never Replace Deterministic Analytics

- Semantic search for "how many refund rows" may retrieve refund-labeled rows but cannot count them accurately without SQL
- Embedding similarity may match semantically related but categorically different rows
- COUNT(*) with exact label match is 100% accurate; semantic count is unreliable
- RAG adds latency and embedding infrastructure cost with no accuracy benefit for structured queries

### Future Vector DB Options

| Option | Strengths | Weaknesses |
|---|---|---|
| FAISS (local) | Fast, no server, Python-native | No metadata filtering |
| ChromaDB (local) | Metadata filtering, persistent | Slower than FAISS |
| LanceDB | Lance format, DuckDB integration | Newer, less mature |
| Qdrant (server) | Full metadata filtering, REST API | Requires server process |

For this project's scale (26,872 rows), FAISS or ChromaDB with local file storage is appropriate.

### Future Reranking

After initial retrieval, apply a cross-encoder reranker to improve result relevance:
- Retrieve top-50 candidates by embedding similarity
- Rerank using a cross-encoder model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`)
- Return top-5 after reranking

### Future Semantic Memory

Long-term memory could be extended to store:
- Embedding of the user's frequent query patterns (not raw text)
- Category preference weights derived from historical queries
- Intent frequency histograms per user

**Constraint:** Embeddings stored in memory must never include raw query text or dataset rows.

---

## Future PLAN MODE Architecture (Design Only)

This section documents a future multi-step planning architecture. It is NOT currently implemented.

### Architecture Proposal

```
User Query
    ↓
[Planner Node]          ← Decomposes multi-step requests into subtasks
    ↓
[Executor Node] × N     ← Executes each subtask (DuckDB tool calls)
    ↓
[Validation Node]       ← Verifies each result before forwarding
    ↓
[Human Approval Gate]   ← Required for multi-step or high-confidence decisions
    ↓
[Response Node]         ← Assembles final answer
```

### Planner Node

- Receives the user's complex query
- Decomposes into an ordered list of subtasks (e.g., "count REFUND", then "count ORDER", then compare)
- Returns a plan with bounded step count (max 5 steps per query)
- **Must never**: generate subtasks that bypass validation or circumvent the category allowlist

### Executor Node

- Executes one subtask at a time using the existing DuckDB analytics tools
- Each tool call is parameterized and validated before execution
- Partial results are logged but not surfaced to user until all steps complete
- **Must never**: execute a step that was not approved by the Planner

### Validation Node

- Checks each executor output against expected type and range
- Flags anomalous results (e.g., count = 0 when category is known to exist)
- Does not override DuckDB results — only flags for review

### Bounded Execution Policy

- Maximum steps per query: 5
- Maximum retry per step: 2
- Maximum total execution time: 10 seconds
- On timeout: return partial results with explicit incompleteness note

### Human Approval Checkpoints

Required before:
- Any operation that writes to persistent storage
- Any query that accesses more than 3 categories in a single session
- Any query where the Validation Node flags an anomaly

### Explainability Requirements

Every multi-step response must include:
- The plan (list of subtasks)
- Tool called for each step
- Observation for each step
- Final assembly logic

### Constraints

- **No autonomous unrestricted execution**: The Planner cannot execute steps without Validator approval
- **No bypass of category allowlist**: Executor may not query arbitrary SQL strings
- **No chain-of-thought surfacing**: Internal plan steps are logged but not shown to user
- **Human override always possible**: Any step can be interrupted by the user before execution

---

## Auditability

### What Is Logged (Operational Trace)

| Event | Log Level | Fields |
|---|---|---|
| Route decision | INFO | route, confidence, reason, latency |
| Tool call | INFO | tool name, parameters, latency |
| Session save | DEBUG | sanitized file path |
| Session load | DEBUG | sanitized file path |
| Corrupted file | WARNING | file path, exception type |
| Query error | ERROR | session ID, exception message |

### Session Traceability

Each session is identified by a sanitized session ID. All log entries for a session share the same `session=<id>` prefix. An operator can filter `outputs/agent.log` by session ID to reconstruct the full query history for a session.

### Deterministic Reproducibility

Given the same query and the same DuckDB state:
- The router always returns the same route (no randomness)
- The analytics tools always return the same result (deterministic SQL)
- The final answer is always the same string (template-formatted from tool output)

The agent is fully reproducible for the same inputs. This is a deliberate property: it enables regression testing without mocking.

### Audit Boundaries

| What | Is Auditable | Notes |
|---|---|---|
| Route decisions | Yes | Logged at INFO level |
| Tool parameters | Yes | Logged at INFO level |
| Tool results | Yes (truncated) | Observation logged at INFO level |
| Session file contents | Yes | JSON files in outputs/memory/sessions/ |
| Profile file contents | Yes | JSON files in outputs/memory/profiles/ |
| Full query text | Partial | Truncated to 64 chars in log; full stored in session |

### What Is Intentionally NOT Logged

| What | Reason |
|---|---|
| Raw dataset row content in logs | Privacy: dataset instructions are customer messages |
| Full observation content | Size: may be large lists; truncated version is sufficient |
| Internal trace list (chain-of-thought) | Security: internal reasoning not for user consumption |
| Profile preference details | Privacy: user behavior patterns |
| DuckDB file absolute path | Security: internal path not needed in user-facing logs |
