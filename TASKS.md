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

- [x] Task 8: Evaluation, security, governance, and robustness harness
  - `src/evaluation/golden_dataset.py` — 33 entries across STRUCTURED, UNSTRUCTURED, OUT_OF_SCOPE, CLARIFICATION, ADVERSARIAL, MALFORMED categories
  - `src/evaluation/eval_metrics.py` — deterministic pass rate, route accuracy, per-category metrics
  - `src/evaluation/manual_review.py` — human scoring framework (1–5 rubric, CSV/JSON export)
  - `src/evaluation/llm_judge_template.py` — advisory LLM judge template (no API calls)
  - `tests/test_adversarial_queries.py` — 31 adversarial and injection tests
  - `tests/test_failure_modes.py` — 21 failure mode and graceful degradation tests
  - `tests/test_security_edges.py` — 24 security boundary and data leakage tests
  - `docs/evaluation_plan.md` — human evaluation framework, scoring rubric, per-route criteria
  - `docs/security_audit.md` — SQL injection, memory leakage, session sanitization, trace boundaries
  - `docs/adversarial_cases.md` — 16 adversarial case inventory with mitigations and residual risks
  - `docs/system_reliability.md` — 15 failure modes with detection, fallback, and risk level
  - `docs/data_analysis.md` — category/intent distribution, noise analysis, RAG implications
  - `docs/prompts_and_iterations.md` — Task 8 governance reflection, future RAG design, PLAN MODE proposal, auditability

## Next

- [ ] Task 9 (Optional): Smart RAG extension
  - Semantic retrieval for open-ended queries not served by keyword search
  - Embedding layer over `instruction` column (FAISS or similar)
  - Gated behind an `unstructured_semantic` route; never replaces deterministic analytics
  - See `docs/engineering_decisions.md` sections 8 and 9 and `docs/data_analysis.md` for rationale
