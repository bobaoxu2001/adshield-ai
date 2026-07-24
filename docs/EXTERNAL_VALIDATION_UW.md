# External Validation — UW CHI 2021 Ad Perceptions

## What this dataset is

The [UW CHI 2021 Ad Perceptions dataset](https://badads.cs.washington.edu/datasets.html) contains
500 real web ads, each rated by a subset of 1,025 independent participants (5,104 rating
observations). For every ad it records participant opinion-label shares (`deceptive`, `clickbait`,
`manipulative`, `trustworthy`, `unclear`, `distasteful`), content-category tags, a 1–7 overall
rating, and free-text comments.

Only derived aggregate statistics are stored in this repository
([`data/public_validation/uw_bad_ads_summary.json`](../data/public_validation/uw_bad_ads_summary.json)).
No ad image, participant comment, or row-level label is redistributed.

## Why the engine does not score these ads

Each ad row is an **image screenshot** (`screenshot: "<id>.webp"`) with **no ad copy** — the fields
are `opinion_label_dist`, `content_labels`, `ratings`, `comments`, `screenshot`. The deterministic
engine in this project matches **text**, and the project explicitly does not perform OCR or vision.
Running the engine over these ads would therefore require capabilities the project deliberately does
not claim, so **no per-ad engine-vs-human agreement is reported.** Reporting one would be fabricated.

## What is validated instead: category-level alignment

The dataset can still answer a real risk-strategy question: **do independent humans perceive the most
deception in the same categories this project prioritizes?** For every content category with at least
15 ads, the ingest step aggregates mean annotator deception and clickbait share (see
`_perception_by_content_category` in [`src/ingest/fetch_uw_bad_ads.py`](../src/ingest/fetch_uw_bad_ads.py)).

Highest independently-perceived deception / clickbait:

| Content category | Ads | Mean deceptive | Mean clickbait | Mapped risk category |
|---|---:|---:|---:|---|
| Listicle | 29 | 0.34 | 0.70 | Deceptive / Misleading Claims |
| Health and Supplements | 29 | 0.45 | 0.57 | Health / Weight Loss / Pharmaceuticals Risk |
| Advertorial | 42 | 0.38 | 0.55 | Deceptive / Misleading Claims |
| Native | 90 | 0.34 | 0.57 | Deceptive / Misleading Claims |
| Software Download | 24 | 0.42 | 0.33 | (format-level deception vector) |

Lowest independently-perceived deception: Journalism (0.07), Self-Link (0.07), Apparel (0.09),
B2B Products (0.11).

## Finding

The two risk areas the taxonomy most emphasizes — **Health / Weight Loss / Pharmaceuticals** and
**Deceptive / Misleading Claims** — are exactly where 1,025 independent annotators perceive the most
deception and clickbait. Categories the taxonomy does not prioritize (journalism, apparel, B2B) draw
the least. This is **external, independent corroboration of the taxonomy's risk ranking at the
category level.**

## Boundaries

- This is category-level corroboration, **not** per-ad enforcement agreement, precision, or recall.
- Participant opinions are perceptions, **not** platform policy-violation ground truth.
- These ads are not TikTok ads and confer **no** production-promotion eligibility
  (`promotion_gate_effect: informative_only`).
- The mapping from UW content categories to this taxonomy is an analyst judgment, documented in
  `UW_TO_TAXONOMY`, not a label supplied by the dataset.
