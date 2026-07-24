from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import requests

from src.config import settings
from src.ingest.common import timestamp, write_manifest

QUERY_ENDPOINT = "https://open.tiktokapis.com/v2/research/adlib/ad/query/"
DETAIL_ENDPOINT = "https://open.tiktokapis.com/v2/research/adlib/ad/detail/"
DOCUMENTATION = "https://developers.tiktok.com/doc/commercial-content-api-query-ads"
FIELDS = (
    "ad.id,ad.first_shown_date,ad.last_shown_date,ad.status,ad.status_statement,"
    "ad.videos,ad.image_urls,ad.reach,advertiser.business_id,advertiser.business_name,"
    "advertiser.paid_for_by"
)


def _request(token: str, body: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        QUERY_ENDPOINT,
        params={"fields": FIELDS},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    error = payload.get("error") or {}
    if error.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok Commercial Content API error: {error.get('message') or error.get('code')}")
    return payload


def fetch_tiktok_commercial_ads(
    *,
    country_code: str = "FR",
    search_term: str = "financial services",
    start_date: date | None = None,
    end_date: date | None = None,
    max_pages: int = 3,
) -> dict[str, object]:
    out = settings.raw_dir / "tiktok_commercial_ads" / timestamp()
    out.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).isoformat()
    token = settings.tiktok_research_access_token
    start = start_date or date.today() - timedelta(days=30)
    end = end_date or date.today()
    if not token:
        manifest = {
            "source": "TikTok Commercial Content API",
            "endpoint": QUERY_ENDPOINT,
            "documentation": DOCUMENTATION,
            "retrieved_at": retrieved_at,
            "status": "skipped_approval_token_required",
            "record_count": 0,
            "required_scope": "research.adlib.basic",
            "truth_boundary": "No TikTok records are substituted when approved research access is absent.",
        }
        write_manifest(out, manifest)
        print("TikTok Commercial Content API: skipped (approved research token is not configured)")
        return manifest

    body: dict[str, Any] = {
        "filters": {
            "ad_published_date_range": {"min": start.strftime("%Y%m%d"), "max": end.strftime("%Y%m%d")},
            "country_code": country_code.upper(),
        },
        "search_term": search_term[:50],
        "search_type": "fuzzy_phrase",
        "max_count": 50,
    }
    records: list[dict[str, Any]] = []
    pages = 0
    for page in range(1, max(1, max_pages) + 1):
        payload = _request(token, body)
        data = payload.get("data") or {}
        page_rows = data.get("ads") or []
        records.extend(page_rows)
        pages = page
        (out / f"page-{page}.json").write_text(json.dumps({"data": {"ads": page_rows}}, ensure_ascii=False, indent=2), encoding="utf-8")
        if not data.get("has_more") or not data.get("search_id"):
            break
        body["search_id"] = data["search_id"]

    manifest = {
        "source": "Official TikTok Commercial Content API",
        "endpoint": QUERY_ENDPOINT,
        "documentation": DOCUMENTATION,
        "retrieved_at": retrieved_at,
        "status": "complete" if records else "complete_no_records",
        "record_count": len(records),
        "pages": pages,
        "country_code": country_code.upper(),
        "search_term": search_term[:50],
        "date_range": {"min": start.isoformat(), "max": end.isoformat()},
        "required_scope": "research.adlib.basic",
    }
    write_manifest(out, manifest)
    print(f"TikTok Commercial Content API: saved {len(records)} public ad records to {out}")
    return manifest


if __name__ == "__main__":
    fetch_tiktok_commercial_ads()
