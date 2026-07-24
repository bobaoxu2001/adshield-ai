from __future__ import annotations

import json
from datetime import UTC, datetime

import duckdb
import pandas as pd

from src.config import settings
from src.risk.policy_retriever import load_policy_rules
from src.risk.scoring import score_case
from src.risk.taxonomy import CATEGORY_NAMES
from src.transform.lifecycle_tables import seed_lifecycle_tables


def _ensure_processed() -> None:
    required = ["ftc_fraud_reports.parquet", "cfpb_complaints.parquet", "ads.parquet"]
    missing = [name for name in required if not (settings.processed_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing normalized files: {', '.join(missing)}. Run `make transform`.")


def _score_cases(cfpb: pd.DataFrame, ads: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in cfpb.itertuples(index=False):
        decision = score_case(row.case_id, row.case_text, row.product, "cfpb").to_dict()
        decision.update({"source": "CFPB", "case_date": row.date_received, "evaluated_at": datetime.now(UTC).isoformat()})
        rows.append(decision)
    for row in ads.itertuples(index=False):
        decision = score_case(row.case_id, row.ad_text, "commercial advertisement", "meta").to_dict()
        decision.update({"source": "Meta", "case_date": row.created_at, "evaluated_at": datetime.now(UTC).isoformat()})
        rows.append(decision)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["evidence_json"] = frame.pop("evidence").map(lambda value: json.dumps(value, ensure_ascii=False))
    frame["matched_policy_rule_ids_json"] = frame.pop("matched_policy_rule_ids").map(json.dumps)
    return frame


def _validation(ads: pd.DataFrame, scores: pd.DataFrame) -> dict[str, object]:
    checks = {
        "ads_no_empty_text": bool(ads.empty or ads["ad_text"].fillna("").str.strip().ne("").all()),
        "ads_unique_ids": bool(ads.empty or ads["ad_id"].is_unique),
        "risk_categories_valid": bool(scores.empty or scores["risk_category"].isin(CATEGORY_NAMES).all()),
        "score_source_present": bool(scores.empty or scores["source"].fillna("").str.strip().ne("").all()),
        "score_timestamp_present": bool(scores.empty or scores["evaluated_at"].fillna("").str.strip().ne("").all()),
    }
    checks["passed"] = all(checks.values())
    return checks


def build_duckdb() -> dict[str, int]:
    _ensure_processed()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    ftc = pd.read_parquet(settings.processed_dir / "ftc_fraud_reports.parquet")
    cfpb = pd.read_parquet(settings.processed_dir / "cfpb_complaints.parquet")
    ads = pd.read_parquet(settings.processed_dir / "ads.parquet")
    scores = _score_cases(cfpb, ads)
    scores.to_parquet(settings.processed_dir / "ad_risk_scores.parquet", index=False)
    policies = pd.DataFrame([rule.__dict__ for rule in load_policy_rules()])
    advertisers = ads[["advertiser_id", "advertiser_name", "source", "retrieved_at"]].drop_duplicates("advertiser_id") if not ads.empty else pd.DataFrame(columns=["advertiser_id", "advertiser_name", "source", "retrieved_at"])
    validation = _validation(ads, scores)
    (settings.processed_dir / "validation_report.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    if not validation["passed"]:
        raise ValueError(f"Data validation failed: {validation}")
    with duckdb.connect(str(settings.db_path)) as db:
        for name, frame in {"ftc_fraud_categories": ftc, "cfpb_complaints": cfpb, "ads": ads, "advertisers": advertisers, "ad_risk_scores": scores, "policy_rules": policies}.items():
            db.register("incoming", frame)
            db.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM incoming")
            db.unregister("incoming")
        db.execute("""
            CREATE TABLE IF NOT EXISTS human_review_feedback (
                feedback_id VARCHAR PRIMARY KEY,
                case_id VARCHAR NOT NULL,
                reviewer_decision VARCHAR NOT NULL,
                notes VARCHAR,
                created_at TIMESTAMP NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                run_id VARCHAR, source VARCHAR, status VARCHAR, records BIGINT, created_at TIMESTAMP
            )
        """)
        lifecycle_counts = seed_lifecycle_tables(db)
    counts = {"ftc": len(ftc), "cfpb": len(cfpb), "ads": len(ads), "scores": len(scores), "policies": len(policies)}
    counts.update(lifecycle_counts)
    print(f"DuckDB: built {settings.db_path} with {counts}")
    return counts


if __name__ == "__main__":
    build_duckdb()
