# Product Architecture

AdShield AI separates evidence, governance, decisions, evaluation, and presentation so a change in one layer remains reviewable.

## Lifecycle

1. Official public sources are retrieved with manifests and normalized.
2. Taxonomy, reusable signals, scoped positive exceptions, and policy packs define policy intent.
3. An immutable strategy version combines policy packs, thresholds, source constraints, capacity, and actions.
4. The deterministic engine extracts evidence, retrieves public policy summaries, scores priority, and applies source-aware routing.
5. The current strategy is authoritative. Candidate output is stored in `strategy_shadow_results` and cannot replace it.
6. Reviewers inspect the Decision Trace and write feedback separately from the original result.
7. Real-public descriptive metrics, curated benchmark agreement, operational measurements, and hypothetical tradeoff simulations remain separate.

## Runtime

- FastAPI exposes read APIs and local-only feedback writes.
- React provides the strategy workspace and accessible Investigation Desk.
- DuckDB stores the analytical mart and lifecycle catalogs.
- Vercel serves a deliberately read-only snapshot; local mode can be writable.

## Guardrails

CFPB cases are forced to research-prior actions. Optional LLM output is non-authoritative. No missing landing-page, advertiser-history, or network evidence is inferred. Strategy versions are frozen objects with rollback targets and lifecycle state.

The lifecycle design is informed by general enterprise governance patterns—separation of taxonomy, detection primitives, exceptions, versioned strategy, and audit logs. It does not copy a proprietary interface, internal taxonomy, organization, dataset, metric, or implementation.
