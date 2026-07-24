from __future__ import annotations

import duckdb

from src.analytics.anomaly_detection import daily_anomalies
from src.analytics.feature_lift import calculate_feature_lift
from src.config import settings


def metric_diagnosis() -> dict[str, object]:
    if not settings.db_path.exists():
        return {"category_distribution": [], "language_comparison": [], "market_comparison": [], "action_coverage": [], "feature_lift": [], "anomalies": [], "strategy_brief": [], "root_cause_decomposition": []}
    with duckdb.connect(str(settings.db_path), read_only=True) as db:
        def records(sql: str) -> list[dict[str, object]]:
            cursor = db.execute(sql)
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

        scores = records("SELECT risk_score, evidence_json FROM ad_risk_scores")
        category = records("SELECT risk_category, count(*) cases FROM ad_risk_scores GROUP BY risk_category ORDER BY cases DESC")
        language = records("""
            SELECT language, count(*) cases,
                   round(avg(CASE WHEN risk_score >= 0.65 THEN 1.0 ELSE 0.0 END), 3) high_risk_rate
            FROM ad_risk_scores GROUP BY language ORDER BY cases DESC
        """)
        action = records("SELECT recommended_action, count(*) cases FROM ad_risk_scores GROUP BY recommended_action ORDER BY cases DESC")
        markets = records("""
            SELECT c.state, count(*) cases, avg(CASE WHEN s.risk_score >= 0.65 THEN 1.0 ELSE 0.0 END) high_risk_rate
            FROM ad_risk_scores s JOIN cfpb_complaints c USING (case_id)
            WHERE c.state IS NOT NULL AND c.state <> ''
            GROUP BY c.state HAVING count(*) >= 5 ORDER BY cases DESC LIMIT 12
        """)
        daily = records("SELECT cast(case_date AS DATE) date, count(*) cases FROM ad_risk_scores WHERE case_date IS NOT NULL GROUP BY date ORDER BY date")
        root_causes = records("""
            WITH dated AS (
              SELECT risk_category, risk_score, cast(case_date AS DATE) case_date,
                     max(cast(case_date AS DATE)) OVER () latest
              FROM ad_risk_scores WHERE case_date IS NOT NULL
            ), labeled AS (
              SELECT *, CASE WHEN case_date >= latest - INTERVAL 90 DAY THEN 'recent_90d' ELSE 'prior_90d' END period
              FROM dated WHERE case_date >= latest - INTERVAL 180 DAY
            ), totals AS (
              SELECT period, count(*) total_cases,
                     avg(CASE WHEN risk_score >= 0.65 THEN 1.0 ELSE 0.0 END) overall_high_risk_rate
              FROM labeled GROUP BY period
            ), segments AS (
              SELECT period, risk_category, count(*) cases,
                     avg(CASE WHEN risk_score >= 0.65 THEN 1.0 ELSE 0.0 END) segment_high_risk_rate
              FROM labeled GROUP BY period, risk_category
            ), combined AS (
              SELECT coalesce(r.risk_category, b.risk_category) risk_category,
                     coalesce(r.cases, 0) recent_cases, coalesce(b.cases, 0) baseline_cases,
                     coalesce(r.cases / nullif(tr.total_cases, 0), 0) recent_share,
                     coalesce(b.cases / nullif(tb.total_cases, 0), 0) baseline_share,
                     coalesce(r.segment_high_risk_rate, 0) recent_rate,
                     coalesce(b.segment_high_risk_rate, 0) baseline_rate
              FROM (SELECT * FROM segments WHERE period = 'recent_90d') r
              FULL OUTER JOIN (SELECT * FROM segments WHERE period = 'prior_90d') b USING (risk_category)
              CROSS JOIN (SELECT * FROM totals WHERE period = 'recent_90d') tr
              CROSS JOIN (SELECT * FROM totals WHERE period = 'prior_90d') tb
            )
            SELECT risk_category, recent_cases, baseline_cases,
                   round(recent_share, 4) recent_share, round(baseline_share, 4) baseline_share,
                   round(recent_rate, 4) recent_high_risk_rate, round(baseline_rate, 4) baseline_high_risk_rate,
                   round((recent_share - baseline_share) * baseline_rate, 4) composition_shift_contribution,
                   round(recent_share * (recent_rate - baseline_rate), 4) within_segment_rate_contribution
            FROM combined
            ORDER BY abs(composition_shift_contribution) + abs(within_segment_rate_contribution) DESC
        """)
        dimension_rows = records("""
            WITH bounds AS (SELECT max(cast(case_date AS DATE)) latest FROM ad_risk_scores WHERE case_date IS NOT NULL)
            SELECT s.risk_category, s.source, s.language, c.state market, s.risk_score,
                   CASE WHEN cast(s.case_date AS DATE) >= latest - INTERVAL 90 DAY THEN 'recent_90d' ELSE 'prior_90d' END period
            FROM ad_risk_scores s
            LEFT JOIN cfpb_complaints c USING (case_id), bounds
            WHERE cast(s.case_date AS DATE) >= latest - INTERVAL 180 DAY
        """)
        evidence_dimension_rows = records("""
            WITH bounds AS (SELECT max(cast(case_date AS DATE)) latest FROM ad_risk_scores WHERE case_date IS NOT NULL)
            SELECT json_extract_string(item.value, '$.term') evidence_feature, s.risk_score,
                   CASE WHEN cast(s.case_date AS DATE) >= latest - INTERVAL 90 DAY THEN 'recent_90d' ELSE 'prior_90d' END period
            FROM ad_risk_scores s, bounds, json_each(s.evidence_json) item
            WHERE cast(s.case_date AS DATE) >= latest - INTERVAL 180 DAY
        """)
    feature_lift = calculate_feature_lift(scores)
    anomalies = daily_anomalies(daily)
    strategy_brief: list[dict[str, str]] = []
    if category:
        top = category[0]
        share = top["cases"] / max(1, len(scores))
        strategy_brief.append({
            "label": "Source-mix concentration",
            "value": f"{share:.0%}",
            "detail": f"{top['risk_category']} dominates this public sample; do not read it as platform prevalence.",
        })
    if feature_lift:
        top_feature = feature_lift[0]
        strategy_brief.append({
            "label": "Strongest differentiator",
            "value": f"{top_feature['term']} · {top_feature['lift']}×",
            "detail": "Descriptive rule-feature lift for investigation prioritization, not causal impact.",
        })
    flagged = [row for row in anomalies if row.get("is_anomaly")]
    strategy_brief.append({
        "label": "Volume spike flags",
        "value": str(len(flagged)),
        "detail": "Absolute z-score ≥ 2 within the displayed dated-case window.",
    })
    def decompose(rows: list[dict[str, object]], field: str, dimension: str) -> list[dict[str, object]]:
        periods = ("recent_90d", "prior_90d")
        totals = {period: sum(row["period"] == period for row in rows) for period in periods}
        output = []
        segments = sorted({str(row.get(field)) for row in rows if row.get(field) not in {None, ""}})
        for segment in segments:
            subset = {period: [row for row in rows if row["period"] == period and str(row.get(field)) == segment] for period in periods}
            counts = {period: len(subset[period]) for period in periods}
            shares = {period: counts[period] / max(1, totals[period]) for period in periods}
            rates = {period: sum(float(row["risk_score"]) >= 0.65 for row in subset[period]) / max(1, counts[period]) for period in periods}
            output.append({"dimension": dimension, "segment": segment, "recent_cases": counts["recent_90d"], "baseline_cases": counts["prior_90d"], "recent_share": round(shares["recent_90d"], 4), "baseline_share": round(shares["prior_90d"], 4), "recent_high_risk_rate": round(rates["recent_90d"], 4), "baseline_high_risk_rate": round(rates["prior_90d"], 4), "composition_shift_contribution": round((shares["recent_90d"] - shares["prior_90d"]) * rates["prior_90d"], 4), "within_segment_rate_contribution": round(shares["recent_90d"] * (rates["recent_90d"] - rates["prior_90d"]), 4)})
        return sorted(output, key=lambda row: abs(float(row["composition_shift_contribution"])) + abs(float(row["within_segment_rate_contribution"])), reverse=True)
    root_by_dimension = []
    for field, dimension in (("risk_category", "category"), ("source", "source"), ("language", "language"), ("market", "market")):
        root_by_dimension.extend(decompose(dimension_rows, field, dimension))
    root_by_dimension.extend(decompose(evidence_dimension_rows, "evidence_feature", "evidence_feature"))
    root_by_dimension.sort(key=lambda row: abs(float(row["composition_shift_contribution"])) + abs(float(row["within_segment_rate_contribution"])), reverse=True)
    recent_rows = [row for row in dimension_rows if row["period"] == "recent_90d"]
    prior_rows = [row for row in dimension_rows if row["period"] == "prior_90d"]
    recent_rate = sum(float(row["risk_score"]) >= 0.65 for row in recent_rows) / max(1, len(recent_rows))
    prior_rate = sum(float(row["risk_score"]) >= 0.65 for row in prior_rows) / max(1, len(prior_rows))
    composition_total = round(sum(float(row["composition_shift_contribution"]) for row in root_causes), 4)
    within_total = round(sum(float(row["within_segment_rate_contribution"]) for row in root_causes), 4)
    delta = round(recent_rate - prior_rate, 4)
    if abs(composition_total) > abs(within_total) + 0.001:
        primary_driver = "sample composition"
    elif abs(within_total) > abs(composition_total) + 0.001:
        primary_driver = "within-segment rate"
    else:
        primary_driver = "mixed composition and within-segment movement"
    direction = "increased" if delta > 0.0005 else "decreased" if delta < -0.0005 else "was broadly flat"
    metric_change_summary = {
        "recent_window": "recent_90d",
        "baseline_window": "prior_90d",
        "recent_high_priority_rate": round(recent_rate, 4),
        "baseline_high_priority_rate": round(prior_rate, 4),
        "rate_change": delta,
        "composition_contribution": composition_total,
        "within_segment_contribution": within_total,
        "primary_driver": primary_driver,
        "operator_readout": f"High-priority rate {direction} by {abs(delta):.1%}; the larger descriptive contribution came from {primary_driver}.",
        "recommended_action": "Inspect the leading segment rows before changing thresholds; this decomposition is descriptive, not causal.",
    }
    return {"category_distribution": category, "language_comparison": language, "market_comparison": markets, "action_coverage": action, "feature_lift": feature_lift, "anomalies": anomalies, "strategy_brief": strategy_brief, "metric_change_summary": metric_change_summary, "root_cause_decomposition": root_causes, "root_cause_by_dimension": root_by_dimension, "root_cause_dimension_availability": {"source": "available", "category": "available", "language": "available", "market": "available for CFPB state only", "advertiser_vertical": "unavailable in the current public snapshot", "evidence_feature": "available as feature-occurrence decomposition"}, "root_cause_note": "Descriptive decomposition splits high-priority-rate movement into sample-composition and within-segment-rate contributions across comparable 90-day windows; not causal attribution."}
