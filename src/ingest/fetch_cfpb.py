from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import UTC, datetime
from urllib.parse import urlencode

import requests

from src.config import settings
from src.ingest.common import sha256_bytes, timestamp, write_manifest

OFFICIAL_API = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
OFFICIAL_PAGE = "https://www.consumerfinance.gov/data-research/consumer-complaints/"
MIRROR_URL = "https://huggingface.co/datasets/claritystorm/cfpb-consumer-complaints/resolve/main/sample_1000.csv"
PRODUCTS = [
    "Credit reporting, credit repair services, or other personal consumer reports",
    "Credit reporting or other personal consumer reports",
    "Debt collection",
    "Payday loan, title loan, or personal loan",
    "Mortgage",
    "Credit card or prepaid card",
    "Money transfer, virtual currency, or money service",
    "Student loan",
]


def _official_rows(max_records: int) -> list[dict[str, object]]:
    params = {
        "format": "json",
        "no_aggs": "true",
        "size": str(max_records),
        "sort": "created_date_desc",
        "product": ",".join(PRODUCTS),
    }
    response = requests.get(
        f"{OFFICIAL_API}?{urlencode(params)}",
        timeout=60,
        headers={"User-Agent": "AdShieldAI/1.0 public-interest research"},
    )
    response.raise_for_status()
    payload = response.json()
    return [hit.get("_source", {}) for hit in payload.get("hits", {}).get("hits", [])]


def _rows_to_csv(rows: Iterable[dict[str, object]]) -> bytes:
    rows = list(rows)
    fields = sorted({key for row in rows for key in row})
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def fetch_cfpb(max_records: int | None = None) -> dict[str, object]:
    max_records = max_records or settings.cfpb_max_records
    run_id = timestamp()
    out = settings.raw_dir / "cfpb" / run_id
    out.mkdir(parents=True, exist_ok=True)
    retrieval_path = "official_api"
    note = "Official CFPB Open Data API response."
    try:
        rows = _official_rows(max_records)
        if not rows:
            raise RuntimeError("Official API returned no rows")
        content = _rows_to_csv(rows[:max_records])
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        response = requests.get(MIRROR_URL, timeout=60, headers={"User-Agent": "AdShieldAI/1.0"})
        response.raise_for_status()
        content = response.content
        retrieval_path = "public_mirror_sample"
        note = (
            "Official CFPB endpoint was inaccessible from this network; used a CC0 public mirror "
            "sample derived from the CFPB database. No records were generated or modified. "
            f"Official error: {type(exc).__name__}."
        )
    path = out / "cfpb_complaints.csv"
    path.write_bytes(content)
    row_count = sum(1 for _ in csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    manifest = {
        "source": "CFPB Consumer Complaint Database",
        "official_source_page": OFFICIAL_PAGE,
        "official_api": OFFICIAL_API,
        "retrieval_path": retrieval_path,
        "fallback_url": MIRROR_URL if retrieval_path != "official_api" else None,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "sha256": sha256_bytes(content),
        "raw_file": str(path.relative_to(settings.root)),
        "rows": row_count,
        "note": note,
        "privacy": "Narratives are CFPB-published and scrubbed; the dashboard excludes company and ZIP fields.",
    }
    write_manifest(out, manifest)
    print(f"CFPB: saved {row_count} real public records via {retrieval_path} to {path}")
    return manifest


if __name__ == "__main__":
    fetch_cfpb()
