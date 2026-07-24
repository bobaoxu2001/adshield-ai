# Production Governance Contract

AdShield separates three decisions that are often incorrectly collapsed:

1. **Does the candidate improve on a curated regression set?** Benchmark Lab.
2. **Is there authorized evidence to evaluate production behavior?** Authorized-data and independent-label gates.
3. **May a named operator change the enforced version?** RBAC promotion service.

## Default-deny roles

| Role | Allowed operations |
|---|---|
| Reviewer | Submit one attributed label for an assigned case |
| Senior reviewer | Submit and adjudicate disagreeing labels |
| Queue manager | Assign at least two distinct reviewers; read SLA state |
| Policy owner | Adjudicate and approve promotion evidence |
| Release manager | Execute promotion or rollback after all gates pass |
| Auditor | Read audit and SLA evidence |

Reviewer identity is required. The local adapter accepts declared identity and role headers for product testing; those headers are not authentication. Production must derive actor identity and roles from a verified identity provider. A role without an explicit permission is denied.

## Independent ground truth

- Each eligible ad is assigned to at least two distinct reviewers.
- Peer decisions remain hidden until the minimum label count is met.
- Matching labels reach consensus; disagreement requires attributed adjudication.
- Existing single-reviewer product feedback is never reclassified as independent ground truth.
- Label agreement is unavailable until enough eligible assignments exist.

## SLA measurement

The SLA service reads persisted assignment, due, and submission timestamps and reports open, overdue, due-within-15-minutes, and completed-on-time measures. Local request latency and illustrative reviewer capacity do not count as production SLA evidence.

## Promotion and rollback

Promotion requires all of the following:

- category, routing, and exception-routing agreement at or above 90%;
- at least 100 authorized ad records and 100 independently labeled ads;
- independent label agreement at or above 85%;
- 100% reviewer identity coverage;
- observed SLA compliance at or above 95%;
- policy-owner approval;
- a release manager and non-empty reason.

A successful promotion records the previous active version. Rollback requires the release-manager role and a reason, restores that version, and appends an audit event. Historical decisions are never rewritten.

## Current deployment truth

The public Vercel deployment exposes readiness evidence but disables mutation. It contains zero authorized Meta ads, zero independent enforcement labels, no advertiser history, no production reviewer assignments, and no policy-owner approval. Candidate v2.1 passes the curated benchmark gate, while the overall production decision correctly remains **HOLD**.

The public demo now also loads aggregate external-validation evidence from the University of Washington CHI 2021 Ad Perceptions dataset: 500 real web ads, 1,025 reported annotators, and 5,104 rating observations. These labels describe participant opinions and remain `informative_only`; they do not satisfy authorized-ad, independent enforcement-label, label-agreement, identity, or reviewer-SLA promotion checks.

An official TikTok Commercial Content API connector is implemented with the `research.adlib.basic` contract. It remains zero-record and fail-closed without an approved research token. No scraper or fallback record is substituted. A scheduled production monitor creates real external reachability observations in GitHub Actions; those observations remain separate from reviewer decision SLA.

The domain service and tests are implemented. A real production deployment must connect them to an identity provider, governed warehouse or transactional store, encrypted secrets, retention policy, and durable append-only audit sink.
