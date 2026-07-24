from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from src.config import settings
from src.ingest.common import timestamp, write_manifest

KEYWORDS = [
    "financial scam", "loan", "investment", "crypto", "weight loss", "supplement",
    "pharmacy", "immigration", "job offer", "gambling", "AI tool", "miracle cure",
    "debt relief", "credit repair",
]

# Fields available across most ad types and regions.
CORE_FIELDS = [
    "id", "ad_creation_time", "ad_creative_bodies", "ad_creative_link_captions",
    "ad_creative_link_descriptions", "ad_creative_link_titles", "ad_snapshot_url",
    "page_id", "page_name", "publisher_platforms",
    "ad_delivery_start_time", "ad_delivery_stop_time",
]
# Fields that only exist for some ad types / EU-transparency ads; requested best-effort
# and dropped automatically if the API reports them as unsupported for a given query.
EXTRA_FIELDS = ["languages", "eu_total_reach"]


class MetaQueryError(RuntimeError):
    """A single (country, ad_type, keyword) query failed; recorded, then skipped."""


def _scrub(text: str) -> str:
    """Remove the access token from any string before it is printed or persisted."""
    token = settings.meta_access_token
    if token:
        text = text.replace(token, "***")
    return re.sub(r"access_token=[^&\s]+", "access_token=***", text)


def _sanitize(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower()
    return cleaned or "x"


def _error_message(payload: dict[str, Any]) -> str:
    err = payload.get("error", {})
    return f"{err.get('message', 'unknown error')} (code {err.get('code')}, subcode {err.get('error_subcode')})"


def _is_field_error(payload: dict[str, Any]) -> bool:
    return "field" in str(payload.get("error", {}).get("message", "")).lower()


def likely_fix(message: str) -> str:
    low = message.lower()
    if "code 190" in low or "access token" in low or "expired" in low or "session" in low:
        return "Token invalid or expired — regenerate it in Graph API Explorer and update .env."
    if "identity" in low or "confirm your" in low:
        return "Complete Meta identity confirmation for the Ad Library, then retry."
    if any(code in low for code in ("code 4)", "code 17)", "code 32)", "code 613")) or "rate" in low:
        return "Rate limited — wait a few minutes, re-run, or lower META_MAX_PAGES_PER_QUERY."
    if "permission" in low or "code 10)" in low or "code 200)" in low:
        return "Token/app lacks Ad Library access — confirm ads_archive permission on the token."
    if "ad_type" in low or "not available" in low or "not supported" in low or "country" in low:
        return "This ad_type may be unavailable in this country — ALL is the safe fallback."
    if "field" in low:
        return "An unsupported field was requested; the fetcher already retries with core fields."
    return "See https://www.facebook.com/ads/library/api/ and verify token scope, ad_type, and country."


def _request(url: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """GET the API and return parsed JSON. Errors are sanitized of any token before raising."""
    try:
        response = requests.get(url, params=params, timeout=60)
    except requests.RequestException as exc:
        raise MetaQueryError(f"network error: {type(exc).__name__}") from None
    try:
        return response.json()
    except ValueError:
        raise MetaQueryError(f"non-JSON response (HTTP {response.status_code})") from None


def _nonempty_creative(ad: dict[str, Any]) -> bool:
    for field in ("ad_creative_bodies", "ad_creative_link_titles", "ad_creative_link_descriptions", "ad_creative_link_captions"):
        if any(str(part).strip() for part in (ad.get(field) or [])):
            return True
    return False


def _save_page(out: Path, country: str, ad_type: str, keyword: str, page: int, data: list[dict[str, Any]], paging: dict[str, Any]) -> None:
    # The verbatim Meta `data` array is preserved alongside a small query annotation.
    # The paging `next` URL carries the access token and is deliberately NOT persisted.
    wrapper = {
        "_query": {"country": country, "ad_type": ad_type, "keyword": keyword, "page": page},
        "data": data,
        "page_info": {"has_next": bool(paging.get("next")), "returned": len(data)},
    }
    fname = f"{country}__{ad_type}__{_sanitize(keyword)}__p{page}.json"
    (out / fname).write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_query(out: Path, endpoint: str, country: str, ad_type: str, keyword: str) -> tuple[int, int, int]:
    """Fetch one query, following pagination up to META_MAX_PAGES_PER_QUERY. Returns (records, nonempty, pages)."""
    base_params = {
        "access_token": settings.meta_access_token,
        "ad_reached_countries": json.dumps([country]),
        "ad_type": ad_type,
        "search_terms": keyword,
        "limit": 100,
    }
    fields_param = ",".join(CORE_FIELDS + EXTRA_FIELDS)
    records = nonempty = pages = 0
    next_url: str | None = None
    for page in range(1, max(1, settings.meta_max_pages_per_query) + 1):
        if next_url:
            payload = _request(next_url, None)
        else:
            payload = _request(endpoint, {**base_params, "fields": fields_param})
            if "error" in payload and _is_field_error(payload):
                fields_param = ",".join(CORE_FIELDS)  # retry once without optional fields
                payload = _request(endpoint, {**base_params, "fields": fields_param})
        if "error" in payload:
            raise MetaQueryError(_scrub(_error_message(payload)))
        data = payload.get("data", [])
        records += len(data)
        nonempty += sum(1 for ad in data if _nonempty_creative(ad))
        pages = page
        _save_page(out, country, ad_type, keyword, page, data, payload.get("paging", {}))
        next_url = payload.get("paging", {}).get("next")
        if not data or not next_url:
            break
    return records, nonempty, pages


def fetch_meta_ads() -> dict[str, Any]:
    out = settings.raw_dir / "meta_ads" / timestamp()
    out.mkdir(parents=True, exist_ok=True)
    countries = list(settings.meta_ad_countries)
    ad_types = list(settings.meta_ad_types)
    endpoint = f"https://graph.facebook.com/{settings.meta_graph_api_version}/ads_archive"

    if not settings.meta_access_token:
        manifest = {
            "source": "Meta Ad Library API",
            "endpoint": endpoint,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "status": "skipped_no_token",
            "total_records": 0,
            "total_nonempty_creatives": 0,
            "countries": countries,
            "ad_types": ad_types,
            "keywords": KEYWORDS,
            "per_query_counts": [],
            "failed_queries": [],
            "note": "Set META_ACCESS_TOKEN to enable official API enrichment; no fallback ads are fabricated.",
        }
        write_manifest(out, manifest)
        print("Meta: skipped (META_ACCESS_TOKEN is not set)")
        return manifest

    total_records = total_nonempty = 0
    per_query_counts: list[dict[str, Any]] = []
    failed_queries: list[dict[str, Any]] = []
    for country in countries:
        for ad_type in ad_types:
            for keyword in KEYWORDS:
                try:
                    records, nonempty, pages = _fetch_query(out, endpoint, country, ad_type, keyword)
                    total_records += records
                    total_nonempty += nonempty
                    per_query_counts.append({
                        "country": country, "ad_type": ad_type, "keyword": keyword,
                        "pages": pages, "records": records, "nonempty_creatives": nonempty,
                    })
                except MetaQueryError as exc:
                    message = _scrub(str(exc))
                    failed_queries.append({
                        "country": country, "ad_type": ad_type, "keyword": keyword,
                        "error": message, "likely_fix": likely_fix(message),
                    })

    status = "complete" if total_records else "complete_no_records"
    manifest: dict[str, Any] = {
        "source": "Official Meta Ad Library API",
        "endpoint": endpoint,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "status": status,
        "total_records": total_records,
        "total_nonempty_creatives": total_nonempty,
        "countries": countries,
        "ad_types": ad_types,
        "keywords": KEYWORDS,
        "per_query_counts": per_query_counts,
        "failed_queries": failed_queries,
    }
    if not total_records:
        manifest["warning"] = (
            "A token is set but the API returned 0 records across all queries. Verify the token has "
            "Ad Library access and identity confirmation is complete, and that the chosen ad_types are "
            "available in the chosen countries (ALL is the safe fallback). See failed_queries for details."
        )
        print(f"Meta: WARNING — 0 records returned across {len(per_query_counts) + len(failed_queries)} queries ({len(failed_queries)} failed). See manifest.")
    else:
        print(f"Meta: saved {total_records} real ads ({total_nonempty} with creative text) across {len(countries)} countries to {out}")
    write_manifest(out, manifest)
    return manifest


if __name__ == "__main__":
    fetch_meta_ads()
