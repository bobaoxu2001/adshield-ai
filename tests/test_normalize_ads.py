import json

import pandas as pd

from src.transform.normalize_ads import COLUMNS, normalize_ads


def _write_run(raw_dir, name: str, payload: dict) -> None:
    run = raw_dir / "meta_ads" / "20260101T000000Z"
    run.mkdir(parents=True, exist_ok=True)
    (run / name).write_text(json.dumps(payload), encoding="utf-8")


def test_empty_table_when_meta_token_absent(tmp_path) -> None:
    """A skipped (no-token) run yields an empty ads table and never fabricates ads."""
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    _write_run(raw_dir, "manifest.json", {"status": "skipped_no_token", "total_records": 0})

    frame = normalize_ads(raw_dir=raw_dir, processed_dir=processed_dir)

    assert frame.empty
    assert list(frame.columns) == COLUMNS
    saved = pd.read_parquet(processed_dir / "ads.parquet")
    assert saved.empty
    assert list(saved.columns) == COLUMNS


def test_real_ads_are_normalized_with_context_and_no_fabrication(tmp_path) -> None:
    """Real `data` is normalized with query context; empty creatives are dropped, not replaced."""
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    _write_run(raw_dir, "manifest.json", {"status": "complete", "total_records": 2})
    _write_run(raw_dir, "GB__ALL__loan__p1.json", {
        "_query": {"country": "GB", "ad_type": "ALL", "keyword": "loan", "page": 1},
        "data": [
            {
                "id": "123", "page_id": "p1", "page_name": "Acme",
                "ad_creative_bodies": ["Guaranteed loan, no credit check"],
                "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=123",
                "languages": ["en"], "eu_total_reach": 12000,
            },
            {"id": "456", "page_id": "p2", "page_name": "Empty Co", "ad_creative_bodies": ["   "]},  # dropped
        ],
    })

    frame = normalize_ads(raw_dir=raw_dir, processed_dir=processed_dir)

    assert len(frame) == 1  # empty-text ad dropped, not replaced by a placeholder
    row = frame.iloc[0]
    assert row["ad_id"] == "123"
    assert row["case_id"] == "meta-123"
    assert "Guaranteed loan" in row["ad_text"]
    assert row["country"] == "GB"
    assert row["ad_type"] == "ALL"
    assert row["keyword"] == "loan"
    assert row["ad_snapshot_url"].endswith("id=123")
    assert row["eu_total_reach"] == 12000
    assert json.loads(row["languages"]) == ["en"]
    assert row["source"] == "Meta Ad Library API"


def test_dedupes_by_ad_id(tmp_path) -> None:
    """The same ad returned under two queries collapses to a single row."""
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    ad = {"id": "789", "page_name": "DupeCo", "ad_creative_bodies": ["crypto doubling scheme"]}
    _write_run(raw_dir, "GB__ALL__crypto__p1.json", {"_query": {"country": "GB", "ad_type": "ALL", "keyword": "crypto"}, "data": [ad]})
    _write_run(raw_dir, "IE__ALL__crypto__p1.json", {"_query": {"country": "IE", "ad_type": "ALL", "keyword": "crypto"}, "data": [ad]})

    frame = normalize_ads(raw_dir=raw_dir, processed_dir=processed_dir)

    assert list(frame["ad_id"]) == ["789"]


def test_only_latest_meta_run_is_normalized(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    old = raw_dir / "meta_ads" / "20260101T000000Z"
    new = raw_dir / "meta_ads" / "20260102T000000Z"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "manifest.json").write_text(json.dumps({"retrieved_at": "2026-01-01T00:00:00+00:00"}))
    (new / "manifest.json").write_text(json.dumps({"retrieved_at": "2026-01-02T00:00:00+00:00"}))
    (old / "GB__ALL__loan__p1.json").write_text(json.dumps({"data": [{"id": "old", "ad_creative_bodies": ["old loan"]}]}))
    (new / "GB__ALL__loan__p1.json").write_text(json.dumps({"data": [{"id": "new", "ad_creative_bodies": ["new loan"]}]}))
    frame = normalize_ads(raw_dir=raw_dir, processed_dir=processed_dir)
    assert list(frame["ad_id"]) == ["new"]
    assert frame.iloc[0]["retrieved_at"] == "2026-01-02T00:00:00+00:00"
