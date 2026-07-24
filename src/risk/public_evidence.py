from __future__ import annotations

import json
from pathlib import Path

from src.config import settings


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def public_evidence_registry() -> dict[str, object]:
    root = settings.root / "data" / "public_validation"
    uw = _read_json(root / "uw_bad_ads_summary.json")
    availability = _read_json(root / "production_availability.json")
    probes = availability.get("observations", []) if availability else []
    passed = sum(bool(item.get("passed")) for item in probes)
    return {
        "data_scope": "public_evidence_registry",
        "sources": [
            {
                "key": "uw_ad_perceptions",
                "name": "UW CHI 2021 Ad Perceptions",
                "status": "aggregate_evidence_loaded" if uw else "not_loaded",
                "records": uw.get("ad_records", 0) if uw else 0,
                "independent_annotators": uw.get("reported_unique_annotators", 0) if uw else 0,
                "label_scope": "participant opinions",
                "promotion_eligible": False,
                "source_url": uw.get("source_page") if uw else "https://badads.cs.washington.edu/datasets.html",
                "truth_boundary": uw.get("truth_boundary") if uw else "Not loaded.",
            },
            {
                "key": "tiktok_commercial_content",
                "name": "TikTok Commercial Content API",
                "status": "token_configured" if settings.tiktok_research_access_token else "approval_required",
                "records": 0,
                "label_scope": "public ad and advertiser metadata; status is not an internal violation label",
                "promotion_eligible": False,
                "source_url": "https://developers.tiktok.com/products/commercial-content-api/",
                "truth_boundary": "The connector is implemented, but no record is claimed until an approved research token returns it.",
            },
        ],
        "uw_summary": uw,
        "identity_provider": {
            "status": "not_configured",
            "public_substitute_available": False,
            "required_control": "Organization-owned OIDC provider with cryptographically verified identities and role claims.",
            "reason": "Public identities cannot establish who performed a production review; using them would weaken the audit trail.",
        },
        "availability_monitoring": {
            "status": "observations_available" if probes else "awaiting_first_probe",
            "observation_count": len(probes),
            "passed_observations": passed,
            "observed_availability": round(passed / len(probes), 4) if probes else None,
            "latest": probes[-1] if probes else None,
            "claim_boundary": "External API reachability only; not reviewer decision SLA and not an SLA commitment.",
            "minimum_observations_for_reporting": 28,
            "reporting_eligible": len(probes) >= 28,
        },
        "answer": {
            "real_public_ads": "available with scope limits",
            "independent_public_labels": "available as opinion/research labels, not enforcement truth",
            "formal_identity": "must be deployment-owned; no safe public substitute",
            "production_sla": "must be observed from this deployment; public monitor now records reachability only",
        },
    }
