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