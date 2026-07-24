from types import SimpleNamespace

import duckdb

from src.analytics import evaluate


def test_auto_coverage_uses_human_review_flag(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "metrics.duckdb"
    with duckdb.connect(str(db_path)) as db:
        db.execute("""
            CREATE TABLE ad_risk_scores AS SELECT * FROM (VALUES
              ('meta-auto', 'Meta', false, 'approve', '[{\"term\":\"loan\"}]'),
              ('meta-review', 'Meta', true, 'soft reject', '[{\"term\":\"loan\"}]'),
              ('cfpb-prior', 'CFPB', true, 'use as risk prior', '[]')
            ) t(case_id, source, needs_human_review, recommended_action, evidence_json)
        """)
        db.execute("CREATE TABLE human_review_feedback (feedback_id VARCHAR, case_id VARCHAR, reviewer_decision VARCHAR, notes VARCHAR, created_at TIMESTAMP)")
    monkeypatch.setattr(evaluate, "settings", SimpleNamespace(db_path=db_path))
    result = evaluate.evaluation_metrics()
    assert result["auto_decision_coverage"] == 0.333
    assert result["estimated_review_minutes_saved"] == 3
    assert result["escalation_rate"] == 0.667


def test_cfpb_feedback_never_unlocks_ad_quality_metrics(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "metrics.duckdb"
    with duckdb.connect(str(db_path)) as db:
        db.execute("""
            CREATE TABLE ad_risk_scores AS SELECT * FROM (VALUES
              ('cfpb-prior', 'CFPB', true, 'prioritize for analyst review', '[]', 'risk_prior', 0.9)
            ) t(case_id, source, needs_human_review, recommended_action, evidence_json, decision_scope, risk_score)
        """)
        db.execute("CREATE TABLE human_review_feedback AS SELECT 'f1' feedback_id, 'cfpb-prior' case_id, 'reject' reviewer_decision, '' notes, current_timestamp created_at")
    monkeypatch.setattr(evaluate, "settings", SimpleNamespace(db_path=db_path))
    result = evaluate.evaluation_metrics()
    assert result["total_feedback_events"] == 1
    assert result["labeled_cases"] == 0
    assert result["precision"] is None
