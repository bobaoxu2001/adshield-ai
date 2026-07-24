from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class AuthorizationContext(BaseModel):
    source_system: str = Field(min_length=2)
    tenant_id: str = Field(min_length=2)
    authorization_reference: str = Field(min_length=6)
    allowed_fields: list[str] = Field(min_length=1)
    expires_at: datetime


class AuthorizedAdRecord(BaseModel):
    source_record_id: str = Field(min_length=1)
    advertiser_id: str = Field(min_length=1)
    creative_text: str = Field(min_length=1)
    observed_at: datetime
    market: str = Field(min_length=2)
    language: str = Field(pattern=r"^(en|zh|mixed)$")
    landing_page_text: str | None = None
    ocr_text: str | None = None
    asr_text: str | None = None
    enforcement_label: str | None = None
    enforcement_label_source: str | None = None
    advertiser_history: list[dict[str, object]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_label_provenance(self) -> "AuthorizedAdRecord":
        if self.enforcement_label and not self.enforcement_label_source:
            raise ValueError("Every enforcement label requires an enforcement_label_source")
        if self.source_record_id.upper().startswith(("CURATED", "SYNTHETIC", "DEMO")):
            raise ValueError("Curated or synthetic identifiers cannot enter the authorized-ad scope")
        return self


class AuthorizedDataBatch(BaseModel):
    authorization: AuthorizationContext
    records: list[AuthorizedAdRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_scope(self) -> "AuthorizedDataBatch":
        if self.authorization.expires_at <= datetime.now(self.authorization.expires_at.tzinfo):
            raise ValueError("Authorization is expired")
        required = {"source_record_id", "advertiser_id", "creative_text", "observed_at", "market", "language"}
        missing = sorted(required - set(self.authorization.allowed_fields))
        if missing:
            raise ValueError(f"Authorization does not allow required fields: {', '.join(missing)}")
        optional_fields = {
            "landing_page_text": any(item.landing_page_text for item in self.records),
            "ocr_text": any(item.ocr_text for item in self.records),
            "asr_text": any(item.asr_text for item in self.records),
            "enforcement_label": any(item.enforcement_label for item in self.records),
            "enforcement_label_source": any(item.enforcement_label_source for item in self.records),
            "advertiser_history": any(item.advertiser_history for item in self.records),
        }
        unauthorized = sorted(name for name, used in optional_fields.items() if used and name not in self.authorization.allowed_fields)
        if unauthorized:
            raise ValueError(f"Payload uses fields outside the authorization scope: {', '.join(unauthorized)}")
        ids = [item.source_record_id for item in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source_record_id values are not allowed")
        return self


def validate_authorized_batch(batch: AuthorizedDataBatch) -> dict[str, object]:
    return {
        "status": "validated_not_persisted",
        "data_scope": "authorized_ads",
        "source_system": batch.authorization.source_system,
        "tenant_id": batch.authorization.tenant_id,
        "record_count": len(batch.records),
        "records_with_enforcement_labels": sum(bool(item.enforcement_label) for item in batch.records),
        "records_with_advertiser_history": sum(bool(item.advertiser_history) for item in batch.records),
        "records_with_ocr_text": sum(bool(item.ocr_text) for item in batch.records),
        "records_with_asr_text": sum(bool(item.asr_text) for item in batch.records),
        "next_step": "Persist only through a governed warehouse adapter with encryption, retention, and audit controls.",
    }
