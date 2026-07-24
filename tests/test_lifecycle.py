from dataclasses import FrozenInstanceError

import pytest

from src.risk.lifecycle import (
    CANDIDATE_STRATEGY,
    CURRENT_STRATEGY,
    CURATED_BENCHMARK_CASES,
    create_candidate_version,
    curated_advertiser_profiles,
    decision_trace,
    evaluate_text,
    preview_candidate_strategy,
    run_benchmark,
    threshold_sensitivity,
)


def test_real_and_benchmark_scopes_are_explicitly_isolated() -> None:
    assert len(CURATED_BENCHMARK_CASES) == 60
    assert {row["data_scope"] for row in CURATED_BENCHMARK_CASES} == {"curated_benchmark"}
    real = evaluate_text("cfpb", "guaranteed loan", source="CFPB")
    assert real["data_scope"] == "real_public"
    assert real["recommended_action"] not in {"allow", "soft reject", "hard reject"}
    benchmark = run_benchmark()
    assert {row["evaluation"]["data_scope"] for row in benchmark["results"]} == {"curated_benchmark"}


def test_ftc_is_research_only_and_unknown_sources_are_rejected() -> None:
    ftc = evaluate_text("ftc", "guaranteed illegal drug", source="FTC")
    assert ftc["data_scope"] == "real_public"
    assert ftc["recommended_action"] in {"prioritize for analyst review", "use as risk prior"}
    with pytest.raises(ValueError, match="Unsupported source"):
        evaluate_text("unknown", "guaranteed loan", source="Unknown")


def test_strategy_versions_are_immutable_and_candidates_are_non_authoritative() -> None:
    with pytest.raises(FrozenInstanceError):
        CURRENT_STRATEGY.status = "paused"  # type: ignore[misc]
    candidate = create_candidate_version(CURRENT_STRATEGY, version_id="strategy@test", change_reason="test only", escalation_threshold=0.6)
    assert candidate.authoritative is False
    assert candidate.rollback_target == CURRENT_STRATEGY.version_id
    assert CURRENT_STRATEGY.status == "enforced"


def test_shadow_decision_does_not_override_authoritative_decision() -> None:
    current = evaluate_text("case", "FDIC-insured deposit guarantee", source="Meta", strategy=CURRENT_STRATEGY)
    shadow = evaluate_text("case", "FDIC-insured deposit guarantee", source="Meta", strategy=CANDIDATE_STRATEGY)
    assert current["authoritative"] is True
    assert shadow["authoritative"] is False
    assert current["strategy_version"] == CURRENT_STRATEGY.version_id


def test_positive_exception_is_visible_and_reduces_candidate_score() -> None:
    result = evaluate_text("safe-context", "FDIC-insured deposit guarantee", product="financial services", source="Meta", strategy=CANDIDATE_STRATEGY)
    assert any(item["exception_id"] == "EXC-FDIC" for item in result["matched_exceptions"])
    assert result["adjusted_score"] < result["base_score"]


def test_high_severity_exception_never_silently_allows_harm() -> None:
    result = evaluate_text("danger", "Educational firearm safety about an illegal drug and weapon", source="Meta", strategy=CANDIDATE_STRATEGY)
    assert any(item["blocked_from_override"] for item in result["matched_exceptions"])
    assert result["recommended_action"] != "allow"
    assert result["needs_human_review"] is True


def test_decision_trace_is_complete_and_disclaims_probability() -> None:
    case = {"case_id": "trace", "case_text": "guaranteed loan", "source": "CFPB", "risk_score": 0.7, "confidence": 0.8, "risk_category": "Financial Scam / High-Risk Financial Services", "language": "en", "decision_scope": "risk_prior", "evidence": [{"type": "keyword", "term": "loan"}], "matched_policy_rule_ids": [], "feedback": []}
    trace = decision_trace(case)
    components = {step["component"] for step in trace["steps"]}
    assert trace["complete"] is True
    assert "not a calibrated probability" in trace["score_disclaimer"]
    assert {"Source record", "Negative signals", "Positive exceptions", "Landing-page signals", "Advertiser-level signals", "Confidence components", "Strategy", "Optional LLM", "Reviewer decision"}.issubset(components)
    by_component = {step["component"]: step for step in trace["steps"]}
    assert "unavailable" in by_component["Landing-page signals"]["value"]
    assert "unavailable" in by_component["Advertiser-level signals"]["value"]
    assert by_component["Recommendation"]["value"] == case.get("recommended_action", "use as risk prior")


def test_authoritative_trace_preserves_stored_action_exactly() -> None:
    case = {"case_id": "stored", "case_text": "FDIC-insured deposit guarantee", "source": "CFPB", "risk_score": 0.7, "confidence": 0.8, "risk_category": "Financial Scam / High-Risk Financial Services", "language": "en", "decision_scope": "risk_prior", "recommended_action": "prioritize for analyst review", "needs_human_review": True}
    trace = decision_trace(case, CURRENT_STRATEGY)
    recommendation = next(step for step in trace["steps"] if step["component"] == "Recommendation")
    assert recommendation["value"] == "prioritize for analyst review"


def test_benchmark_metrics_are_bounded_and_use_only_curated_labels() -> None:
    result = run_benchmark()
    assert result["data_scope"] == "curated_benchmark"
    assert result["scenario_count"] == 60
    for key in ("category_agreement", "evidence_coverage", "routing_agreement", "exception_handling_agreement", "mandarin_variant_coverage", "false_positive_scenario_agreement"):
        assert 0 <= result[key] <= 1
    assert result["promotion_gate"]["status"] in {"hold", "eligible_for_review"}
    assert result["promotion_gate"]["threshold"] == 0.9
    assert {row["key"] for row in result["failure_buckets"]} == {"taxonomy", "routing", "evidence", "exceptions"}
    assert all({"count", "owner", "next_step"}.issubset(row) for row in result["failure_buckets"])


def test_threshold_sensitivity_and_reviewer_capacity_are_calculated() -> None:
    rows = threshold_sensitivity(capacity=10)
    assert [row["threshold"] for row in rows] == sorted(row["threshold"] for row in rows)
    assert all(row["capacity_utilization"] == round(row["review_volume"] / 10, 3) for row in rows)
    assert all(row["within_capacity"] == (row["review_volume"] <= 10) for row in rows)


def test_editable_candidate_preview_remains_shadow_and_capacity_aware() -> None:
    result = preview_candidate_strategy(0.45, 0.55, 10)
    assert result["data_scope"] == "curated_benchmark"
    assert result["authoritative"] is False
    assert result["strategy"]["rollback_target"] == CURRENT_STRATEGY.version_id
    assert result["strategy"]["status"] == "shadow"
    assert result["capacity_utilization"] == round(result["review_volume"] / 10, 3)
    assert result["within_capacity"] == (result["review_volume"] <= 10)


def test_candidate_preview_rejects_invalid_threshold_order() -> None:
    with pytest.raises(ValueError, match="risk.*escalation"):
        preview_candidate_strategy(0.7, 0.5, 10)


def test_curated_advertiser_profiles_never_impersonate_real_companies() -> None:
    profiles = curated_advertiser_profiles()
    assert profiles
    assert {row["data_scope"] for row in profiles} == {"curated_benchmark"}
    assert all(row["advertiser_id"].startswith("CURATED-ADV-") for row in profiles)
    assert all("Benchmark Advertiser" in row["display_name"] for row in profiles)


def test_dialog_accessibility_contract_remains_present() -> None:
    source = (pytest.importorskip("pathlib").Path(__file__).parents[1] / "src" / "App.jsx").read_text()
    assert 'role="dialog"' in source
    assert 'aria-modal="true"' in source
    assert 'event.key === "Escape"' in source
    assert 'event.key !== "Tab"' in source
    assert 'window.scrollTo({ top: 0' in source
