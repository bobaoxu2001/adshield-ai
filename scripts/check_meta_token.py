#!/usr/bin/env python
"""Local Meta Ad Library token check.

Runs ONE small, safe query against the official Meta Ad Library API so you can confirm
your token works before a full ingest. It reads META_ACCESS_TOKEN from your local .env
and NEVER prints, logs, or persists the token (error text is scrubbed of it as well).

Usage:
    make check-meta-token        # or:  python scripts/check_meta_token.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

# Make `src` importable when run as a plain script (python scripts/check_meta_token.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import settings  # noqa: E402
from src.ingest.fetch_meta_ads import likely_fix  # noqa: E402

COUNTRY = "GB"
AD_TYPE = "FINANCIAL_PRODUCTS_AND_SERVICES_ADS"
SEARCH_TERMS = "loan"
FIELDS = [
    "id", "page_id", "page_name", "ad_creative_bodies", "ad_creative_link_titles",
    "ad_snapshot_url", "ad_delivery_start_time", "ad_delivery_stop_time",
]


def _scrub(text: str) -> str:
    token = settings.meta_access_token
    if token:
        text = text.replace(token, "***")
    return re.sub(r"access_token=[^&\s]+", "access_token=***", text)


def _nonempty(ad: dict) -> bool:
    for field in ("ad_creative_bodies", "ad_creative_link_titles"):
        if any(str(part).strip() for part in (ad.get(field) or [])):
            return True
    return False


def _excerpt(ad: dict) -> str:
    for field in ("ad_creative_bodies", "ad_creative_link_titles"):
        values = ad.get(field) or []
        if values and str(values[0]).strip():
            text = " ".join(str(values[0]).split())
            return text[:120] + "…" if len(text) > 120 else text
    return "(no creative text)"


def main() -> int:
    if not settings.meta_access_token:
        print("No META_ACCESS_TOKEN found in your environment/.env.")
        print("Fix: copy .env.example to .env, paste your token into META_ACCESS_TOKEN, then re-run.")
        return 1

    endpoint = f"https://graph.facebook.com/{settings.meta_graph_api_version}/ads_archive"
    params = {
        "access_token": settings.meta_access_token,
        "ad_reached_countries": json.dumps([COUNTRY]),
        "ad_type": AD_TYPE,
        "search_terms": SEARCH_TERMS,
        "fields": ",".join(FIELDS),
        "limit": 10,
    }
    print(f"Testing Meta Ad Library API — country={COUNTRY}, ad_type={AD_TYPE}, search_terms='{SEARCH_TERMS}' (token hidden).")

    try:
        response = requests.get(endpoint, params=params, timeout=60)
    except requests.RequestException as exc:
        print(f"Request succeeded: no — network error ({type(exc).__name__}).")
        print("Fix: check your internet connection and retry.")
        return 1

    try:
        payload = response.json()
    except ValueError:
        print(f"Request succeeded: no — non-JSON response (HTTP {response.status_code}).")
        return 1

    if "error" in payload:
        err = payload["error"]
        message = _scrub(str(err.get("message", "unknown error")))
        print(f"Request succeeded: no — API error (HTTP {response.status_code}).")
        print(f"  Message: {message} [code {err.get('code')}, subcode {err.get('error_subcode')}]")
        print(f"  Likely fix: {likely_fix(message)}")
        return 1

    data = payload.get("data", [])
    nonempty = [ad for ad in data if _nonempty(ad)]
    print("Request succeeded: yes")
    print(f"Records returned: {len(data)}")
    print(f"Records with non-empty creative text: {len(nonempty)}")
    if data:
        print("First 3 results:")
        for ad in data[:3]:
            print(f"  - id={ad.get('id')} | page='{ad.get('page_name')}' | text='{_excerpt(ad)}'")
    else:
        print("Note: 0 records is not necessarily an error for this narrow query.")
        print("Try AD_TYPE=ALL or a different country (e.g. set META_AD_TYPES/META_AD_COUNTRIES) before a full ingest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
