# Project Tasks

## Completed

- [x] Task 1: Architecture initialization
- [x] Task 2: Dataset ingestion and schema inspection (Bitext → DuckDB)
- [x] Task 3: Deterministic analytics tools (DuckDB/Pandas, parameterized queries)
- [x] Task 4: FastMCP server (Pydantic validation, tool wrappers)
- [x] Task 5: LangGraph orchestration and execution layer (4-route graph, trace contract)
- [x] Task 6: CLI runtime, session memory, and data leakage prevention
  - `main.py` — `--session` CLI entry point with logging setup
  - `src/cli/chat_loop.py` — interactive loop, operational trace output, exit handling
  - `src/memory/checkpoints.py` — short-term session state (JSON, sanitized IDs)
  - `src/memory/user_profile.py` — long-term user profile (non-sensitive facts only)
  - `tests/test_memory.py` — 27 tests: sanitization, save/load, security, no raw rows
  - `tests/test_cli.py` — 21 tests: EXIT_COMMANDS, trace format, session extraction, loop behavior
  - 155/155 total tests passing
- [x] Task 7: Final submission documentation
  - `README.md` — executive summary, architecture, setup, examples, limitations, future work
  - `docs/engineering_decisions.md` — 11 architectural decision rationales
  - `docs/prompts_and_iterations.md` — AI-assisted development reflection and iteration history
  - `docs/testing_strategy.md` — test categories, intentional gaps, risks, accepted assumptions
  - `docs/failure_modes.md` — query/memory/infrastructure/behavioral failure modes with mitigations
  - All 155 tests continue to pass

## Next

- [ ] Task 8: Persistent follow-up memory behavior
  - Resolve ambiguous follow-up queries ("show me more", "those") using session context
  - Implement safe context substitution from `last_route`, `last_category`, `last_keyword`
  - Add clarification loop: ask once, retry with resolved context
- [ ] Task 9 (Optional): Smart RAG extension
  - Semantic retrieval for open-ended queries not served by keyword search
  - Embedding layer over `instruction` column (FAISS or similar)
  - Gated behind an `unstructured_semantic` route; never replaces deterministic analytics
  - See `docs/engineering_decisions.md` sections 8 and 9 for rationale
