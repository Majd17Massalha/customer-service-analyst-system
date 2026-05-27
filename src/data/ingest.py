import logging
import re
import sys
from pathlib import Path

import duckdb
from datasets import load_dataset

DATASET_ID = "bitext/Bitext-customer-support-llm-chatbot-training-dataset"
OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"
DB_PATH = OUTPUTS_DIR / "customer_support.duckdb"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUTS_DIR / "agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _safe_table_name(split: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", split)
    return f"customer_support_{sanitized}"


def load_and_inspect():
    logger.info("Loading dataset: %s", DATASET_ID)
    try:
        dataset = load_dataset(DATASET_ID)
    except Exception as exc:
        logger.error("Failed to load dataset: %s", exc)
        raise

    splits = list(dataset.keys())

    print("\n=== Dataset Splits ===")
    print(splits)

    print("\n=== Row Counts ===")
    for split in splits:
        print(f"  {split}: {len(dataset[split]):,} rows")

    first_split = dataset[splits[0]]
    columns = first_split.column_names

    print("\n=== Column Names ===")
    print(columns)

    print("\n=== Sample Rows (3) ===")
    sample_df = first_split.select(range(min(3, len(first_split)))).to_pandas()
    print(sample_df.to_string(index=False))

    return dataset, splits, columns


def save_to_duckdb(dataset, splits: list[str]) -> None:
    logger.info("Saving dataset to DuckDB: %s", DB_PATH)
    try:
        con = duckdb.connect(str(DB_PATH))
        for split in splits:
            df = dataset[split].to_pandas()  # noqa: F841  — used by DuckDB via locals
            table = _safe_table_name(split)
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df")
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            logger.info("Saved table '%s': %d rows", table, count)
        con.close()
    except Exception as exc:
        logger.error("Failed to save to DuckDB: %s", exc)
        raise

    logger.info("DuckDB written to: %s", DB_PATH)


def main() -> None:
    dataset, splits, _columns = load_and_inspect()
    save_to_duckdb(dataset, splits)
    print(f"\nDone. Database written to: {DB_PATH}")


if __name__ == "__main__":
    main()
