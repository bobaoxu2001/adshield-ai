# Benchmark Methodology

The benchmark contains exactly 60 curated hypothetical scenarios, isolated with `data_scope = curated_benchmark`:

| Segment | Count |
|---|---:|
| English commercial-risk cases | 15 |
| Mandarin commercial-risk cases | 15 |
| Mixed-language and evasion variants | 10 |
| Positive-exception / false-positive challenges | 10 |
| Advertiser-behavior scenarios | 10 |

Every row includes language, market, vertical, hypothetical advertiser context, creative text, optional landing text, expected category, evidence, exception, routing, human-review expectation, ambiguity, and rationale.

Reported outputs are category agreement, expected-term coverage, routing agreement, exception-application agreement, Mandarin expected-term coverage, and exact exception-scenario routing agreement. They are not production precision, recall, F1, accuracy, false-positive rate, or false-negative rate.

## This is a development set, not a test set

**The 60 scenarios are the set candidate v2.1 was remediated against.** Its category precedence rules
and routing term sets in [`src/risk/lifecycle.py`](../src/risk/lifecycle.py) and
[`src/risk/scoring.py`](../src/risk/scoring.py) were written while inspecting these failures. Reported
agreement is therefore **regression coverage — proof that a known set of defects is fixed and stays
fixed — and not evidence of generalization to unseen ads.** No held-out set exists yet; building one
(ideally authored by a second bilingual reviewer after v2.1 was frozen) is the first blocker on any
generalization claim.

Both versions run against the identical 60 labels, and no expected label was edited to manufacture
agreement:

| Strategy | Category | Routing | Exception routing | Development-set decision |
|---|---:|---:|---:|---|
| Frozen authoritative v1 | 60% | 66.7% | 30% | HOLD |
| Shadow candidate v2.1 (tuned on this set) | 93.3% | 100% | 100% | Regression clean; eligible for controlled human review |

Candidate v2.1 adds explicit category precedence, structured benchmark-only advertiser context, bounded bilingual canonicalization, and guarded exception routing. Five scenarios still have a category or evidence disagreement, and remain visible for inspection.

Passing this curated gate does not authorize production. The separate Launch Readiness gate still requires authorized ad records, independently labeled enforcement outcomes, reviewer identity coverage, label agreement, observed SLA compliance, policy-owner approval, and release-manager execution.

The current set is curated by the project author **and was used to develop the candidate it scores**, so it demonstrates deterministic behavior and regression coverage—not independent external validation or generalization. A held-out set, bilingual expert adjudication, and inter-rater agreement remain mandatory production blockers rather than aspirational footnotes.
