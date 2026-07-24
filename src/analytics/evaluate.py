from __future__ import annotations

from datetime import UTC, datetime

import duckdb

from src.config import settings


def evaluation_metrics() -> dict[str, object]:
    if not settings.db_path.exists():
        return {"status": "unavailable", "reason": "DuckDB mart not built"}
    with duckdb.connect(str(settings.db_path), read_only=True) as db:
        counts = db.execute("""
            SELECT count(*) scored,
                   count(*) FILTER (WHERE needs_human_review) review_cases,
                   count(*) FILTER (WHERE NOT needs_human_review AND source = 'Meta') auto_cases,
                   count(*) FILTER (WHERE coalesce(evidence_json, '[]') <> '[]') evidence_cases
            FROM ad_risk_scores
        """).fetchone()
        feedback_count = int(db.execute("SELECT count(*) FROM human_review_feedback").fetchone()[0])
        eligible_feedback_count = int(db.execute("""
            SELECT count(*) FROM human_review_feedback f
            JOIN ad_risk_scores s USING (case_id)
            WHERE s.source = 'Meta' AND s.decision_scope = 'ad_triage'
        """).fetchone()[0]) if feedback_count else 0
        usable = db.execute("""
                WITH latest AS (
                  SELECT case_id, reviewer_decision,
                         row_number() OVER (PARTITION BY case_id ORDER BY created_at DESC) row_num
                  FROM human_review_feedback
                )
                SELECT s.risk_score, l.reviewer_decision
                FROM ad_risk_scores s JOIN latest l USING (case_id)
                WHERE l.row_num = 1
                  AND s.source = 'Meta' AND s.decision_scope = 'ad_triage'
                  AND l.reviewer_decision IN ('approve', 'reject', 'false positive', 'false negative')
            """).fetchall() if feedback_count else []
    scored, review_cases, auto_cases, evidence_cases = map(int, counts)
    if not scored:
        return {"status": "unavailable", "reason": "No cases scored"}
    result: dict[str, object] = {
        "status": "available",
        "scored_cases": scored,
        "escalation_rate": round(review_cases / scored, 3),
        "auto_decision_coverage": round(auto_cases / scored, 3),
        "evidence_extraction_completeness": round(evidence_cases / scored, 3),
        "estimated_review_minutes_saved": auto_cases * 3,
        "labeled_cases": eligible_feedback_count,
        "total_feedback_events": feedback_count,
        "precision": None,
        "recall": None,
        "f1": None,
        "label_note": "Precision/recall/F1 appear only after eligible authorized-ad reviewer labels exist; complaint-prior feedback is excluded.",
    }
    if usable:
        predicted = [float(score) >= 0.65 for score, _ in usable]
        actual = [decision in {"reject", "false negative"} for _, decision in usable]
        tp = sum(pred and truth for pred, truth in zip(predicted, actual, strict=True))
        fp = sum(pred and not truth for pred, truth in zip(predicted, actual, strict=True))
        fn = sum(not pred and truth for pred, truth in zip(predicted, actual, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        result.update({"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "label_note": "Metrics use the latest eligible authorized-ad reviewer decision per case; complaint priors are excluded."})
    return result


def _comparison_section() -> str:
    from src.risk.comparison import rule_vs_llm_comparison

    comparison = rule_vs_llm_comparison(limit=5)
    if comparison.get("status") != "available":
        return (
            "The deterministic rules engine is the default and is evaluated for every case. "
            "A sample comparison could not be generated because the DuckDB mart is not built; "
            "run `make ingest && make transform` first.\n"
        )
    lines = [comparison.get("note", ""), ""]
    if comparison.get("llm_available") and comparison.get("llm_requested"):
        lines.append(f"LLM comparison model: `{comparison.get('llm_model')}`. ")
        rate = comparison.get("category_agreement_rate")
        if rate is not None:
            lines.append(f"Category agreement on the sample: **{rate:.0%}**.")
        lines.append("")
        lines.append("| Case | Source | Rule category → action | LLM category → action | Category match |")
        lines.append("|---|---|---|---|---|")
        for case in comparison["cases"]:
            det = case["deterministic"]
            llm = case.get("llm") or {}
            match = "—" if case.get("category_agreement") is None else ("✅" if case["category_agreement"] else "⚠️")
            lines.append(
                f"| {case['case_id']} | {case['source']} | {det['risk_category']} → {det['recommended_action']} | "
                f"{llm.get('risk_category', 'n/a')} → {llm.get('recommended_action', 'n/a')} | {match} |"
            )
    elif comparison.get("llm_available"):
        lines.append("An API key is configured, but the report does not trigger paid calls. Run the comparison explicitly in the dashboard when needed.")
    else:
        lines.append("Sampled deterministic decisions (the authoritative default). The LLM column is intentionally")
        lines.append("empty because no `OPENAI_API_KEY` is configured — nothing is fabricated.")
        lines.append("")
        lines.append("| Case | Source | Rule category | Severity | Rule action | LLM (optional) |")
        lines.append("|---|---|---|---|---|---|")
        for case in comparison["cases"]:
            det = case["deterministic"]
            lines.append(
                f"| {case['case_id']} | {case['source']} | {det['risk_category']} | {det['severity']} | "
                f"{det['recommended_action']} | not run (no key) |"
            )
    return "\n".join(lines) + "\n"


def write_report() -> None:
    result = evaluation_metrics()
    metrics = "\n".join(f"- **{key.replace('_', ' ').title()}:** {value}" for key, value in result.items())
    text = f"""# Evaluation Report

Generated: {datetime.now(UTC).isoformat()}

This report is calculated from the current local DuckDB mart. It never substitutes fabricated labels. Precision, recall, and F1 remain unavailable until human review feedback exists.

## Current deterministic workflow

{metrics}

## Rule vs. LLM comparison

The deterministic rules engine (`deterministic_rules_v1`) is the default and is evaluated for every case. If `OPENAI_API_KEY` is configured, `src/risk/comparison.py` produces a second structured assessment for a 5-case sample through the optional `src/risk/llm_evaluator.py`; no paid call is made by default. The same data also powers the dashboard's `/api/llm-comparison` panel.

{_comparison_section()}
## Interpretation limits

CFPB complaints are not verified examples of policy-violating ads, and FTC rows are aggregates. These sources provide consumer-harm priors and vocabulary, not ground-truth ad enforcement labels. Human review remains required for ambiguous decisions.
"""
    (settings.root / "docs" / "EVALUATION_REPORT.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    write_report()
