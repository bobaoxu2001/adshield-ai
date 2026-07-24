from __future__ import annotations

from statistics import stdev


def daily_anomalies(daily_counts: list[dict[str, object]]) -> list[dict[str, object]]:
    if not daily_counts:
        return []
    values = [int(row["cases"]) for row in daily_counts]
    mean = sum(values) / len(values)
    std = stdev(values) if len(values) > 1 else 0.0
    rows = []
    for row in daily_counts:
        z_score = round((int(row["cases"]) - mean) / std, 2) if std else 0.0
        rows.append({"date": str(row["date"]), "cases": int(row["cases"]), "z_score": z_score, "is_anomaly": abs(z_score) >= 2})
    return rows[-30:]
