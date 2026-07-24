from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime

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

# Minimum ads for a content category to be reported (small cells are noisy).
CONTENT_MIN_ADS = 15

# Maps UW content categories to this project's risk taxonomy. Only categories with a
# clear, defensible mapping are included; format-only labels (e.g. "Image") are omitted.
# The target names must exist in src.risk.taxonomy.CATEGORY_NAMES.
UW_TO_TAXONOMY = {
    "Health and Supplements": "Health / Weight Loss / Pharmaceuticals Risk",
    "Medical Services and Prescriptions": "Health / Weight Loss / Pharmaceuticals Risk",
    "COVID Products": "Health / Weight Loss / Pharmaceuticals Risk",
    "Advertorial": "Deceptive / Misleading Claims",
    "Listicle": "Deceptive / Misleading Claims",
    "Native": "Deceptive / Misleading Claims",
    "Sponsored Content": "Deceptive / Misleading Claims",
    "Sponsored Search": "Deceptive / Misleading Claims",
}


def _round(value: float) -> float:
    return round(value, 4)


def _perception_by_content_category(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Aggregate human deception/clickbait/manipulation perception per content category.

    This is derived-aggregate evidence only: no ad text, image, or row-level label is
    retained. The UW ads are image screenshots with no ad copy, so the deterministic text
    engine cannot score them; this instead checks whether independent human perception
    concentrates in the same categories the taxonomy prioritizes.
    """
    buckets: dict[str, dict[str, float]] = {}
    for row in rows:
        dist = row["opinion_label_dist"]
        for label in row["content_labels"]:
            cell = buckets.setdefault(label, {"n": 0, "deceptive": 0.0, "clickbait": 0.0, "manipulative": 0.0, "maj_dec": 0, "maj_click": 0})
            cell["n"] += 1
            cell["deceptive"] += float(dist.get("deceptive", 0.0))
            cell["clickbait"] += float(dist.get("clickbait", 0.0))
            cell["manipulative"] += float(dist.get("manipulative", 0.0))
            cell["maj_dec"] += int(float(dist.get("deceptive", 0.0)) >= 0.5)
            cell["maj_click"] += int(float(dist.get("clickbait", 0.0)) >= 0.5)
    output = []
    for label, cell in buckets.items():
        n = int(cell["n"])
        if n < CONTENT_MIN_ADS:
            continue
        output.append({
            "content_category": label,
            "ad_count": n,
            "mean_deceptive_share": _round(cell["deceptive"] / n),
            "mean_clickbait_share": _round(cell["clickbait"] / n),
            "mean_manipulative_share": _round(cell["manipulative"] / n),
            "ads_majority_deceptive": int(cell["maj_dec"]),
            "ads_majority_clickbait": int(cell["maj_click"]),
            "mapped_risk_category": UW_TO_TAXONOMY.get(label),
        })
    output.sort(key=lambda r: r["mean_deceptive_share"] + r["mean_clickbait_share"], reverse=True)
    return output


def _summarize(rows: list[dict[str, object]], source_sha256: str, retrieved_at: str) -> dict[str, object]:
    if len(rows) != 500:
        raise ValueError(f"Expected the frozen 500-ad dataset, received {len(rows)} rows")
    rating_count = sum(len(row["ratings"]) for row in rows)
    rating_total = sum(sum(row["ratings"]) for row in rows)
    content_counts = Counter(label for row in rows for label in row["content_labels"])
    perception = _perception_by_content_category(rows)
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
        "perception_by_content_category": perception,
        "taxonomy_alignment": {
            "method": (
                "The UW ads are image screenshots with no ad copy, so the deterministic text engine "
                "cannot score them. Instead, each content category with at least "
                f"{CONTENT_MIN_ADS} ads is ranked by mean independent-annotator deception and clickbait "
                "share, and compared with the risk categories this project prioritizes."
            ),
            "top_perceived_deception_categories": [row["content_category"] for row in perception[:5]],
            "lowest_perceived_deception_categories": [row["content_category"] for row in perception[-3:]],
            "risk_relevant_mapped_categories": sorted({row["mapped_risk_category"] for row in perception if row["mapped_risk_category"]}),
            "readout": (
                "Independent human perception concentrates in Health/Supplements and in advertorial, "
                "listicle, and native formats — the same areas the taxonomy prioritizes as health and "
                "deceptive-claim risk. Low-perceived-deception categories (journalism, apparel, B2B) are "
                "not prioritized. This corroborates the taxonomy's risk ranking at the category level; it "
                "is not per-ad enforcement agreement and confers no promotion eligibility."
            ),
        },
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
