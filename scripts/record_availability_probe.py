from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _get(url: str) -> dict[str, object]:
    started = time.perf_counter()
    request = Request(url, headers={"User-Agent": "AdShieldAI-Public-Monitor/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = response.status
        error = None
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        payload = None
        status = getattr(exc, "code", None)
        error = f"{type(exc).__name__}: {exc}"
    return {
        "url": url,
        "http_status": status,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "json": payload,
        "error": error,
    }


def record_probe(base_url: str, output: Path) -> dict[str, object]:
    base = base_url.rstrip("/")
    checks = [_get(f"{base}{path}") for path in ("/api/health", "/api/benchmark-lab", "/api/public-evidence")]
    passed = (
        all(item["http_status"] == 200 for item in checks)
        and checks[0]["json"].get("status") == "ok"
        and checks[0]["json"].get("database_ready") is True
        and checks[1]["json"].get("promotion_gate", {}).get("status") == "eligible_for_review"
        and checks[2]["json"].get("uw_summary", {}).get("ad_records") == 500
    )
    observation = {
        "checked_at": datetime.now(UTC).isoformat(),
        "target": base,
        "passed": passed,
        "checks": [
            {
                "url": item["url"],
                "http_status": item["http_status"],
                "latency_ms": item["latency_ms"],
                "error": item["error"],
            }
            for item in checks
        ],
    }
    history = {"measurement_scope": "external_api_reachability", "observations": []}
    if output.exists():
        history = json.loads(output.read_text(encoding="utf-8"))
    history["observations"] = [*history.get("observations", []), observation][-1000:]
    history["claim_boundary"] = "Public endpoint reachability; not reviewer decision SLA and not a contractual availability SLA."
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return observation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    observation = record_probe(args.url, args.output)
    print(json.dumps(observation, indent=2))
    if not observation["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
