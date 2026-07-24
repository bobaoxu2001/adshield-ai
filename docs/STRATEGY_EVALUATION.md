# Strategy Evaluation

Strategy Evaluation compares the enforced version with a shadow candidate across the isolated benchmark.

## Outputs

- review queue volume and reviewer-capacity utilization;
- allow, escalation, and rejection routing rates;
- automation-eligible coverage;
- curated missed-risk and false-positive-scenario exposure;
- threshold sensitivity across five escalation settings;
- deterministic latency guardrail;
- illustrative review time, reviewer cost, model-cost-if-applied, revenue-at-risk, and harm assumptions. Actual deterministic model cost remains zero because no paid model runs in this evaluation.

All financial and business values carry this label: **Illustrative scenario assumptions, not observed business values.** They are editable to show decision sensitivity, not to forecast a platform.

Operational Performance separately measures evidence extraction, policy retrieval, complete `score_case` routing, and total pipeline p50/p95/p99 latency on the current request. It is a local request benchmark, not production traffic or an SLA claim.
