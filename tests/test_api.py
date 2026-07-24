from fastapi.testclient import TestClient

from src.app.api import app

client = TestClient(app)


def test_health_reports_real_data_only() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["real_data_only"] is True
    assert "database_ready" in body
    assert body["deployment_mode"] in {"local_writable_mart", "public_read_only_snapshot"}
    assert isinstance(body["feedback_writable"], bool)


def test_llm_comparison_endpoint_is_safe_without_key() -> None:
    """The endpoint must respond without error and never claim an LLM is available without a key."""
    response = client.get("/api/llm-comparison?limit=3")
    assert response.status_code == 200
    body = response.json()
    assert body["llm_available"] is False
    assert "cases" in body
    assert isinstance(body["cases"], list)


def test_lifecycle_product_endpoints_keep_scopes_separate() -> None:
    policy = client.get("/api/policy-studio")
    strategies = client.get("/api/strategies")
    benchmark = client.get("/api/benchmark-lab")
    provenance = client.get("/api/system-provenance")
    assert policy.status_code == 200
    assert strategies.status_code == 200
    assert benchmark.status_code == 200
    assert provenance.status_code == 200
    assert policy.json()["data_scope"] == "hypothetical_simulation"
    assert strategies.json()["active_version"]["authoritative"] is True
    assert strategies.json()["candidate_version"]["authoritative"] is False
    assert benchmark.json()["data_scope"] == "curated_benchmark"
    assert benchmark.json()["scenario_count"] == 60
    assert "real_public" in provenance.json()["data_scopes"]


def test_metric_root_causes_and_operational_stages_are_explicit() -> None:
    metrics = client.get("/api/metrics").json()
    assert "root_cause_decomposition" in metrics
    assert "not causal" in metrics["root_cause_note"]
    assert metrics["metric_change_summary"]["primary_driver"]
    assert metrics["metric_change_summary"]["operator_readout"]
    operations = client.get("/api/operational-performance?sample_size=3").json()
    assert set(operations["stages"]) == {"evidence_extraction", "policy_retrieval", "end_to_end_scoring_call", "total_pipeline"}
    assert operations["traffic_claim"].endswith("not production-scale traffic.")


def test_strategy_preview_api_is_non_authoritative_and_validated() -> None:
    response = client.post("/api/strategy-preview", json={"risk_threshold": 0.45, "escalation_threshold": 0.55, "reviewer_capacity": 20})
    assert response.status_code == 200
    assert response.json()["authoritative"] is False
    invalid = client.post("/api/strategy-preview", json={"risk_threshold": 0.7, "escalation_threshold": 0.5, "reviewer_capacity": 20})
    assert invalid.status_code == 400


def test_emerging_risk_discovery_contract_is_complete() -> None:
    response = client.get("/api/emerging-risks")
    assert response.status_code == 200
    assert {"candidates", "novel_ngrams", "category_spikes", "unusual_evidence_combinations", "source_category_mix"}.issubset(response.json())


def test_launch_readiness_separates_benchmark_pass_from_production_hold() -> None:
    benchmark = client.get("/api/benchmark-lab").json()
    readiness = client.get("/api/launch-readiness").json()
    assert benchmark["baseline"]["category_agreement"] == 0.5  # frozen v1 honest baseline
    assert benchmark["promotion_gate"]["status"] == "eligible_for_review"
    assert readiness["benchmark_gate"]["status"] == "eligible_for_review"
    assert readiness["status"] == "hold"
    assert any(item["key"] == "authorized_ad_records" for item in readiness["blockers"])
    assert readiness["public_evidence"]["real_ad_records"] == 500
    assert readiness["public_evidence"]["promotion_eligible"] is False


def test_public_evidence_endpoint_keeps_external_labels_out_of_enforcement_scope() -> None:
    response = client.get("/api/public-evidence")
    assert response.status_code == 200
    body = response.json()
    assert body["uw_summary"]["ad_records"] == 500
    assert body["uw_summary"]["rating_observations"] == 5104
    assert body["sources"][0]["label_scope"] == "participant opinions"
    assert body["sources"][0]["promotion_eligible"] is False
    assert body["identity_provider"]["public_substitute_available"] is False
    assert body["availability_monitoring"]["reporting_eligible"] is False


def test_multimodal_text_endpoint_exposes_upstream_modality_provenance() -> None:
    response = client.post("/api/multimodal-text/evaluate", json={"creative_text": "caption", "ocr_text": "稳转项目"})
    assert response.status_code == 200
    assert response.json()["modality_availability"]["ocr_text"] is True
    assert response.json()["evidence"][0]["modality"] == "ocr_text"


def test_spa_route_confines_file_serving_to_dist() -> None:
    """The SPA fallback must never serve files outside the built dist directory."""
    for path in ("/../pyproject.toml", "/%2e%2e/pyproject.toml", "/../.env", "/assets/../../.env"):
        response = client.get(path)
        assert response.status_code in {200, 404}
        assert b"[project]" not in response.content
        assert b"META_ACCESS_TOKEN" not in response.content
