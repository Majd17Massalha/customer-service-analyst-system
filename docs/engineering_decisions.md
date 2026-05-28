# Engineering Decisions

## 1. Deterministic Analytics Layer (DuckDB over LLM Reasoning)

**Decision:** All numerical queries are answered exclusively by DuckDB. The LLM is never asked to count, aggregate, or filter dataset rows.

**Rationale:** Language models do not count. When asked "how many billing interactions are in the dataset?" a model will produce a number that sounds plausible but cannot be verified without running the actual query. This is a hard failure mode for an analytics system: a wrong count is worse than no answer. DuckDB executes parameterized SQL and returns exact, reproducible results. This boundary is structural — the only path to a numerical answer is through a tool function return value.

**Trade-off accepted:** Queries that fall outside the five defined tool signatures cannot be answered. This is intentional — an unanswerable query returns a clarification prompt rather than a hallucinated response.

---

## 2. Deterministic Router (No LLM at Routing Time)

**Decision:** Query classification is done by keyword matching against four intent sets. No LLM call is made to determine the route.

**Rationale:** Routing is a high-frequency, low-latency operation. Every query passes through it. An LLM call at routing time would add 1–3 seconds of latency, require an API key, and introduce non-determinism into a classification that only needs to distinguish between four coarse categories. Keyword sets for structured queries (count, how many, total, top), unstructured queries (summarize, show me, examples), out-of-scope signals (weather, stock price, poem), and clarification triggers (more, those, that) cover the practical query space with zero latency and full predictability.

**Trade-off accepted:** Edge cases where a query contains keywords from multiple categories may be misrouted. The router resolves ambiguity by checking out-of-scope first, then structured, then unstructured, then clarification. This ordering minimizes harmful false positives.

---

## 3. Operational Traces vs Chain-of-Thought

**Decision:** The CLI prints a fixed set of trace fields (route, confidence, tool, tool\_input, observation, final\_answer). The internal `trace` list is never exposed.

**Rationale:** Chain-of-thought output creates several risks in a production context: (a) it may leak intermediate data that should not be user-visible, (b) it creates an expectation of reasoning transparency that can be exploited (users learn to phrase queries to manipulate the reasoning path), (c) it bloats the output with content that is irrelevant to the actual answer. The operational trace is sufficient for debugging: it tells you exactly which route was selected, which tool was called, what parameters were passed, and what the tool returned. That is all an operator needs to diagnose a bad answer.

---

## 4. Parameterized SQL (No String Concatenation)

**Decision:** All DuckDB queries use `?` parameter placeholders. User-supplied values are never concatenated into query strings.

**Rationale:** Even in a local, single-user deployment, building SQL from string concatenation is a design defect. It teaches the wrong pattern, and the pattern propagates. When the system is extended (multi-user, REST API, MCP public endpoint), a concatenation vulnerability becomes exploitable immediately. Parameterized queries are the correct default and require no extra effort.

**Implementation note:** `contains()` is used for substring matching instead of `LIKE` with `%` wildcards. This avoids a separate class of injection vectors while providing the same functional result.

---

## 5. No Raw Dataset Rows in Long-Term Memory

**Decision:** `update_profile_from_state()` reads only `category` and `intent` from `tool_input`. It never reads `observation`, `query`, or `final_answer`.

**Rationale:** The `observation` field contains raw dataset rows returned by DuckDB tools (full `instruction` and `response` text). Storing these in a user profile would: (a) grow the profile file without bound, (b) persist user-facing dataset content that may contain sensitive synthetic data patterns, (c) create a data leakage path where content from one user's session could theoretically influence another if profiles were shared. The profile stores only structured metadata (category names, intent names) that is already schema-controlled.

---

## 6. Session Sanitization (Path Traversal Prevention)

**Decision:** `sanitize_session_id()` strips all characters except alphanumeric, dash, and underscore; caps length at 64 chars; rejects empty strings with a fallback to `"default_session"`.

**Rationale:** Session IDs are used directly in filesystem paths (`outputs/memory/sessions/<id>.json`). An unsanitized ID like `../../etc/passwd` or `../outputs/agent.log` would allow a caller to write to arbitrary filesystem locations. This is not hypothetical — it is the first thing a security reviewer checks when they see user input used in a file path.

---

## 7. Bounded Memory Design

**Decision:** `last_query` in session state is capped at 500 characters. Profile fields (`frequent_categories`, `frequent_intents`) deduplicate entries. No unbounded list growth is permitted.

**Rationale:** Unbounded memory accumulation is a resource exhaustion vector. A long-running agent session should not produce ever-growing files. The 500-character cap on query text is generous for analytical queries (which are typically short) while preventing a malicious or accidental multi-kilobyte paste from being persisted. Profile deduplication ensures that repeated queries to the same category do not inflate the stored list.

---

## 8. Why RAG Was Intentionally Postponed

**Decision:** No embedding layer, vector database, or semantic retrieval is implemented.

**Rationale:** The Bitext dataset is a structured, schema-controlled table. Every analytical question has an exact SQL answer. RAG is appropriate when the answer must be assembled from unstructured documents that cannot be queried deterministically. For "how many billing queries are there?" — RAG would retrieve a handful of billing examples and ask the model to estimate a count from them. That is strictly worse than a `COUNT(*)` query. RAG is only appropriate for the genuinely exploratory unstructured path (e.g., "what themes appear in account management complaints?") — and even then, only when the question cannot be answered by keyword search. Implementing RAG before establishing that keyword search is insufficient would add complexity, latency, and a hallucination surface without adding value.

---

## 9. Why Embeddings and Vector DB Were Not Required for Structured Analytics

**Decision:** No vector embeddings are stored or computed.

**Rationale:** The analytics layer answers questions about counts, distributions, and filtered subsets of a structured table. These operations are defined by exact categorical values (`category = 'billing'`, `intent = 'cancel_order'`). Embedding-based similarity search returns approximate nearest neighbors — which is the wrong primitive for categorical matching. Using embeddings to find "billing-like" categories when the exact value "billing" is in the schema would introduce unnecessary approximation error. Exact string matching with case normalization (`LOWER()`) is both more accurate and more efficient.

---

## 10. Why MCP Was Separated from Orchestration

**Decision:** `src/mcp/server.py` is an independent FastMCP server. It does not import from `src/agent/` and is not started as part of the CLI runtime.

**Rationale:** The MCP server is an external tool exposure boundary. Its consumers are external: IDE integrations, LangChain agents, third-party clients. The LangGraph orchestration is an internal execution boundary. Its consumers are internal: the CLI, tests, future plan-mode extensions. Conflating these two boundaries would mean that starting the CLI also starts a network service, that MCP protocol changes break the agent graph, and that the two concerns become impossible to test independently. Separation allows the MCP server to be versioned, restarted, and scaled independently of the agent runtime.

---

## 11. Why Local Execution Was Preferred Over Distributed Execution

**Decision:** The system runs as a single Python process with file-based persistence. No message queues, task workers, or distributed databases are used.

**Rationale:** The current deployment target is a single-analyst workstation. DuckDB is an embedded analytical database — it does not require a server process and provides excellent analytical query performance for datasets up to hundreds of millions of rows without horizontal scaling. Adding Celery, Redis, or a cloud database for a single-user local tool would add operational complexity (running multiple processes, managing connections, handling distributed failures) with no benefit. The architecture is designed so that the DuckDB layer can be replaced with a server-backed database (PostgreSQL, MotherDuck) if horizontal scale becomes a requirement.
