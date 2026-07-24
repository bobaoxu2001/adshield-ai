from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.risk.data_access import AuthorizedDataBatch, validate_authorized_batch
from src.risk.evidence_extractor import extract_evidence, extract_multimodal_text_evidence


def _batch(record_id: str = "ad-1") -> dict[str, object]:
    return {
        "authorization": {
            "source_system": "authorized-export",
            "tenant_id": "tenant-1",
            "authorization_reference": "ticket-12345",
            "allowed_fields": ["source_record_id", "advertiser_id", "creative_text", "observed_at", "market", "language"],
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
        "records": [{
            "source_record_id": record_id,
            "advertiser_id": "advertiser-1",
            "creative_text": "authorized creative",
            "observed_at": datetime.now(UTC).isoformat(),
            "market": "US",
            "language": "en",
        }],
    }


def test_authorized_batch_validates_without_persisting_or_relabeling() -> None:
    result = validate_authorized_batch(AuthorizedDataBatch.model_validate(_batch()))
    assert result["status"] == "validated_not_persisted"
    assert result["data_scope"] == "authorized_ads"
    assert result["records_with_enforcement_labels"] == 0


def test_curated_identifiers_cannot_enter_authorized_scope() -> None:
    with pytest.raises(ValidationError, match="Curated or synthetic"):
        AuthorizedDataBatch.model_validate(_batch("CURATED-ADV-01"))


def test_payload_cannot_use_fields_outside_authorization_scope() -> None:
    payload = _batch()
    payload["records"][0]["enforcement_label"] = "reject"
    payload["records"][0]["enforcement_label_source"] = "internal-review-v1"
    with pytest.raises(ValidationError, match="outside the authorization scope"):
        AuthorizedDataBatch.model_validate(payload)


def test_candidate_homophones_and_upstream_modalities_keep_provenance() -> None:
    homophones = extract_evidence("稳转项目，家薇联系", profile="v2.1")
    assert {item.get("canonical_term") for item in homophones if item["type"] == "curated_homophone_variant"} == {"稳赚", "加微"}
    result = extract_multimodal_text_evidence("ordinary caption", ocr_text="保苯理财", asr_text="秒披贷款")
    assert result["modality_availability"] == {"creative_text": True, "ocr_text": True, "asr_text": True}
    assert {item["modality"] for item in result["evidence"]} >= {"ocr_text", "asr_text"}
    assert "raw-media understanding is not claimed" in result["provenance_note"]
