# Metric Dictionary

| Metric | Definition | Decision use | Limitation |
|---|---|---|---|
| Total real records | FTC aggregate rows + normalized CFPB complaints + optional Meta ads | Provenance and data coverage | Mixed granularity; not total ads reviewed |
| Cases analyzed | CFPB complaint-derived cases + Meta ads scored | Workflow throughput | CFPB cases are risk priors, not ad violations |
| High-risk rate | Share of scores ≥ 0.65 | Queue planning | Rule threshold, not ground-truth prevalence |
| Review queue size | Cases with `needs_human_review=true` | Staffing and backlog | Depends on confidence/routing policy |
| Estimated minutes saved | Meta ad cases with `needs_human_review=false` × 3 minutes | Directional efficiency | Assumption, clearly labeled estimate; zero for complaint-only queues |
| Feature lift | High-risk term prevalence divided by all-case prevalence | Monitor risk-driving terms | Descriptive and partly endogenous to rules |
| Escalation rate | Human-review recommendations / scored cases | Automation risk appetite | Lower is not automatically better |
| Auto-decision coverage | Actual-ad cases with `needs_human_review=false` / all scored cases | Review capacity | Does not equal correctness; complaint priors are never automation-eligible |
| Evidence completeness | Cases with ≥1 extracted phrase / scored cases | Explanation coverage | Product/source priors may score without a phrase |
| Precision / Recall / F1 | Calculated only from human feedback labels | Quality management | Unavailable before labels exist |
| Anomaly flag | Absolute daily volume z-score ≥ 2 | Investigate spikes | Sensitive to sparse dates and sampling |
