from __future__ import annotations

from datetime import UTC, datetime

import duckdb
import pandas as pd

from src.risk.lifecycle import CANDIDATE_STRATEGY, CURRENT_STRATEGY, evaluate_text, json_rows, lifecycle_records


def seed_lifecycle_tables(db: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Persist isolated lifecycle catalogs and benchmarks into the analytical mart."""
    counts: dict[str, int] = {}
    for table, records in lifecycle_records().items():
        frame = pd.DataFrame(json_rows(records))
        db.register("lifecycle_incoming", frame)
        db.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM lifecycle_incoming")
        db.unregister("lifecycle_incoming")
        counts[table] = len(frame)
    db.execute("""
        CREATE TABLE IF NOT EXISTS strategy_shadow_results (
            shadow_result_id VARCHAR PRIMARY KEY,
            case_id VARCHAR NOT NULL,
            data_scope VARCHAR NOT NULL,
            authoritative_strategy_version VARCHAR NOT NULL,
            candidate_strategy_version VARCHAR NOT NULL,
            authoritative_action VARCHAR NOT NULL,
            candidate_action VARCHAR NOT NULL,
            candidate_score DOUBLE,
            differs BOOLEAN NOT NULL,
            evaluated_at TIMESTAMP NOT NULL
        )
    """)
    db.execute("CREATE OR REPLACE VIEW strategies AS SELECT * FROM strategy_versions")
    db.execute("CREATE OR REPLACE VIEW reviewer_feedback AS SELECT * FROM human_review_feedback")
    db.execute("""
        CREATE TABLE IF NOT EXISTS strategy_assignments (
            assignment_id VARCHAR PRIMARY KEY, strategy_version VARCHAR NOT NULL,
            assignment_scope VARCHAR NOT NULL, status VARCHAR NOT NULL, assigned_at TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS advertiser_integrity_profiles (
            advertiser_id VARCHAR, data_scope VARCHAR, profile_json VARCHAR, updated_at TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS decision_trace (
            trace_id VARCHAR PRIMARY KEY,
            case_id VARCHAR NOT NULL,
            data_scope VARCHAR NOT NULL,
            strategy_version VARCHAR NOT NULL,
            trace_json VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_results (
            benchmark_run_id VARCHAR,
            scenario_id VARCHAR,
            strategy_version VARCHAR,
            data_scope VARCHAR CHECK (data_scope = 'curated_benchmark'),
            result_json VARCHAR,
            created_at TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS emerging_risk_candidates (
            candidate_id VARCHAR,
            data_scope VARCHAR,
            signal VARCHAR,
            status VARCHAR CHECK (status IN ('investigate', 'dismiss', 'monitor', 'propose_taxonomy_signal')),
            evidence_json VARCHAR,
            created_at TIMESTAMP
        )
    """)
    db.execute("DELETE FROM strategy_shadow_results")
    case_rows = db.execute("""
        WITH case_texts AS (
          SELECT case_id, case_text, product FROM cfpb_complaints
          UNION ALL SELECT case_id, ad_text, 'commercial advertisement' product FROM ads
        )
        SELECT s.case_id, s.source, c.case_text, c.product, s.recommended_action
        FROM ad_risk_scores s JOIN case_texts c USING (case_id)
    """).fetchall()
    shadow_rows = []
    action_aliases = {"approve": "allow", "escalate to human review": "escalate"}
    evaluated_at = datetime.now(UTC).isoformat()
    for case_id, source, text, product, authoritative_action in case_rows:
        candidate = evaluate_text(str(case_id), str(text or ""), product=str(product or ""), source=str(source), strategy=CANDIDATE_STRATEGY)
        normalized_authoritative_action = action_aliases.get(str(authoritative_action), str(authoritative_action))
        shadow_rows.append((
            f"shadow:{case_id}:{CANDIDATE_STRATEGY.version_id}", str(case_id),
            str(candidate["data_scope"]), CURRENT_STRATEGY.version_id, CANDIDATE_STRATEGY.version_id,
            normalized_authoritative_action, str(candidate["recommended_action"]), float(candidate["adjusted_score"]),
            normalized_authoritative_action != str(candidate["recommended_action"]), evaluated_at,
        ))
    if shadow_rows:
        db.executemany("INSERT INTO strategy_shadow_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", shadow_rows)
    counts["strategy_shadow_results"] = len(shadow_rows)
    return counts
