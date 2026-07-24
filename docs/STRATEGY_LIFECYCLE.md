# Strategy Lifecycle

## States

`draft → shadow → enforced → paused`

The repository ships two immutable versions:

- `STRAT-COMMERCIAL-RISK@1.0.0`: enforced and authoritative.
- `STRAT-COMMERCIAL-RISK@2.1.0-candidate`: remediated shadow candidate and non-authoritative.

Each version records owner, thresholds, policy packs, market/language scope, reviewer capacity, latency guardrail, effective date, change reason, and rollback target.

## Promotion contract

A candidate may be promoted only after scoped benchmark review, shadow disagreement inspection, source-boundary verification, reviewer-capacity assessment, at least 100 authorized ad records, at least 100 independently labeled ads, 85% label agreement, 100% reviewer identity coverage, 95% observed SLA compliance, policy-owner approval, and an explicit release-manager action. This public demo never promotes automatically.

Shadow results are stored separately with both actions, candidate score, disagreement flag, and evaluated time. The repository implements and tests the RBAC promotion/rollback state machine: failed checks deny promotion, a successful promotion records the previous active version, and rollback restores it with an attributed reason and audit event. The public Vercel surface is read-only; a production deployment still needs governed identity and durable audit-storage adapters.

Independent labeling is blind until two distinct assigned reviewers submit. Agreement closes the task; disagreement requires a senior reviewer or policy owner to adjudicate. SLA monitoring is calculated from persisted assignment and submission timestamps, never from illustrative throughput measurements.
