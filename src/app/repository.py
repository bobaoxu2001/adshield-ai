from __future__ import annotations

import json
import math
import re
import statistics
import time
import uuid
from collections import Counter
from itertools import combinations
from datetime import UTC, datetime

import duckdb

from src.analytics.evaluate import evaluation_metrics
from src.analytics.metric_diagnosis import metric_diagnosis
from src.config import settings
from src.risk.comparison import rule_vs_llm_comparison
from src.risk.evidence_extractor import extract_evidence
from src.risk.evidence_extractor import CURATED_HOMOPHONE_VARIANTS, extract_multimodal_text_evidence
from src.risk.governance import Actor, PromotionEvidence, promotion_readiness, require_permission
from src.risk.lifecycle import (
    CANDIDATE_STRATEGY,
    CURRENT_STRATEGY,
    HOLDOUT_BENCHMARK_CASES,
    POLICY_PACKS,
    RISK_EXCEPTIONS,
    RISK_SIGNALS,
    RISK_TAXONOMY,
    STRATEGIES,
    curated_advertiser_profiles,
    decision_trace,
    evaluate_text,
    preview_candidate_strategy,
    run_benchmark,
    strategy_evaluation,
)
from src.risk.taxonomy import MANDARIN_TERMS
from src.risk.policy_retriever import retrieve_policy_rules
from src.risk.public_evidence import public_evidence_registry
from src.risk.scoring import score_case

VALID_DECISIONS = frozenset({
    "approve", "reject", "escalate", "wrong category", "false positive", "false negative",
    "relevant prior", "not relevant", "needs specialist review",
})

REQUIRED_TABLES = frozenset({
    "cfpb_complaints", "ftc_fraud_categories", "ads", "ad_risk_scores", "policy_rules",
    "risk_taxonomy_versions", "risk_signals", "risk_exceptions", "policy_packs",
    "strategy_versions", "curated_benchmark_cases", "strategy_shadow_results",
})

_CASE_TEXTS = """
    WITH case_texts AS (
      SELECT case_id, case_text, product, issue, state, 'CFPB' source_name, source_url FROM cfpb_complaints
      UNION ALL
      SELECT case_id, ad_text, 'Commercial ad', advertiser_name, NULL, 'Meta', source_url FROM ads
    )
"""

_CASE_FILTERS = """
    WHERE (? = '' OR lower(c.case_text) LIKE '%' || lower(?) || '%' OR lower(s.case_id) LIKE '%' || lower(?) || '%')
      AND (? = '' OR s.risk_category = ?)
      AND (? = '' OR s.severity = ?)
      AND (? = '' OR s.language = ?)
      AND (? = '' OR s.source = ?)
      AND (? = '' OR s.recommended_action = ?)
"""


def _case_filter_params(search: str, category: str, severity: str, language: str, source: str, action: str) -> list[object]:
    return [search, search, search, category, category, severity, severity, language, language, source, source, action, action]


def validate_feedback_decision(decision: str) -> str:
    """Return the decision if a reviewer is allowed to record it, else raise ValueError."""
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Unsupported reviewer decision: {decision!r}")
    return decision


def _connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    if not settings.db_path.exists():
        raise FileNotFoundError("Data mart is missing. Run `make ingest && make transform`.")
    return duckdb.connect(str(settings.db_path), read_only=read_only)


def _records(db: duckdb.DuckDBPyConnection, sql: str, params: list[object] | None = None) -> list[dict[str, object]]:
    cursor = db.execute(sql, params or [])
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def database_health() -> dict[str, object]:
    if not settings.db_path.exists():
        return {"ready": False, "missing_tables": sorted(REQUIRED_TABLES), "database_path": str(settings.db_path)}
    with duckdb.connect(str(settings.db_path), read_only=True) as db:
        present = {str(row[0]) for row in db.execute("SHOW TABLES").fetchall()}
    missing = sorted(REQUIRED_TABLES - present)
    return {"ready": not missing, "missing_tables": missing, "database_path": str(settings.db_path)}


def overview() -> dict[str, object]:
    with _connect() as db:
        counts = db.execute("SELECT (SELECT count(*) FROM cfpb_complaints), (SELECT count(*) FROM ftc_fraud_categories), (SELECT count(*) FROM ads), (SELECT count(*) FROM ad_risk_scores)").fetchone()
        high = db.execute("SELECT count(*) FROM ad_risk_scores WHERE risk_score >= 0.65").fetchone()[0]
        review = db.execute("SELECT count(*) FROM ad_risk_scores WHERE needs_human_review").fetchone()[0]
        auto_cases = db.execute("SELECT count(*) FROM ad_risk_scores WHERE NOT needs_human_review AND source = 'Meta'").fetchone()[0]
        latest = db.execute("SELECT max(evaluated_at) FROM ad_risk_scores").fetchone()[0]
        retrieval = db.execute("SELECT retrieval_path FROM cfpb_complaints LIMIT 1").fetchone()
    cfpb_count, ftc_count, ads_count, scored = map(int, counts)
    return {
        "total_real_records": cfpb_count + ftc_count + ads_count,
        "cases_analyzed": scored,
        "high_risk_cases": int(high),
        "high_risk_rate": round(high / scored, 3) if scored else 0,
        "review_queue_size": int(review),
        "estimated_minutes_saved": int(auto_cases) * 3,
        "last_updated": str(latest) if latest else None,
        "sources": [
            {"key": "ftc", "name": "FTC Consumer Sentinel", "records": ftc_count, "status": "loaded", "detail": "Official 2024 aggregate archive"},
            {"key": "cfpb", "name": "CFPB Complaints", "records": cfpb_count, "status": "loaded", "detail": (retrieval[0] if retrieval else "unknown").replace("_", " ")},
            {"key": "meta", "name": "Meta Ad Library", "records": ads_count, "status": "loaded" if ads_count else "optional", "detail": "Official API token required"},
        ],
    }


def cases(search: str = "", category: str = "", severity: str = "", language: str = "", source: str = "", action: str = "", limit: int = 200, offset: int = 0) -> list[dict[str, object]]:
    sql = _CASE_TEXTS + """
        SELECT s.case_id, s.source, s.case_date, s.language, s.risk_score, s.risk_category,
               s.severity, s.recommended_action, s.needs_human_review, s.decision_scope, s.confidence, c.case_text, c.product,
               c.issue, c.state, c.source_url
        FROM ad_risk_scores s JOIN case_texts c USING (case_id)
    """ + _CASE_FILTERS + " ORDER BY s.risk_score DESC, s.case_date DESC NULLS LAST LIMIT ? OFFSET ?"
    params = [*_case_filter_params(search, category, severity, language, source, action), limit, offset]
    with _connect() as db:
        return _records(db, sql, params)


def case_count(search: str = "", category: str = "", severity: str = "", language: str = "", source: str = "", action: str = "") -> int:
    sql = _CASE_TEXTS + """
        SELECT count(*)
        FROM ad_risk_scores s JOIN case_texts c USING (case_id)
    """ + _CASE_FILTERS
    with _connect() as db:
        return int(db.execute(sql, _case_filter_params(search, category, severity, language, source, action)).fetchone()[0])


_SINGLE_CASE_SQL = _CASE_TEXTS + """
    SELECT s.case_id, s.source, s.case_date, s.language, s.risk_score, s.risk_category,
           s.severity, s.recommended_action, s.needs_human_review, s.decision_scope, s.confidence, c.case_text, c.product,
           c.issue, c.state, c.source_url
    FROM ad_risk_scores s JOIN case_texts c USING (case_id)
    WHERE s.case_id = ?
"""


def case_detail(case_id: str) -> dict[str, object] | None:
    with _connect() as db:
        base_rows = _records(db, _SINGLE_CASE_SQL, [case_id])
    if not base_rows:
        return None
    base = base_rows[0]
    with _connect() as db:
        score = _records(db, "SELECT * FROM ad_risk_scores WHERE case_id = ?", [case_id])[0]
        rule_ids = json.loads(score.get("matched_policy_rule_ids_json") or "[]")
        policies = _records(db, "SELECT * FROM policy_rules WHERE rule_id IN (SELECT unnest(?::VARCHAR[]))", [rule_ids]) if rule_ids else []
        feedback = _records(db, "SELECT * FROM human_review_feedback WHERE case_id = ? ORDER BY created_at DESC", [case_id])
    score["evidence"] = json.loads(score.pop("evidence_json") or "[]")
    score["matched_policy_rule_ids"] = rule_ids
    detail = {**base, **score, "policies": policies, "feedback": feedback}
    detail["decision_trace"] = decision_trace(detail, CURRENT_STRATEGY)
    detail["shadow_evaluation"] = {
        "label": "Candidate shadow result — does not replace the authoritative deterministic decision.",
        "authoritative_action": detail["recommended_action"],
        "candidate": decision_trace(detail, CANDIDATE_STRATEGY),
    }
    return detail


def save_feedback(case_id: str, decision: str, notes: str = "", *, reviewer_id: str, reviewer_role: str = "reviewer") -> dict[str, object]:
    if not getattr(settings, "feedback_writable", True):
        raise PermissionError(
            "The public Vercel demo is a read-only evidence snapshot. "
            "Run the project locally to persist reviewer feedback."
        )
    actor = Actor(reviewer_id, reviewer_role)
    require_permission(actor, "review.submit")
    with _connect(read_only=False) as db:
        record = db.execute("SELECT source, decision_scope FROM ad_risk_scores WHERE case_id = ?", [case_id]).fetchone()
        if not record:
            raise LookupError(f"Unknown case_id: {case_id}")
        validate_feedback_decision(decision)
        source, decision_scope = record
        allowed = (
            {"relevant prior", "not relevant", "needs specialist review", "wrong category"}
            if str(source).upper() == "CFPB" or decision_scope == "risk_prior"
            else {"approve", "reject", "escalate", "wrong category", "false positive", "false negative"}
        )
        if decision not in allowed:
            raise ValueError(f"Decision {decision!r} is not permitted for {decision_scope} scope")
        payload = {"feedback_id": str(uuid.uuid4()), "case_id": case_id, "reviewer_decision": decision, "notes": notes, "created_at": datetime.now(UTC).isoformat()}
        db.execute("INSERT INTO human_review_feedback VALUES (?, ?, ?, ?, ?)", list(payload.values()))
        db.execute("""
            CREATE TABLE IF NOT EXISTS reviewer_identity_audit (
              feedback_id VARCHAR PRIMARY KEY, reviewer_id VARCHAR NOT NULL,
              reviewer_role VARCHAR NOT NULL, recorded_at TIMESTAMP NOT NULL
            )
        """)
        db.execute("INSERT INTO reviewer_identity_audit VALUES (?, ?, ?, ?)", [payload["feedback_id"], actor.actor_id, actor.role, payload["created_at"]])
    return {**payload, "reviewer_id": actor.actor_id, "reviewer_role": actor.role}


def metrics() -> dict[str, object]:
    return {**metric_diagnosis(), "evaluation": evaluation_metrics()}


def policies() -> list[dict[str, object]]:
    with _connect() as db:
        return _records(db, "SELECT * FROM policy_rules ORDER BY category, rule_id")


def llm_comparison(limit: int = 5, run_llm: bool = False) -> dict[str, object]:
    """Deterministic rule output vs. optional LLM output for a small sample of scored cases.

    The deterministic engine is always the default. A paid LLM call is made only when
    OPENAI_API_KEY is configured; otherwise the LLM column is an explicit empty state.
    """
    return rule_vs_llm_comparison(limit=limit, run_llm=run_llm)


def mandarin_lab() -> dict[str, object]:
    terms = [{"term": term, "pinyin": values[0], "gloss": values[1], "category": values[2]} for term, values in MANDARIN_TERMS.items()]
    examples = []
    for row in cases(limit=10000):
        matches = [term for term in MANDARIN_TERMS if term in (row.get("case_text") or "")]
        if matches:
            examples.append({"case_id": row["case_id"], "source": row["source"], "matches": matches, "excerpt": row["case_text"][:240]})
    return {
        "terms": terms,
        "real_record_examples": examples[:20],
        "tested_coverage": [
            {"capability": "literal", "status": "tested", "scope": f"{len(terms)} curated canonical terms"},
            {"capability": "normalized pinyin", "status": "tested", "scope": "canonical terms with explicit pinyin mappings"},
            {"capability": "split character", "status": "tested", "scope": "short punctuation or whitespace splits"},
            {"capability": "curated homophones", "status": "tested", "scope": f"{len(CURATED_HOMOPHONE_VARIANTS)} explicit variants"},
            {"capability": "OCR / ASR text", "status": "adapter ready", "scope": "authorized upstream text only; no raw-media claim"},
            {"capability": "novel homophones / cultural code words", "status": "human review", "scope": "not auto-promoted"},
        ],
        "curated_homophone_variants": [{"variant": variant, "canonical_term": values[0], "category": values[1]} for variant, values in CURATED_HOMOPHONE_VARIANTS.items()],
        "note": "Candidate v2.1 adds four tested, explicit homophone substitutions and provenance-preserving OCR/ASR text inputs. Novel variants and raw media still require bilingual or multimodal review.",
    }


def policy_studio() -> dict[str, object]:
    return {
        "data_scope": "hypothetical_simulation",
        "truth_boundary": "Original public-demo configuration informed by general governance patterns; not internal platform policy.",
        "taxonomy": RISK_TAXONOMY,
        "signals": RISK_SIGNALS,
        "exceptions": RISK_EXCEPTIONS,
        "policy_packs": POLICY_PACKS,
    }


def strategy_catalog() -> dict[str, object]:
    return {
        "authoritative_engine": "deterministic_rules_v1",
        "active_version": CURRENT_STRATEGY.to_dict(),
        "candidate_version": CANDIDATE_STRATEGY.to_dict(),
        "versions": [item.to_dict() for item in STRATEGIES],
        "lifecycle_states": ["draft", "shadow", "enforced", "paused", "retired"],
        "actions": ["allow", "hold", "escalate", "soft reject", "hard reject"],
        "guardrail": "Unvalidated candidate strategies can run only in simulation or shadow mode.",
    }


def benchmark_lab(include_results: bool = False) -> dict[str, object]:
    baseline = run_benchmark(CURRENT_STRATEGY)
    result = run_benchmark(CANDIDATE_STRATEGY)
    result["baseline"] = {key: baseline[key] for key in ("strategy_version", "category_agreement", "evidence_coverage", "routing_agreement", "false_positive_scenario_agreement", "promotion_gate")}
    result["comparison_note"] = "Candidate v2.1 was remediated against these same frozen 60 scenarios, so its agreement is development-set regression coverage rather than generalization. Passing this curated gate does not authorize production promotion."
    if not include_results:
        result.pop("results", None)
    return result


def multimodal_text_evaluation(creative_text: str, ocr_text: str | None = None, asr_text: str | None = None) -> dict[str, object]:
    return extract_multimodal_text_evidence(creative_text, ocr_text=ocr_text, asr_text=asr_text)


def holdout_benchmark() -> dict[str, object]:
    """Generalization estimate on a held-out set authored after v2.1 was frozen.

    The 60 curated scenarios are the development set v2.1 was tuned against; this set was
    not, so it estimates generalization rather than regression coverage. Numbers here are
    expected to be materially lower than the development-set gate — that gap is the point.
    """
    dev_v1 = run_benchmark(CURRENT_STRATEGY)
    dev_v21 = run_benchmark(CANDIDATE_STRATEGY)
    hold_v1 = run_benchmark(CURRENT_STRATEGY, cases=HOLDOUT_BENCHMARK_CASES)
    hold_v21 = run_benchmark(CANDIDATE_STRATEGY, cases=HOLDOUT_BENCHMARK_CASES)

    def summarize(result: dict[str, object]) -> dict[str, object]:
        return {
            "scenario_count": result["scenario_count"],
            "category_agreement": result["category_agreement"],
            "routing_agreement": result["routing_agreement"],
        }

    misses = [
        {
            "scenario_id": row["scenario_id"],
            "expected_category": row["expected_category"],
            "observed_category": row["evaluation"]["category"],
            "expected_routing": row["expected_routing"],
            "observed_routing": row["evaluation"]["recommended_action"],
            "category_agreement": row["category_agreement"],
            "routing_agreement": row["routing_agreement"],
        }
        for row in hold_v21["results"]
        if not row["category_agreement"] or not row["routing_agreement"]
    ]
    return {
        "data_scope": "holdout_generalization",
        "label": "Held-out scenarios authored after v2.1 was frozen; estimates generalization, not regression coverage.",
        "development_set": {"v1": summarize(dev_v1), "candidate_v2_1": summarize(dev_v21)},
        "holdout_set": {"v1": summarize(hold_v1), "candidate_v2_1": summarize(hold_v21)},
        "generalization_gap": {
            "category_agreement": round(float(dev_v21["category_agreement"]) - float(hold_v21["category_agreement"]), 3),
            "routing_agreement": round(float(dev_v21["routing_agreement"]) - float(hold_v21["routing_agreement"]), 3),
        },
        "readout": (
            "Candidate v2.1 still beats v1 on unseen scenarios, but agreement drops sharply from the "
            "development set. The gap is the honest cost of tuning rules against a fixed label set: most "
            "held-out misses are novel phrasings, slang, and non-keyword synonyms the deterministic "
            "matcher has no term for, which fall back to the default category."
        ),
        "holdout_misses": misses,
    }


def launch_readiness() -> dict[str, object]:
    candidate = run_benchmark(CANDIDATE_STRATEGY)
    with _connect() as db:
        authorized_ads = int(db.execute("SELECT count(*) FROM ads").fetchone()[0])
        feedback_count = int(db.execute("SELECT count(*) FROM human_review_feedback").fetchone()[0])
        tables = {str(item[0]) for item in db.execute("SHOW TABLES").fetchall()}
        identity_count = int(db.execute("SELECT count(*) FROM reviewer_identity_audit").fetchone()[0]) if "reviewer_identity_audit" in tables else 0
    # Existing feedback is single-reviewer product feedback. It is deliberately not
    # reclassified as independent ground truth.
    evidence = PromotionEvidence(
        candidate_version=CANDIDATE_STRATEGY.version_id,
        rollback_target=CURRENT_STRATEGY.version_id,
        category_agreement=float(candidate["category_agreement"]),
        routing_agreement=float(candidate["routing_agreement"]),
        exception_routing_agreement=float(candidate["false_positive_scenario_agreement"]),
        authorized_ad_records=authorized_ads,
        independently_labeled_ads=0,
        independent_label_agreement=None,
        reviewer_identity_coverage=round(identity_count / feedback_count, 3) if feedback_count else None,
        sla_compliance=None,
        policy_owner_approved=False,
    )
    readiness = promotion_readiness(evidence)
    public_evidence = public_evidence_registry()
    return {
        **readiness,
        "benchmark_gate": candidate["promotion_gate"],
        "observed_feedback_records": feedback_count,
        "rbac": {"implemented_roles": ["reviewer", "senior_reviewer", "queue_manager", "policy_owner", "release_manager", "auditor"], "default": "deny", "public_demo_mutations": "disabled"},
        "independent_labeling": {"minimum_reviewers": 2, "blind_until_minimum_labels": True, "disagreements_require_adjudication": True},
        "sla_monitoring": {"implemented": True, "status": "awaiting persisted review assignments"},
        "promotion_service": {"implemented": True, "automatic_promotion": False, "required_role": "release_manager", "rollback_target": CURRENT_STRATEGY.version_id, "audit_log": "append-only adapter contract"},
        "data_access": {"authorized_batch_validator": True, "persisted_authorized_ads": authorized_ads, "truth_boundary": "No authorized internal ads, enforcement labels, or advertiser history are present in this snapshot."},
        "public_evidence": {
            "real_ad_records": public_evidence["sources"][0]["records"],
            "independent_annotators": public_evidence["sources"][0]["independent_annotators"],
            "label_scope": public_evidence["sources"][0]["label_scope"],
            "promotion_eligible": False,
            "why": "External perception labels improve validation coverage but cannot replace platform policy-enforcement ground truth.",
        },
    }


def public_evidence() -> dict[str, object]:
    return public_evidence_registry()


def evaluate_strategies(assumptions: dict[str, float] | None = None) -> dict[str, object]:
    return strategy_evaluation(assumptions)


def preview_strategy(risk_threshold: float, escalation_threshold: float, reviewer_capacity: int) -> dict[str, object]:
    return preview_candidate_strategy(risk_threshold, escalation_threshold, reviewer_capacity)


def advertiser_integrity() -> dict[str, object]:
    with _connect() as db:
        real_profiles = _records(db, """
            SELECT a.advertiser_id, max(a.advertiser_name) display_name,
                   'authorized_public_ads' data_scope, count(*) total_creatives,
                   count(*) FILTER (WHERE s.needs_human_review) reviewed_creatives,
                   count(*) FILTER (WHERE s.recommended_action IN ('soft reject', 'hard reject')) rejected_creatives,
                   round(avg(CASE WHEN s.needs_human_review THEN 1.0 ELSE 0.0 END), 3) escalation_rate,
                   list(DISTINCT s.risk_category) repeated_risk_categories,
                   CASE WHEN max(s.risk_score) >= 0.85 THEN 'high' WHEN max(s.risk_score) >= 0.4 THEN 'medium' ELSE 'low' END integrity_risk_level
            FROM ads a JOIN ad_risk_scores s ON a.case_id = s.case_id
            GROUP BY a.advertiser_id
            ORDER BY max(s.risk_score) DESC
        """)
    for row in real_profiles:
        row.update({"recommended_analyst_action": "Inspect public creative-level evidence; no linked-entity relationship is inferred.", "associated_landing_pages": [], "off_platform_contact_signals": None, "similar_creative_clusters": None, "velocity_signals": None, "prior_reviewer_decisions": [], "appeal_or_reversal_status": "not available"})
    return {
        "real_public_profiles": real_profiles,
        "curated_benchmark_profiles": curated_advertiser_profiles(),
        "truth_boundary": "Curated advertisers are hypothetical benchmark entities. They are never mixed with real public ad profiles.",
        "layers": ["content-level", "campaign-level", "advertiser-level", "network-level (unavailable without authorized linkage data)"],
    }


def emerging_risks() -> dict[str, object]:
    with _connect() as db:
        rows = _records(db, """
            WITH evidence AS (
              SELECT case_date, language, source, risk_category,
                     json_extract_string(item.value, '$.term') term
              FROM ad_risk_scores, json_each(evidence_json) item
              WHERE case_date IS NOT NULL
            ), bounds AS (SELECT max(case_date) latest FROM evidence),
            counts AS (
              SELECT term, language, risk_category,
                     count(*) FILTER (WHERE case_date >= latest - INTERVAL 90 DAY) recent_count,
                     count(*) FILTER (WHERE case_date >= latest - INTERVAL 180 DAY AND case_date < latest - INTERVAL 90 DAY) baseline_count,
                     max(case_date) latest_seen
              FROM evidence, bounds WHERE term IS NOT NULL AND term <> ''
              GROUP BY term, language, risk_category
            )
            SELECT term emerging_signal, language, risk_category affected_category,
                   recent_count, baseline_count,
                   round((recent_count + 1.0) / (baseline_count + 1.0), 2) growth_ratio,
                   latest_seen
            FROM counts WHERE recent_count > baseline_count
            ORDER BY growth_ratio DESC, recent_count DESC LIMIT 20
        """)
        text_rows = _records(db, """
            WITH texts AS (
              SELECT s.case_date, s.source, s.risk_category, s.language, s.evidence_json, c.case_text
              FROM ad_risk_scores s JOIN cfpb_complaints c USING (case_id)
              WHERE s.case_date IS NOT NULL
            ), bounds AS (SELECT max(case_date) latest FROM texts)
            SELECT case_text, source, risk_category, language, evidence_json,
                   CASE WHEN case_date >= latest - INTERVAL 90 DAY THEN 'recent_90d' ELSE 'prior_90d' END period
              FROM texts, bounds WHERE case_date >= latest - INTERVAL 180 DAY
        """)
        mix = _records(db, """
            WITH bounds AS (SELECT max(case_date) latest FROM ad_risk_scores WHERE case_date IS NOT NULL)
            SELECT source, risk_category,
                   CASE WHEN case_date >= latest - INTERVAL 90 DAY THEN 'recent_90d' ELSE 'prior_90d' END period,
                   count(*) cases
            FROM ad_risk_scores, bounds WHERE case_date >= latest - INTERVAL 180 DAY
            GROUP BY source, risk_category, period ORDER BY period, cases DESC
        """)
        category_spikes = _records(db, """
            WITH bounds AS (SELECT max(case_date) latest FROM ad_risk_scores WHERE case_date IS NOT NULL), counts AS (
              SELECT risk_category,
                     count(*) FILTER (WHERE case_date >= latest - INTERVAL 90 DAY) recent_count,
                     count(*) FILTER (WHERE case_date >= latest - INTERVAL 180 DAY AND case_date < latest - INTERVAL 90 DAY) baseline_count
              FROM ad_risk_scores, bounds WHERE case_date IS NOT NULL GROUP BY risk_category
            )
            SELECT *, round((recent_count + 1.0) / (baseline_count + 1.0), 2) growth_ratio
            FROM counts ORDER BY growth_ratio DESC, recent_count DESC
        """)
    for row in rows:
        sample = next((str(item["case_text"])[:220] for item in text_rows if str(row["emerging_signal"]).lower() in str(item["case_text"]).lower()), None)
        row.update({"sample_evidence": sample, "evidence_strength": "descriptive" if row["recent_count"] < 5 else "moderate descriptive", "analyst_next_step": "investigate", "status": "candidate_only"})
    token_counts = {"recent_90d": Counter(), "prior_90d": Counter()}
    for item in text_rows:
        tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,4}", str(item["case_text"]).lower())
        ngrams = tokens + [f"{left} {right}" for left, right in zip(tokens, tokens[1:])]
        token_counts[str(item["period"])].update(ngrams)
    novel_ngrams = []
    for term, recent_count in token_counts["recent_90d"].most_common(100):
        baseline_count = token_counts["prior_90d"].get(term, 0)
        if recent_count >= 1 and recent_count > baseline_count:
            novel_ngrams.append({"term": term, "recent_count": recent_count, "baseline_count": baseline_count, "growth_ratio": round((recent_count + 1) / (baseline_count + 1), 2), "status": "candidate_only"})
        if len(novel_ngrams) == 20:
            break
    pair_counts = {"recent_90d": Counter(), "prior_90d": Counter()}
    for item in text_rows:
        terms = sorted({str(evidence.get("term") or "") for evidence in json.loads(str(item.get("evidence_json") or "[]")) if evidence.get("term")})
        pair_counts[str(item["period"])].update(" + ".join(pair) for pair in combinations(terms, 2))
    unusual_combinations = [{"evidence_combination": term, "recent_count": count, "baseline_count": pair_counts["prior_90d"].get(term, 0), "status": "candidate_only"} for term, count in pair_counts["recent_90d"].most_common(15) if count > pair_counts["prior_90d"].get(term, 0)]
    return {"data_scope": "real_public", "method": "Recent 90-day evidence and unigram/bigram counts versus the immediately preceding 90-day window, with additive smoothing.", "causality_note": "Descriptive prioritization only; discovered terms are never added to active policy automatically.", "candidates": rows, "novel_ngrams": novel_ngrams, "category_spikes": category_spikes, "unusual_evidence_combinations": unusual_combinations, "source_category_mix": mix}


def operational_performance(sample_size: int = 40) -> dict[str, object]:
    sample = cases(limit=min(sample_size, 100))
    measurements: dict[str, list[float]] = {"evidence_extraction": [], "policy_retrieval": [], "end_to_end_scoring_call": [], "total_pipeline": []}
    failures = 0
    for row in sample:
        pipeline_started = time.perf_counter()
        try:
            text = str(row.get("case_text") or "")
            started = time.perf_counter()
            extract_evidence(text)
            measurements["evidence_extraction"].append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            retrieve_policy_rules(str(row.get("risk_category") or ""))
            measurements["policy_retrieval"].append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            score_case(str(row["case_id"]), text, str(row.get("product") or ""), str(row["source"]))
            measurements["end_to_end_scoring_call"].append((time.perf_counter() - started) * 1000)
        except Exception:
            failures += 1
        measurements["total_pipeline"].append((time.perf_counter() - pipeline_started) * 1000)
    def percentile(values: list[float], quantile: float) -> float:
        ordered = sorted(values)
        if not ordered:
            return 0.0
        index = min(len(ordered) - 1, max(0, math.ceil(quantile * len(ordered)) - 1))
        return round(ordered[index], 3)
    stages = {name: {"p50_latency_ms": percentile(values, 0.5), "p95_latency_ms": percentile(values, 0.95), "p99_latency_ms": percentile(values, 0.99), "measurement_count": len(values)} for name, values in measurements.items()}
    total_ms = sum(measurements["total_pipeline"])
    total = stages["total_pipeline"]
    return {"measurement_scope": "local_request_benchmark", "traffic_claim": "Measured on this request; not production-scale traffic.", "request_count": len(sample), **{key: total[key] for key in ("p50_latency_ms", "p95_latency_ms", "p99_latency_ms")}, "stages": stages, "stage_notes": {"evidence_extraction": "Isolated evidence-extraction call.", "policy_retrieval": "Isolated policy-retrieval call.", "end_to_end_scoring_call": "Complete deterministic score_case call, including its own extraction and policy lookup.", "total_pipeline": "Measurement harness total: isolated checks plus the complete scoring call."}, "timeout_count": 0, "failure_count": failures, "throughput_cases_per_second": round(len(sample) / max(total_ms / 1000, 0.001), 2), "estimated_cost_per_reviewed_case": 0.0, "cost_note": "Deterministic local execution; optional paid LLM cost is excluded unless explicitly run."}


def system_provenance() -> dict[str, object]:
    return {"data_scopes": {"real_public": "FTC aggregate records and scrubbed CFPB complaint records used for research priors.", "external_independent_validation": "UW real-web-ad perception aggregates from independent research participants; never enforcement ground truth.", "authorized_public_ads": "Meta or TikTok commercial-content creatives only when an authorized token produced records.", "curated_benchmark": "Hypothetical labeled evaluation scenarios, isolated from real-data KPIs.", "hypothetical_simulation": "Editable strategy and business assumptions, never observed values.", "test_fixture": "Automated-test records only."}, "controls": ["CFPB actions are restricted to research-prior routing", "External opinion labels cannot satisfy internal enforcement-label gates", "Benchmark rows are not queried by real-public KPI endpoints", "Candidate strategy results are stored and displayed separately", "Precision, recall, and F1 remain empty without eligible reviewer labels", "LLM calls require both an API key and an explicit user action"], "deployment_mode": "public_read_only_snapshot" if settings.public_demo else "local_writable_mart"}
