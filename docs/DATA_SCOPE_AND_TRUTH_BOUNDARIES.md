# Data Scope and Truth Boundaries

| Scope | What it contains | Permitted claims | Prohibited claims |
|---|---|---|---|
| `real_public` | FTC aggregates and scrubbed CFPB records | harm priors, vocabulary, descriptive mix, research prioritization | ads, verified violations, platform prevalence, approve/reject enforcement |
| `external_independent_validation` | Aggregate UW evidence from 500 real web ads and independent participant opinions | external perception mix, annotator coverage, label ambiguity, validation planning | TikTok prevalence, enforcement accuracy, policy violation truth, promotion eligibility |
| `authorized_public_ads` | Meta creatives retrieved with an authorized API token | creative-level evidence and source-scoped routing | private history, identity, networks, internal platform decisions |
| `curated_benchmark` | 60 hypothetical labeled scenarios | benchmark agreement and sensitivity | production quality or observed volume |
| `hypothetical_simulation` | editable capacity, cost, revenue, and harm assumptions | tradeoff exploration | observed business value or forecast |
| `test_fixture` | automated test records | regression behavior | product or business evidence |

## Enforcement controls

- CFPB source routing cannot emit allow, soft reject, or hard reject.
- External opinion labels cannot be reclassified as platform enforcement labels or satisfy a promotion gate.
- Benchmark tables are not queried by real-public KPI endpoints.
- Candidate strategy output is non-authoritative and stored separately.
- Quality metrics remain null until eligible human labels exist.
- Optional LLM calls require both a configured key and an explicit request.
- Missing modalities and advertiser/network relationships are shown as unavailable.

Risk scores are review-priority values, not calibrated probabilities, legal conclusions, or autonomous enforcement decisions.
