from __future__ import annotations

from pathlib import Path


def latest_run(root: Path, required: str | None = None) -> Path:
    runs = sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []
    if required:
        runs = [path for path in runs if (path / required).exists()]
    if not runs:
        raise FileNotFoundError(f"No ingestion run found under {root}. Run `make ingest` first.")
    return runs[-1]


def number(value: object) -> float | None:
    if value is None:
        return None
    cleaned = str(value).replace(",", "").replace("$", "").replace("%", "").replace("M", "000000").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None
