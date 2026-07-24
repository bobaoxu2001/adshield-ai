from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

import requests

from src.config import settings
from src.ingest.common import sha256_bytes, timestamp, write_manifest

SOURCE_PAGE = "https://www.ftc.gov/reports/consumer-sentinel-network-data-book-2024"
DATA_URL = "https://www.ftc.gov/system/files/ftc_gov/data/csn-data-book-2024-csv.zip"


def fetch_ftc() -> dict[str, object]:
    run_id = timestamp()
    out = settings.raw_dir / "ftc" / run_id
    out.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AdShieldAI/1.0; public-interest research)",
        "Referer": SOURCE_PAGE,
    }
    response = requests.get(DATA_URL, headers=headers, timeout=60)
    response.raise_for_status()
    archive = out / "csn-data-book-2024-csv.zip"
    archive.write_bytes(response.content)
    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        bundle.extractall(out)
        files = [name for name in bundle.namelist() if name.lower().endswith(".csv")]
    manifest = {
        "source": "FTC Consumer Sentinel Network Data Book 2024",
        "source_page": SOURCE_PAGE,
        "download_url": DATA_URL,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "sha256": sha256_bytes(response.content),
        "archive": str(archive.relative_to(settings.root)),
        "csv_files": files,
        "record_granularity": "aggregated public statistics; not individual reports",
    }
    write_manifest(out, manifest)
    print(f"FTC: downloaded {len(files)} public CSV files to {out}")
    return manifest


if __name__ == "__main__":
    fetch_ftc()
