from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from src.config import settings
from src.transform.common import latest_run, number


def normalize_ftc() -> pd.DataFrame:
    run = latest_run(settings.raw_dir / "ftc")
    csv_dir = run / "CSVs"
    category_file = next(csv_dir.glob("*_CSN_Report_Categories.csv"))
    state_file = next(csv_dir.glob("*_CSN_State_Fraud_Reports_and_Losses.csv"))

    categories = pd.read_csv(category_file, skiprows=2, encoding="cp1252")
    categories = categories[categories["Category"].notna()].copy()
    category_rows = pd.DataFrame({
        "record_id": "ftc-category-" + categories["Rank"].astype(str),
        "granularity": "category",
        "category": categories["Category"].astype(str).str.strip(),
        "state": None,
        "report_count": categories[" # of Reports "].map(number).astype("Int64"),
        "percent_reporting_loss": None,
        "total_loss_usd": None,
        "median_loss_usd": None,
    })

    states = pd.read_csv(state_file, skiprows=2, encoding="cp1252")
    states = states[states["State"].notna()].copy()
    state_rows = pd.DataFrame({
        "record_id": "ftc-state-" + states["State"].astype(str).str.lower().str.replace(r"\W+", "-", regex=True),
        "granularity": "state",
        "category": "All fraud reports",
        "state": states["State"].astype(str).str.strip(),
        "report_count": states["# of Reports"].map(number).astype("Int64"),
        "percent_reporting_loss": states["% Reporting $ Loss"].map(number),
        "total_loss_usd": states["Total $ Loss"].map(number),
        "median_loss_usd": states["Median $ Loss"].map(number),
    })
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    frame = pd.concat([category_rows, state_rows], ignore_index=True)
    frame["data_year"] = 2024
    frame["source"] = "FTC Consumer Sentinel Network Data Book 2024"
    frame["source_url"] = manifest["source_page"]
    frame["retrieved_at"] = manifest["retrieved_at"]
    frame["created_at"] = datetime.now(UTC).isoformat()
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    out = settings.processed_dir / "ftc_fraud_reports.parquet"
    frame.to_parquet(out, index=False)
    print(f"FTC: normalized {len(frame)} aggregate rows to {out}")
    return frame


if __name__ == "__main__":
    normalize_ftc()
