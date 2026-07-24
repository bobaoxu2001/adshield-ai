from src.risk import comparison
from src.risk.comparison import rule_vs_llm_comparison


def test_comparison_is_deterministic_default_without_key() -> None:
    """Without OPENAI_API_KEY, the LLM column must stay empty and nothing is fabricated."""
    result = rule_vs_llm_comparison(limit=3)
    assert result["llm_available"] is False
    assert result["llm_model"] is None
    assert result["default_engine"] == "deterministic_rules_v1"
    assert isinstance(result["cases"], list)
    assert result["sample_size"] == len(result["cases"])

    if result["status"] == "available":
        # Mart is built: each sampled case has deterministic output and an empty LLM cell.
        for case in result["cases"]:
            assert case["deterministic"]["risk_category"]
            assert case["llm"] is None
            assert case["category_agreement"] is None
    else:
        # Mart not built (e.g. CI before ingest): clean empty state, no fabricated cases.
        assert result["status"] == "unavailable"
        assert result["cases"] == []


def test_configured_llm_is_still_on_demand(monkeypatch) -> None:
    row = {
        "case_id": "sample", "source": "Meta", "language": "en", "case_text": "guaranteed loan",
        "product": "commercial advertisement", "risk_category": "Financial Scam / High-Risk Financial Services",
        "risk_score": 0.8, "severity": "high", "recommended_action": "soft reject", "confidence": 0.8,
    }
    calls = []
    monkeypatch.setattr(comparison, "llm_available", lambda: True)
    monkeypatch.setattr(comparison, "_sample_rows", lambda _limit: [row])
    monkeypatch.setattr(comparison, "evaluate_with_openai", lambda payload: calls.append(payload) or None)
    result = comparison.rule_vs_llm_comparison(limit=1, run_llm=False)
    assert calls == []
    assert result["llm_available"] is True
    assert result["llm_requested"] is False


def test_llm_failure_is_isolated_per_case(monkeypatch) -> None:
    row = {
        "case_id": "sample", "source": "Meta", "language": "en", "case_text": "guaranteed loan",
        "product": "commercial advertisement", "risk_category": "Financial Scam / High-Risk Financial Services",
        "risk_score": 0.8, "severity": "high", "recommended_action": "soft reject", "confidence": 0.8,
        "evidence_json": "[]",
    }
    monkeypatch.setattr(comparison, "llm_available", lambda: True)
    monkeypatch.setattr(comparison, "_sample_rows", lambda _limit: [row])
    monkeypatch.setattr(comparison, "evaluate_with_openai", lambda _payload: (_ for _ in ()).throw(TimeoutError("provider timeout")))
    result = comparison.rule_vs_llm_comparison(limit=1, run_llm=True)
    assert result["failure_count"] == 1
    assert result["cases"][0]["llm_error"] == "TimeoutError"
    assert result["cases"][0]["deterministic"]["recommended_action"] == "soft reject"
