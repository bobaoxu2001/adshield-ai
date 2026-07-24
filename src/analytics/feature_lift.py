from __future__ import annotations

import json
from collections import Counter

def calculate_feature_lift(scores: list[dict[str, object]]) -> list[dict[str, object]]:
    if not scores:
        return []
    all_terms: Counter[str] = Counter()
    high_terms: Counter[str] = Counter()
    high_total = 0
    for row in scores:
        value = row.get("evidence_json")
        terms = {item.get("term", "") for item in json.loads(value or "[]") if item.get("term")}
        all_terms.update(terms)
        if float(row.get("risk_score") or 0) >= 0.65:
            high_total += 1
            high_terms.update(terms)
    high_total = max(1, high_total)
    total = max(1, len(scores))
    rows = []
    for term, count in all_terms.items():
        high_count = high_terms[term]
        lift = (high_count / high_total) / max(count / total, 1 / total)
        rows.append({"term": term, "cases": count, "high_risk_cases": high_count, "lift": round(lift, 2)})
    return sorted(rows, key=lambda row: (row["lift"], row["high_risk_cases"]), reverse=True)[:12]
