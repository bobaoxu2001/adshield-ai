# Policy Studio

Policy Studio makes four configuration layers inspectable:

- **Risk taxonomy:** hierarchical category ID, parent, description, severity, markets, languages, verticals, owner, version, effective time, and change reason.
- **Risk signals:** reusable keyword, exact, pinyin, character-split, off-platform, landing-page, and behavior primitives with explicit capability limits.
- **Positive exceptions:** scoped counter-signals with measurable score reduction. `never_override_categories` prevents silent clearance of dangerous-product risk.
- **Policy packs:** versioned bundles of categories, signals, exceptions, deployment scope, owner, and status.

The catalog is seeded into DuckDB rather than hidden in UI copy. It is a candidate/demo governance overlay and is not the canonical runtime configuration for `deterministic_rules_v1`, whose audited taxonomy and evidence mappings remain in the existing scoring modules. The demo does not offer production publication: edits in Strategy Builder are hypothetical settings for a non-authoritative candidate.

Policy summaries link to public sources and assist interpretation; they are not legal advice or copied proprietary platform rules.
