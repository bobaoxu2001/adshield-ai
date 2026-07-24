# Public Evidence Register

AdShield AI uses public evidence only when the label meaning, access authority, and permitted claim remain attached to the record. Public availability is not treated as permission to relabel a dataset or bypass a production control.

## Integrated now: UW CHI 2021 Ad Perceptions

The University of Washington Security and Privacy Lab publishes a research dataset of 500 real web advertisements labeled by 1,025 participants. Each ad has at least 10 independent ratings and opinion-label distributions including deceptive, clickbait, manipulative, trustworthy, unclear, and distasteful.

AdShield verifies the frozen source file at commit `9dd424e1ed4ec6a781d25f0d4a3ba97fbe3c3e40` and records its SHA-256 hash. The deployed product contains only derived aggregate statistics:

- 500 real web ads;
- 1,025 reported unique annotators;
- 5,104 rating observations;
- annotator-share and majority counts for six opinion labels;
- top researcher-generated content labels.

The source repository exposes no separate license file at the pinned commit. AdShield therefore does not redistribute screenshots, participant comments, participant context, raw responses, or row-level labels. The source remains the University of Washington [dataset page](https://badads.cs.washington.edu/datasets.html) and [research repository](https://github.com/eric-zeng/chi-bad-ads-data).

### Claim boundary

These are independent participant perceptions of real web ads. They are not:

- TikTok ads;
- platform enforcement actions;
- policy-violation ground truth;
- advertiser account history;
- evidence for production precision, recall, false-positive rate, or false-negative rate.

The dataset improves external-validation breadth but has `promotion_gate_effect: informative_only`.

## Connector ready: TikTok Commercial Content API

`src/ingest/fetch_tiktok_commercial_ads.py` implements TikTok's official `POST /v2/research/adlib/ad/query/` contract with the `research.adlib.basic` scope. It requests public ad dates, status, status statement, image/video URLs, reach, and public advertiser metadata, follows the API's `search_id` pagination, and stores token-free raw pages plus a manifest.

Without an approved `TIKTOK_RESEARCH_ACCESS_TOKEN`, it writes `skipped_approval_token_required`, returns zero records, and never substitutes scraped or fabricated ads. API access is public-facing but approval-gated; a qualifying research application is still required.

## Identity is not a public-data problem

A public list of people cannot prove who performed a production review. Production identity must come from an organization-owned identity provider that cryptographically verifies the user and maps governed role claims. The public deployment therefore keeps identity status `not_configured`; declared local reviewer IDs are not described as authentication.

## SLA evidence must be observed here

The scheduled `Production evidence monitor` checks the deployed health, benchmark, and public-evidence endpoints every six hours and uploads a timestamped GitHub Actions artifact. Those observations measure external API reachability only.

Reviewer decision SLA requires real persisted assignment, due, submission, and adjudication timestamps. It cannot be borrowed from another public service. AdShield does not report an availability percentage from the product until at least 28 external observations exist, and even then it remains an observed reachability rate rather than a contractual SLA.

