# Real Ads Enrichment (Meta Ad Library)

AdShield AI is built around **real public data**. By default it runs on public FTC and CFPB risk
cases. When official Meta Ad Library credentials are supplied, it additionally ingests **real ad
creatives** so the queue contains genuine commercial ad text alongside the consumer-harm priors.

This document explains exactly how that enrichment works, what is queried, where files land, how many
records the current run retrieved, and — importantly — what happens honestly when no token is present.

> **Secret handling.** Your access token is a secret. Paste it **only** into your local `.env`
> (which is git-ignored). The tooling here never prints, logs, or commits the token, and it strips
> the token out of saved API responses and error messages.

## What the default (no-token) demo uses

| Mode | Data in the dashboard | Requires |
|---|---|---|
| **Default demo** | Public **FTC** fraud aggregates + **CFPB** consumer complaints, scored as risk *priors* | No keys |
| **+ Meta enrichment** | Above **plus real ad creatives** from the official Meta Ad Library API | `META_ACCESS_TOKEN` |

The default demo is fully functional with **no credentials**: ingestion, normalization, evidence
extraction, scoring, policy retrieval, analytics, feedback, and the full dashboard all run on real
public FTC/CFPB records. Meta enrichment only adds a second, complementary kind of real data — actual
ad creative examples — when a token is available.

## How to get real ad creatives

A step-by-step path using **only official Meta pages**. Several steps are manual UI actions that only
you can complete — where that happens, the checklist says exactly what to click.

### 1. Set up Meta developer access (official pages only)

1. **Confirm your Facebook identity/location (if prompted).** The Ad Library API requires a confirmed
   identity for some ad categories/regions. Start at the Ad Library
   (<https://www.facebook.com/ads/library/>); if asked, complete ID/location confirmation at
   <https://www.facebook.com/ID> (this is a manual Meta flow — follow Meta's on-screen steps).
2. **Create a Meta for Developers account.** Go to <https://developers.facebook.com/>, click
   **Get Started / Log in**, and accept the developer terms. *(Manual UI action.)*
3. **Create a developer app.** Go to <https://developers.facebook.com/apps/>, click **Create App**,
   and choose a generic type (e.g. **Other → Business**). *(Manual UI action.)*
4. **Open the Ad Library API access flow.** See the official docs at
   <https://www.facebook.com/ads/library/api/> and the Graph API Explorer at
   <https://developers.facebook.com/tools/explorer/>.
5. **Generate an access token.** In Graph API Explorer, select your app, then **Generate Access
   Token**. The Ad Library `ads_archive` endpoint works with a standard user/app token from a
   confirmed account; you do **not** need elevated political-ads permissions for commercial
   (`ALL`/financial/employment/housing) ad types. *(Manual UI action — Meta shows the token once.)*
6. **Copy the token manually into `.env`.** Do **not** paste it into chat or any shared tool. Open
   your local `.env` and set `META_ACCESS_TOKEN=...`.

> If any Meta page differs from the above (Meta changes its UI periodically), **stop** and follow the
> on-screen instructions; the only thing this project needs is a working token in `.env`.

### 2. Put the token in `.env`

```bash
cp .env.example .env
# edit .env and set META_ACCESS_TOKEN=...  (UK/EU countries are the default)
```

`.env` is git-ignored — it will not be committed.

### 3. Verify the token with one safe call

```bash
make check-meta-token
```

This runs a single small query (`country=GB`, `ad_type=FINANCIAL_PRODUCTS_AND_SERVICES_ADS`,
`search_terms=loan`) and prints whether it succeeded, how many records came back, how many had
creative text, and the first three results. It **never prints the token**, and on an API error it
prints the message plus a likely fix.

### 4. Ingest, transform, and run

```bash
make ingest && make transform && make app
```

Then open the dashboard at <http://127.0.0.1:8501>, go to the **Command Center**, and confirm the
**Meta Ad Library** source now shows a non-zero record count (it shows *optional* / 0 without a token).

## How enrichment works when `META_ACCESS_TOKEN` is provided

Implemented in [`src/ingest/fetch_meta_ads.py`](../src/ingest/fetch_meta_ads.py):

1. The fetcher reads `META_ACCESS_TOKEN`, `META_GRAPH_API_VERSION` (default `v23.0`),
   `META_AD_COUNTRIES` (default `GB,IE,FR,DE,NL,ES,IT`), `META_AD_TYPES`
   (default `FINANCIAL_PRODUCTS_AND_SERVICES_ADS,EMPLOYMENT_ADS,HOUSING_ADS,ALL`), and
   `META_MAX_PAGES_PER_QUERY` (default `3`).
2. It iterates over every **country × ad_type × keyword** combination and calls the official endpoint
   `https://graph.facebook.com/<version>/ads_archive` with `limit=100` and the country in
   `ad_reached_countries`.
3. It requests public creative fields:
   `id, ad_creation_time, ad_creative_bodies, ad_creative_link_captions,
   ad_creative_link_descriptions, ad_creative_link_titles, ad_snapshot_url, page_id, page_name,
   publisher_platforms, ad_delivery_start_time, ad_delivery_stop_time` plus best-effort
   `languages, eu_total_reach`. If a query rejects an optional field, it retries once with the core
   field set.
4. It **follows pagination** up to `META_MAX_PAGES_PER_QUERY` pages per query.
5. Each page is written to disk; a per-run **manifest** records counts and any failed queries. The
   `ALL` ad type is the safe fallback — special categories (financial/employment/housing) are not
   available in every country, so unsupported combinations are recorded in `failed_queries` and the
   run continues.
6. [`src/transform/normalize_ads.py`](../src/transform/normalize_ads.py) reads only the `data` arrays,
   concatenates the creative text fields, attaches country/ad_type/keyword/snapshot/languages/
   eu_total_reach, drops empty creatives, de-dupes by `ad_id`, and writes the normalized `ads` table.

Normalized ads are then scored by the same deterministic engine as every other case (see
[`RISK_SCORING_METHODOLOGY.md`](RISK_SCORING_METHODOLOGY.md)) with a lower source prior, because a
general commercial ad is not pre-filtered for risk the way a CFPB complaint is.

> **Volume note.** Countries × ad types × keywords × pages can be hundreds of API calls and may hit
> Meta rate limits. Narrow `META_AD_COUNTRIES` / `META_AD_TYPES` or lower `META_MAX_PAGES_PER_QUERY`
> for a quicker run.

## Which keywords are queried

The keyword list lives in `KEYWORDS` in [`src/ingest/fetch_meta_ads.py`](../src/ingest/fetch_meta_ads.py):

```
financial scam, loan, investment, crypto, weight loss, supplement, pharmacy,
immigration, job offer, gambling, AI tool, miracle cure, debt relief, credit repair
```

These mirror the risk taxonomy (financial scams, health/weight-loss, gambling, deceptive offers) so
the retrieved creatives are relevant to the categories the engine triages.

## Where raw files are stored

```
data/raw/meta_ads/<UTC timestamp>/
    manifest.json                                  # run metadata (see below)
    GB__ALL__loan__p1.json                         # one file per country__ad_type__keyword__page
    GB__ALL__loan__p2.json
    GB__FINANCIAL_PRODUCTS_AND_SERVICES_ADS__loan__p1.json
    IE__ALL__crypto__p1.json
    ...
```

- The filename encodes **country, ad_type, keyword, and page number**.
- Each file stores a small `_query` annotation plus Meta's verbatim `data` array. The pagination
  `next` URL (which contains your token) is **deliberately not persisted** — only a `has_next` flag.
- Each run gets its own timestamped folder, so runs are reproducible and never overwrite history.
- Normalized output is written to `data/processed/ads.parquet` and loaded into the DuckDB `ads` table.
- Both `data/raw/` and `data/processed/` are **Git-ignored**.

The per-run `manifest.json` records:

```
source, endpoint, retrieved_at, status, total_records, total_nonempty_creatives,
countries, ad_types, keywords, per_query_counts, failed_queries
```

`per_query_counts` lists `{country, ad_type, keyword, pages, records, nonempty_creatives}` for each
successful query; `failed_queries` lists `{country, ad_type, keyword, error, likely_fix}` (with the
token scrubbed). `status` is one of `complete`, `complete_no_records` (with a `warning`), or
`skipped_no_token`.

## How many records the current run retrieved

The repository's most recent ingestion ran **without** a `META_ACCESS_TOKEN`. The current manifest at
`data/raw/meta_ads/<timestamp>/manifest.json` has `status: "skipped_no_token"`, `total_records: 0`,
and the UK/EU `countries`/`ad_types` it *would* query. So the current run retrieved **0 real ad
records**, and `data/processed/ads.parquet` contains **0 rows**. The dashboard therefore shows the
Meta source as *optional*. To populate real creatives, add a token and re-run
`make ingest && make transform`.

## What happens honestly when no token / no records

- **No token:** the fetcher writes a transparent `skipped_no_token` manifest (`total_records: 0`) and
  **continues** — the pipeline does not fail.
- **Token but 0 records:** the manifest `status` is `complete_no_records` and a clear `warning`
  explains the likely causes (token scope, identity confirmation, ad_type/country availability).
- **Normalization never fabricates.** `normalize_ads()` produces an **empty `ads` table with the full
  schema** — it never invents placeholder advertisers, fake creatives, or synthetic ad text. (Covered
  by `tests/test_normalize_ads.py`.)
- The dashboard's Command Center marks the Meta source as `optional` rather than `loaded`, and
  surfaces the real record count (0).

No fabricated or scraped ad data is ever substituted into real-data tables or KPIs. Synthetic test text lives in
`tests/fixtures/` (all ids prefixed `test-`), while 60 separately scoped hypothetical cases live only in the
`curated_benchmark` evaluation catalog. Neither scope enters real-public dashboard metrics.

## Related docs

- [Risk Scoring Methodology](RISK_SCORING_METHODOLOGY.md) — how each ad is scored once ingested.
- [Evaluation Report](EVALUATION_REPORT.md) — current metrics and rule-vs-LLM comparison.
