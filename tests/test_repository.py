from types import SimpleNamespace

import duckdb
import pytest

from src.app import repository


def _repository_db(path) -> None:
    with duckdb.connect(str(path)) as db:
        db.execute("""
            CREATE TABLE cfpb_complaints AS SELECT
              'cfpb-late-900'::VARCHAR case_id, 'ordinary complaint text'::VARCHAR case_text,
              'loan'::VARCHAR product, 'billing'::VARCHAR issue, 'CA'::VARCHAR state,
              'https://example.test'::VARCHAR source_url
        """)
        db.execute("""
            CREATE TABLE ads (
              case_id VARCHAR, ad_text VARCHAR, advertiser_name VARCHAR, source_url VARCHAR
            )
        """)
        db.execute("""
            CREATE TABLE ad_risk_scores (
              case_id VARCHAR, source VARCHAR, case_date DATE, language VARCHAR, risk_score DOUBLE,
              risk_category VARCHAR, severity VARCHAR, recommended_action VARCHAR,
              needs_human_review BOOLEAN, decision_scope VARCHAR, confidence DOUBLE
            )
        """)
        db.execute("""
            INSERT INTO ad_risk_scores VALUES (
              'cfpb-late-900', 'CFPB', DATE '2026-01-01', 'en', 0.5,
              'Financial Scam / High-Risk Financial Services', 'medium', 'use as risk prior',
              true, 'risk_prior', 0.7
            )
        """)
        db.execute("""
            CREATE TABLE human_review_feedback (
              feedback_id VARCHAR, case_id VARCHAR, reviewer_decision VARCHAR, notes VARCHAR, created_at TIMESTAMP
            )
        """)


def test_case_id_search_uses_the_complete_server_query(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "repo.duckdb"
    _repository_db(db_path)
    monkeypatch.setattr(repository, "settings", SimpleNamespace(db_path=db_path))
    assert repository.case_count(search="late-900") == 1
    assert repository.cases(search="late-900")[0]["case_id"] == "cfpb-late-900"


def test_feedback_rejects_unknown_case_id(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "repo.duckdb"
    _repository_db(db_path)
    monkeypatch.setattr(repository, "settings", SimpleNamespace(db_path=db_path))
    with pytest.raises(LookupError):
        repository.save_feedback("missing", "approve", reviewer_id="reviewer-1")


def test_public_demo_feedback_is_read_only(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "repo.duckdb"
    _repository_db(db_path)
    monkeypatch.setattr(repository, "settings", SimpleNamespace(db_path=db_path, feedback_writable=False))
    with pytest.raises(PermissionError, match="read-only"):
        repository.save_feedback("cfpb-late-900", "relevant prior", reviewer_id="reviewer-1")


def test_cfpb_feedback_rejects_enforcement_decisions_server_side(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "repo.duckdb"
    _repository_db(db_path)
    monkeypatch.setattr(repository, "settings", SimpleNamespace(db_path=db_path, feedback_writable=True))
    with pytest.raises(ValueError, match="not permitted"):
        repository.save_feedback("cfpb-late-900", "reject", reviewer_id="reviewer-1")
    saved = repository.save_feedback("cfpb-late-900", "relevant prior", reviewer_id="reviewer-1")
    assert saved["reviewer_decision"] == "relevant prior"
    assert saved["reviewer_id"] == "reviewer-1"


def test_case_detail_fetches_single_case_with_trace() -> None:
    """case_detail resolves one case directly (no full-table scan) and attaches its trace."""
    from src.app import repository
    sample = repository.cases(limit=1)
    assert sample, "expected at least one scored case in the mart"
    case_id = sample[0]["case_id"]
    detail = repository.case_detail(case_id)
    assert detail is not None
    assert detail["case_id"] == case_id
    assert detail["decision_trace"]["steps"]
    assert "candidate" in detail["shadow_evaluation"]
    assert repository.case_detail("does-not-exist") is None
