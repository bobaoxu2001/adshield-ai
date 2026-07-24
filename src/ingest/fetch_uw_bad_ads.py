from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import requests

from src.config import settings
from src.ingest.common import timestamp, write_manifest

SOURCE_NAME = "UW CHI 2021 Ad Perceptions Dataset"
SOURCE_PAGE = "https://badads.cs.washington.edu/datasets.html"
REPOSITORY = "https://github.com/eric-zeng/chi-bad-ads-data"
SOURCE_COMMIT = "9dd424e1ed4ec6a781d25f0d4a3ba97fbe3c3e40"
DATA_URL = (
    "https://raw.githubusercontent.com/eric-zeng/chi-bad-ads-data/"
    f"{SOURCE_COMMIT}/data/ads_all_labels.json"
)
OPINION_LABELS = ("deceptive", "clickbait", "manipulative", "trustworthy", "unclear", "distasteful")


def _round(value: float) -> float:
    return round(value, 4)


def _summarize(rows: list[dict[str, object]], source_sha256: str, retrieved_at: str) -> dict[str, object]:
    if len(rows) != 500:
        raise ValueError(f"Expected the frozen 500-ad dataset, received {len(rows)} rows")
    rating_count = sum(len(row["ratings"]) for row in rows)
    rating_total = sum(sum(row["ratings"]) for row in rows)
    content_counts = Counter(label for row in rows for label in row["content_labels"])
    opinions: dict[str, dict[str, object]] = {}
    for label in OPINION_LABELS:
        values = [float(row["opinion_label_dist"][label]) for row in rows]
        opinions[label] = {
            "mean_annotator_share": _round(sum(values) / len(values)),
            "ads_with_any_label": sum(value > 0 for value in values),
            "ads_with_majority_label": sum(value >= 0.5 for value in values),
            "majority_threshold": ">= 50% of an ad's annotators",
        }
    return {
        "dataset_id": "uw-chi-2021-ad-perceptions",
        "source_name": SOURCE_NAME,
        "source_page": SOURCE_PAGE,
        "repository": REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "source_sha256": source_sha256,
        "retrieved_at": retrieved_at,
        "data_scope": "external_independent_validation",
        "integration_status": "aggregate_evidence_loaded",
        "ad_records": len(rows),
        "reported_unique_annotators": 1025,
        "rating_observations": rating_count,
        "annotators_per_ad": {
            "minimum": min(len(row["ratings"]) for row in rows),
            "maximum": max(len(row["ratings"]) for row in rows),
            "mean": _round(rating_count / len(rows)),
        },
        "mean_overall_rating_1_to_7": _round(rating_total / rating_count),
        "opinion_label_summary": opinions,
        "top_content_labels": [
            {"label": label, "ad_count": count} for label, count in content_counts.most_common(12)
        ],
        "truth_boundary": (
            "Independent participant opinions about real web ads; not platform enforcement decisions, "
            "policy-violation ground truth, TikTok ads, or production precision/recall evidence."
        ),
        "redistribution_boundary": (
            "Only derived aggregate statistics are tracked here. Ad images, participant comments, "
            "participant context, and row-level labels remain at the cited source."
        ),
        "license_note": (
            "The public research repository requests citation but exposes no separate license file at "
            "the pinned commit; this project therefore avoids redistributing source media or raw responses."
        ),
        "promotion_gate_effect": "informative_only",
    }


def fetch_uw_bad_ads() -> dict[str, object]:
    retrieved_at = datetime.now(UTC).isoformat()
    response = requests.get(DATA_URL, timeout=120)
    response.raise_for_status()
    payload = response.content
    rows = response.json()
    if not isinstance(rows, list):
        raise TypeError("UW source payload must be a list")
    source_sha256 = hashlib.sha256(payload).hexdigest()
    summary = _summarize(rows, source_sha256, retrieved_at)

    raw_out = settings.raw_dir / "uw_bad_ads" / timestamp()
    raw_out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": SOURCE_NAME,
        "source_page": SOURCE_PAGE,
        "download_url": DATA_URL,
        "source_commit": SOURCE_COMMIT,
        "retrieved_at": retrieved_at,
        "sha256": source_sha256,
        "record_count": len(rows),
        "raw_payload_persisted": False,
        "reason": "Aggregate-only reuse; no source media, comments, participant context, or row-level labels are redistributed.",
    }
    write_manifest(raw_out, manifest)

    public_out = settings.root / "data" / "public_validation"
    public_out.mkdir(parents=True, exist_ok=True)
    destination = public_out / "uw_bad_ads_summary.json"
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"UW Bad Ads: verified {len(rows)} public ads and wrote aggregate evidence to {destination}")
    return summary


if __name__ == "__main__":
    fetch_uw_bad_ads()
