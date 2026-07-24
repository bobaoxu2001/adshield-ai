# Product Upgrade Changelog

## 2026-07-16 — Production-control and benchmark remediation

### Added

- shadow strategy v2.1 with explicit category precedence, guarded positive exceptions, and benchmark-only structured advertiser evidence;
- same-label benchmark comparison: 60% → 93.3% category, 66.7% → 100% routing, and 30% → 100% exception routing;
- Launch Readiness with separate benchmark, authorized-data, independent-label, reviewer-identity, SLA, approval, promotion, and rollback gates;
- default-deny RBAC, two-person blind labeling, disagreement adjudication, assignment SLA measurement, attributed promotion/rollback, and audit events;
- authorized-ad batch validation that rejects expired scope, missing fields, duplicate records, unproven labels, and curated/synthetic IDs;
- four bounded Mandarin homophone substitutions and provenance-preserving OCR/ASR text evidence adapters;
- attributed reviewer feedback using reviewer identity and role headers;
- eight additional automated tests, bringing the suite to 64 passing tests.

### Preserved

- authoritative v1 behavior and its frozen 60% / 66.7% / 30% benchmark baseline;
- public read-only deployment, explicit empty states, complaint-prior restrictions, and no claim of internal data, independent validation, novel-homophone discovery, or raw-media understanding.

## 2026-07-16 — Review-operations polish

### Added

- explicit benchmark promotion checks and failure attribution by taxonomy, routing, evidence, and exception handling;
- accountable remediation owners and next tests for every benchmark gap bucket;
- separate capacity and quality status in candidate shadow previews;
- priority, language, and routing segmentation in the complete review queue;
- first-viewport operator summary in Investigation Desk;
- plain-language metric attribution readout with a recommended analyst action;
- cross-surface scroll reset and a fresh evidence-based product audit.

### Preserved

- the public-vs-curated data boundary, complaint-prior routing restrictions, non-authoritative candidate behavior, read-only public deployment, bounded Mandarin claims, and visible hold-promotion decision.

## 2026-07-15 — Strategy lifecycle release

### Added

- independent product framing and lifecycle-first navigation;
- Policy Studio for taxonomy, signals, positive exceptions, and policy packs;
- immutable enforced and shadow strategy versions with rollback metadata;
- Decision Trace with explicit unavailable modalities and confidence boundary;
- 60-scenario bilingual benchmark and threshold sensitivity;
- Strategy Evaluation with reviewer-capacity and illustrative business guardrails;
- Advertiser Integrity with strict real-vs-curated separation;
- Emerging Risks term, n-gram, and source/category-mix discovery;
- composition-vs-within-segment metric decomposition;
- per-stage operational latency, throughput, and failure measurements;
- expanded optional rule-vs-LLM comparison fields;
- lifecycle DuckDB tables and persisted shadow results;
- product architecture, methodology, and truth-boundary docs.

### Preserved

- navy Command Center shell, dense operational tables, provenance-first overview, Investigation Desk, public-source ingestion, deterministic source guardrails, read-only Vercel mode, and local feedback workflow.

### Claim changes

The README presents the product on its own terms as an independent ads-risk prototype. Benchmark outcomes are described only as curated agreement, and missing LLM cost/usage data remains unavailable.
