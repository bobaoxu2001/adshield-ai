from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _db_path() -> Path:
    configured = os.getenv("ADSHIELD_DB_PATH")
    if configured:
        return ROOT / configured
    local = ROOT / "data" / "processed" / "adshield.duckdb"
    deploy = ROOT / "data" / "deploy" / "adshield.duckdb"
    return local if local.exists() else deploy


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    """Parse a comma-separated env var into an upper-cased, de-blanked tuple."""
    return tuple(part.strip().upper() for part in os.getenv(name, default).split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    raw_dir: Path = ROOT / "data" / "raw"
    processed_dir: Path = ROOT / "data" / "processed"
    policy_dir: Path = ROOT / "data" / "policies"
    db_path: Path = _db_path()
    public_demo: bool = bool(os.getenv("VERCEL"))
    feedback_writable: bool = not bool(os.getenv("VERCEL"))
    meta_access_token: str | None = os.getenv("META_ACCESS_TOKEN") or None
    meta_graph_api_version: str = os.getenv("META_GRAPH_API_VERSION", "v23.0")
    meta_ad_countries: tuple[str, ...] = _csv_env("META_AD_COUNTRIES", "GB,IE,FR,DE,NL,ES,IT")
    meta_ad_types: tuple[str, ...] = _csv_env("META_AD_TYPES", "FINANCIAL_PRODUCTS_AND_SERVICES_ADS,EMPLOYMENT_ADS,HOUSING_ADS,ALL")
    meta_max_pages_per_query: int = int(os.getenv("META_MAX_PAGES_PER_QUERY", "3"))
    tiktok_research_access_token: str | None = os.getenv("TIKTOK_RESEARCH_ACCESS_TOKEN") or None
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    cfpb_max_records: int = int(os.getenv("CFPB_MAX_RECORDS", "1000"))


settings = Settings()
