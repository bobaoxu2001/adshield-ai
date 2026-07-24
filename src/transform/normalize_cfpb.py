from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from src.config import settings
from src.transform.common import latest_run

TARGET_TERMS = ("credit", "debt", "payday", "mortgage", "card", "money", "virtual currency", "student loan", "bank")


def _column(frame: pd.DataFrame, *candidates: str, default: str = "") -> pd.Series:
    by_lower = {name.lower().replace(" ", "_"): name for name in frame.columns}
    for candidate in candidates:
        actual = by_lower.get(candidate.lower().replace(" ", "_"))
        if actual:
            return frame[actual].fillna(default).astype(str)
    return pd.Series([default] * len(frame), index=frame.index, dtype="object")


def normalize_cfpb() -> pd.DataFrame:
    run = latest_run(settings.raw_dir / "cfpb", "cfpb_complaints.csv")
    raw = pd.read_csv(run / "cfpb_complaints.csv", low_memory=False)
    product = _column(raw, "product")
    mask = product.str.lower().map(lambda value: any(term in value for term in TARGET_TERMS))
    raw = raw[mask].copy()
    product = product[mask]
    complaint_id = _column(raw, "complaint_id", "complaint id")
    issue = _column(raw, "issue")
    sub_issue = _column(raw, "sub_issue", "sub-issue")
    narrative = _column(raw, "consumer_narrative", "consumer complaint narrative")
    fallback_text = product + ". Issue: " + issue + ". Detail: " + sub_issue
    case_text = narrative.where(narrative.str.strip().ne(""), fallback_text).str.slice(0, 1800)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    frame = pd.DataFrame({
        "complaint_id": complaint_id,
        "case_id": "cfpb-" + complaint_id,
        "date_received": pd.to_datetime(_column(raw, "date_received", "date received"), errors="coerce"),
        "product": product,
        "sub_product": _column(raw, "sub_product", "sub-product"),
        "issue": issue,
        "sub_issue": sub_issue,
        "case_text": case_text,
        "has_public_narrative": narrative.str.strip().ne(""),
        "state": _column(raw, "state"),
        "submitted_via": _column(raw, "submitted_via", "submitted via"),
        "timely_response": _column(raw, "timely_response", "timely response?"),
        "source": "CFPB Consumer Complaint Database",
        "source_url": manifest["official_source_page"],
        "retrieval_path": manifest["retrieval_path"],
        "retrieved_at": manifest["retrieved_at"],
        "created_at": datetime.now(UTC).isoformat(),
    })
    frame = frame[frame["case_text"].str.strip().ne("")].drop_duplicates("case_id")
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    out = settings.processed_dir / "cfpb_complaints.parquet"
    frame.to_parquet(out, index=False)
    print(f"CFPB: normalized {len(frame)} finance-related public complaints to {out}")
    return frame


if __name__ == "__main__":
    normalize_cfpb()
