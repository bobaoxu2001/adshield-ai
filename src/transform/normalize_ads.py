from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import settings

COLUMNS = [
    "ad_id", "case_id", "ad_text", "advertiser_id", "advertiser_name", "created_at",
    "delivery_start", "delivery_stop", "platforms", "ad_snapshot_url", "country",
    "ad_type", "keyword", "languages", "eu_total_reach", "source", "source_url", "retrieved_at",
]

CREATIVE_FIELDS = ("ad_creative_bodies", "ad_creative_link_titles", "ad_creative_link_descriptions", "ad_creative_link_captions")


def _query_context(payload: dict[str, Any], stem: str) -> dict[str, str | None]:
    """Country/ad_type/keyword come from the saved `_query` block, falling back to the filename."""
    ctx = payload.get("_query") or {}
    if ctx:
        return {"country": ctx.get("country"), "ad_type": ctx.get("ad_type"), "keyword": ctx.get("keyword")}
    parts = stem.split("__")
    if len(parts) >= 3:
        return {"country": parts[0], "ad_type": parts[1], "keyword": parts[2]}
    return {"country": None, "ad_type": None, "keyword": None}


def _creative_text(ad: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in CREATIVE_FIELDS:
        parts.extend(ad.get(field) or [])
    return " ".join(dict.fromkeys(str(part).strip() for part in parts if str(part).strip()))


def normalize_ads(raw_dir: Path | None = None, processed_dir: Path | None = None) -> pd.DataFrame:
    """Normalize real Meta Ad Library responses into a tabular ads frame.

    Only `data` entries from saved API responses are read. When no token was supplied,
    the raw run holds a skipped manifest with no `data`, so this returns an empty frame
    with the full schema rather than fabricating any ad records. Records with no creative
    text are dropped (never replaced by placeholders), and ads are de-duplicated by ad_id.
    """
    raw_dir = raw_dir or settings.raw_dir
    processed_dir = processed_dir or settings.processed_dir
    rows: list[dict[str, object]] = []
    runs = sorted(path for path in (raw_dir / "meta_ads").glob("*") if path.is_dir())
    selected_run = runs[-1] if runs else None
    manifest: dict[str, Any] = {}
    if selected_run and (selected_run / "manifest.json").exists():
        manifest = json.loads((selected_run / "manifest.json").read_text(encoding="utf-8"))
    paths = sorted(selected_run.glob("*.json")) if selected_run else []
    for path in paths:
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        retrieved_at = manifest.get("retrieved_at") or datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
        ctx = _query_context(payload, path.stem)
        for ad in payload.get("data", []):
            text = _creative_text(ad)
            if not text:  # drop empty creatives; do not fabricate
                continue
            ad_id = str(ad.get("id", ""))
            rows.append({
                "ad_id": ad_id,
                "case_id": f"meta-{ad_id}",
                "ad_text": text,
                "advertiser_id": str(ad.get("page_id", "")),
                "advertiser_name": str(ad.get("page_name", "")),
                "created_at": ad.get("ad_creation_time") or retrieved_at,
                "delivery_start": ad.get("ad_delivery_start_time"),
                "delivery_stop": ad.get("ad_delivery_stop_time"),
                "platforms": json.dumps(ad.get("publisher_platforms") or []),
                "ad_snapshot_url": ad.get("ad_snapshot_url"),
                "country": ctx.get("country"),
                "ad_type": ctx.get("ad_type"),
                "keyword": ctx.get("keyword"),
                "languages": json.dumps(ad.get("languages") or []),
                "eu_total_reach": ad.get("eu_total_reach"),
                "source": "Meta Ad Library API",
                "source_url": "https://www.facebook.com/ads/library/",
                "retrieved_at": retrieved_at,
            })
    frame = pd.DataFrame(rows, columns=COLUMNS).drop_duplicates("ad_id") if rows else pd.DataFrame(columns=COLUMNS)
    processed_dir.mkdir(parents=True, exist_ok=True)
    out = processed_dir / "ads.parquet"
    frame.to_parquet(out, index=False)
    print(f"Meta: normalized {len(frame)} ads to {out}")
    return frame


if __name__ == "__main__":
    normalize_ads()
