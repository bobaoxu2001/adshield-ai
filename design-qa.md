# Design QA — AdShield AI Command Center

- Visual source of truth: `docs/screenshots/reference-command-center.png`
- Current captures: `docs/screenshots/current-command-center.png`, `current-review-queue.png`, `current-investigation-desk.png`, and `current-metric-diagnosis.png`
- Desktop review viewport: 1440 × 1024
- Data state: current public FTC/CFPB mart; Meta data and human labels are absent and shown as explicit empty states

## Result

The current build preserves the selected Command Center shell: fixed navy navigation, compact enterprise typography, provenance-first hierarchy, restrained semantic colors, and dense operational tables. The real-data distribution is intentionally more concentrated than the illustrative reference.

No blocking visual mismatch remains. The production build now separates chart and icon dependencies and completes without the earlier oversized-chunk warning.

## Evidence checked in the running app

- Command Center shows 1,039 public records, 956 analyzed cases, source provenance, and the absent Meta enrichment state without invented values.
- Review Queue searches the complete mart and paginates 956 cases. A case outside the former 500-row client subset (`cfpb-6572773`) was found as `1–1 of 1`.
- Investigation Desk distinguishes a CFPB complaint signal from an ad decision, uses research-only actions, and exposes source-appropriate feedback choices.
- Metric Diagnosis shows source-mix concentration, the strongest differentiating feature, spike flags, feature lift, evaluation coverage, and the explicit no-key LLM state.
- The drawer exposes dialog semantics and an accessible close name. Browser verification confirmed focus enters the dialog, Escape closes it, and focus returns to the invoking case button.
- Navigation buttons retain accessible names at compact widths.

## Evidence limits

This QA used browser DOM inspection, keyboard behavior checks, screenshots, API checks, and responsive captures already stored in the repository. It did not run a screen reader, automated axe suite, contrast analyzer, browser-zoom matrix, or reduced-motion audit. No WCAG-compliance claim is made.

## Implementation checklist

- [x] Match the selected Command Center shell and information hierarchy.
- [x] Use public-source values rather than illustrative or synthetic dashboard data.
- [x] Preserve Investigation Desk and Metric Diagnosis workflows.
- [x] Make complaint-derived records research priors rather than enforcement decisions.
- [x] Add complete-mart queue search and pagination.
- [x] Add dialog semantics, Escape handling, focus containment, and focus restoration.
- [x] Keep optional LLM comparison failure-isolated and off until explicitly requested.
- [x] Capture the final desktop states after the latest build.

Final result: passed within the evidence limits above.
