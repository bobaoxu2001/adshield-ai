"""Export the minimum public, read-only DuckDB snapshot used by Vercel."""

from pathlib import Path

import duckdb

from src.config import ROOT
from src.transform.lifecycle_tables import seed_lifecycle_tables

SOURCE = ROOT / "data" / "processed" / "adshield.duckdb"
TARGET = ROOT / "data" / "deploy" / "adshield.duckdb"
TABLES = (
    "cfpb_complaints",
    "ftc_fraud_categories",
    "ads",
    "ad_risk_scores",
    "policy_rules",
    "human_review_feedback",
)


def export() -> Path:
    if not SOURCE.exists():
        raise FileNotFoundError("Build the local mart before exporting the Vercel snapshot.")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.unlink(missing_ok=True)
    with duckdb.connect(str(TARGET)) as output:
        source_path = str(SOURCE).replace("'", "''")
        output.execute(f"ATTACH '{source_path}' AS source (READ_ONLY)")
        for table in TABLES:
            output.execute(f"CREATE TABLE {table} AS SELECT * FROM source.{table}")
        output.execute("DETACH source")
        seed_lifecycle_tables(output)
        output.execute("VACUUM")
    return TARGET


if __name__ == "__main__":
    print(export())
