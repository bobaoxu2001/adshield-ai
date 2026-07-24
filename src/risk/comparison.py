from __future__ import annotations

import json
import time
import duckdb

from src.config import settings
from src.risk.llm_evaluator import evaluate_with_openai, llm_available

# Fields compared side by side between the deterministic engine and the optional LLM.
_DETERMINISTIC_FIELDS = ("risk_category", "risk_score", "severity", "recommended_action", "confidence")

_SAMPLE_SQL = """
    WITH case_texts AS (
      SELECT case_id, case_text, product FROM cfpb_complaints
      UNION ALL
      SELECT case_id, ad_text, 'commercial advertisement' FROM ads
    )
    SELECT s.case_id, s.source, s.language, s.risk_category, s.risk_score, s.severity,
           s.recommended_action, s.confidence, s.evidence_json, c.case_text, c.product
    FROM ad_risk_scores s JOIN case_texts c USING (case_id)
    ORDER BY s.risk_score DESC, s.case_id
    LIMIT ?
"""


def _excerpt(text: str, length: int = 220) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= length else f"{text[:length]}…"


def _sample_rows(limit: int) -> list[dict[str, object]]:
    with duckdb.connect(str(settings.db_path), read_only=True) as db:
        cursor = db.execute(_SAMPLE_SQL, [limit])
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def rule_vs_llm_comparison(limit: int = 5, run_llm: bool = False) -> dict[str, object]:
    """Compare deterministic rule output against an optional LLM second opinion.

    Truth boundary: the deterministic engine is authoritative. The LLM is a comparison
    layer only, and no paid request is sent unless OPENAI_API_KEY is configured. When the
    key is absent, every LLM cell is an explicit empty state — nothing is fabricated.
    """
    available = llm_available()
    base = {
        "llm_available": available,
        "llm_requested": bool(run_llm and available),
        "llm_model": settings.openai_model if available else None,
        "default_engine": "deterministic_rules_v1",
        "note": (
            "LLM comparison is active for this explicit request. The deterministic engine remains authoritative."
            if available and run_llm else
            "An API key is configured, but no paid call has been made. Run the comparison explicitly when needed."
            if available else
            "No OPENAI_API_KEY is configured, so no LLM call is made. Deterministic rule-based scoring "
            "remains the default for every case; LLM comparison is an optional, opt-in layer."
        ),
    }
    if not settings.db_path.exists():
        return {**base, "status": "unavailable", "reason": "DuckDB mart not built", "sample_size": 0, "cases": []}

    rows = _sample_rows(limit)
    cases: list[dict[str, object]] = []
    for row in rows:
        deterministic = {field: row.get(field) for field in _DETERMINISTIC_FIELDS}
        llm_output: dict[str, object] | None = None
        category_agreement: bool | None = None
        action_agreement: bool | None = None
        evidence_overlap: float | None = None
        unsupported_evidence_rate: float | None = None
        latency_ms: float | None = None
        llm_error: str | None = None
        if available and run_llm:
            payload = {
                "case_id": row.get("case_id"),
                "text": row.get("case_text"),
                "product": row.get("product"),
                "source": row.get("source"),
                "language": row.get("language"),
            }
            try:
                started = time.perf_counter()
                llm_output = evaluate_with_openai(payload)
                latency_ms = round((time.perf_counter() - started) * 1000, 3)
                if llm_output:
                    category_agreement = llm_output.get("risk_category") == deterministic["risk_category"]
                    action_agreement = llm_output.get("recommended_action") == deterministic["recommended_action"]
                    deterministic_terms = {str(item.get("term", "")).lower() for item in json.loads(str(row.get("evidence_json") or "[]"))}
                    llm_terms = [str(item).lower() for item in (llm_output.get("evidence") or [])]
                    evidence_overlap = round(sum(any(term and term in item for term in deterministic_terms) for item in llm_terms) / len(llm_terms), 3) if llm_terms else 0.0
                    source_text = str(row.get("case_text") or "").lower()
                    unsupported_evidence_rate = round(sum(item not in source_text for item in llm_terms) / len(llm_terms), 3) if llm_terms else 0.0
            except Exception as exc:  # Optional comparison must never break deterministic review.
                llm_error = type(exc).__name__
        cases.append({
            "case_id": row.get("case_id"),
            "source": row.get("source"),
            "language": row.get("language"),
            "excerpt": _excerpt(str(row.get("case_text") or "")),
            "deterministic": deterministic,
            "llm": llm_output,
            "category_agreement": category_agreement,
            "action_agreement": action_agreement,
            "routing_agreement": action_agreement,
            "evidence_overlap_rate": evidence_overlap,
            "unsupported_evidence_rate": unsupported_evidence_rate,
            "llm_latency_ms": latency_ms,
            "llm_cost_usd": None,
            "cost_note": "Unavailable because the evaluator does not expose provider usage and pricing metadata.",
            "llm_error": llm_error,
        })
    agreements = [c["category_agreement"] for c in cases if c["category_agreement"] is not None]
    routing = [c["routing_agreement"] for c in cases if c["routing_agreement"] is not None]
    evidence = [c["evidence_overlap_rate"] for c in cases if c["evidence_overlap_rate"] is not None]
    unsupported = [c["unsupported_evidence_rate"] for c in cases if c["unsupported_evidence_rate"] is not None]
    latencies = [c["llm_latency_ms"] for c in cases if c["llm_latency_ms"] is not None]
    return {
        **base,
        "status": "available",
        "sample_size": len(cases),
        "category_agreement_rate": round(sum(agreements) / len(agreements), 3) if agreements else None,
        "routing_agreement_rate": round(sum(routing) / len(routing), 3) if routing else None,
        "evidence_overlap_rate": round(sum(evidence) / len(evidence), 3) if evidence else None,
        "unsupported_evidence_rate": round(sum(unsupported) / len(unsupported), 3) if unsupported else None,
        "average_llm_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "estimated_llm_cost_usd": None,
        "failure_count": sum(case["llm_error"] is not None for case in cases),
        "cases": cases,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(rule_vs_llm_comparison(), ensure_ascii=False, indent=2))
