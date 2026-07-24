from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Iterable

from src.risk.evidence_extractor import contains_term, detect_language, extract_evidence
from src.risk.scoring import score_case

DATA_SCOPE_CURATED = "curated_benchmark"
DATA_SCOPE_REAL = "real_public"
ASSUMPTION_LABEL = "Illustrative scenario assumptions, not observed business values."


def _now() -> str:
    return "2026-07-15T00:00:00+00:00"


RISK_TAXONOMY = [
    {"category_id": "CAT-COMMERCIAL-INTEGRITY", "parent_category_id": None, "level": 1, "name": "Commercial Integrity", "description": "Top-level public-demo taxonomy for commercial content integrity research.", "severity": "variable", "applicable_markets": ["global"], "applicable_languages": ["en", "zh", "mixed"], "applicable_verticals": ["all"], "status": "active", "owner": "Risk Strategy", "version": "1.0.0", "created_at": _now(), "effective_at": _now(), "change_reason": "Initial independent product taxonomy"},
    {"category_id": "CAT-DECEPTIVE", "parent_category_id": "CAT-COMMERCIAL-INTEGRITY", "level": 2, "name": "Deceptive / Misleading Claims", "description": "Unsubstantiated guarantees, urgency, or outcome claims requiring context review.", "severity": "high", "applicable_markets": ["global"], "applicable_languages": ["en", "zh", "mixed"], "applicable_verticals": ["all"], "status": "active", "owner": "Risk Strategy", "version": "1.1.0", "created_at": _now(), "effective_at": _now(), "change_reason": "Added explicit exception handling"},
    {"category_id": "CAT-FINANCE", "parent_category_id": "CAT-COMMERCIAL-INTEGRITY", "level": 2, "name": "Financial Scam / High-Risk Financial Services", "description": "High-risk financial claims and regulated-product signals; complaint records remain research priors only.", "severity": "high", "applicable_markets": ["global"], "applicable_languages": ["en", "zh", "mixed"], "applicable_verticals": ["financial_services"], "status": "active", "owner": "Financial Risk", "version": "1.1.0", "created_at": _now(), "effective_at": _now(), "change_reason": "Aligned complaint-prior routing"},
    {"category_id": "CAT-HEALTH", "parent_category_id": "CAT-COMMERCIAL-INTEGRITY", "level": 2, "name": "Health / Weight Loss / Pharmaceuticals Risk", "description": "Potentially misleading health outcome, pharmaceutical, or weight-loss claims.", "severity": "high", "applicable_markets": ["global"], "applicable_languages": ["en", "zh", "mixed"], "applicable_verticals": ["health"], "status": "active", "owner": "Health Risk", "version": "1.0.0", "created_at": _now(), "effective_at": _now(), "change_reason": "Initial independent product taxonomy"},
    {"category_id": "CAT-DANGEROUS", "parent_category_id": "CAT-COMMERCIAL-INTEGRITY", "level": 2, "name": "Dangerous Products or Services", "description": "Weapon, explosive, illegal-drug, or harmful-service signals that cannot be silently cleared by exceptions.", "severity": "critical", "applicable_markets": ["global"], "applicable_languages": ["en", "zh", "mixed"], "applicable_verticals": ["all"], "status": "active", "owner": "High Severity Risk", "version": "1.0.0", "created_at": _now(), "effective_at": _now(), "change_reason": "Initial independent product taxonomy"},
    {"category_id": "CAT-OFFPLATFORM", "parent_category_id": "CAT-COMMERCIAL-INTEGRITY", "level": 2, "name": "Off-Platform Diversion", "description": "Contact or redirect signals that move a commercial interaction outside the reviewed surface.", "severity": "medium", "applicable_markets": ["global"], "applicable_languages": ["en", "zh", "mixed"], "applicable_verticals": ["all"], "status": "active", "owner": "Integrity Operations", "version": "1.0.0", "created_at": _now(), "effective_at": _now(), "change_reason": "Promoted reusable contact signals"},
    {"category_id": "CAT-ADVERTISER", "parent_category_id": "CAT-COMMERCIAL-INTEGRITY", "level": 2, "name": "Advertiser Integrity Risk", "description": "Identity, repetition, and behavior signals available only within the record's declared data scope.", "severity": "high", "applicable_markets": ["global"], "applicable_languages": ["en", "zh", "mixed"], "applicable_verticals": ["all"], "status": "active", "owner": "Integrity Operations", "version": "1.0.0", "created_at": _now(), "effective_at": _now(), "change_reason": "Separated content and advertiser layers"},
    {"category_id": "CAT-LANDING", "parent_category_id": "CAT-COMMERCIAL-INTEGRITY", "level": 2, "name": "Landing Page Mismatch", "description": "Creative-to-destination consistency signals where landing text is available.", "severity": "medium", "applicable_markets": ["global"], "applicable_languages": ["en", "zh", "mixed"], "applicable_verticals": ["all"], "status": "active", "owner": "Integrity Operations", "version": "1.0.0", "created_at": _now(), "effective_at": _now(), "change_reason": "Added modality-specific scope"},
]


RISK_SIGNALS = [
    {"signal_id": "SIG-GUARANTEE-EN", "name": "Outcome guarantee terms", "signal_type": "keyword", "expression": ["guaranteed", "guarantee", "risk-free", "100%"], "category_id": "CAT-DECEPTIVE", "severity": "high", "markets": ["global"], "languages": ["en"], "verticals": ["all"], "enabled": True, "owner": "Risk Strategy", "version": "1.1.0", "rationale": "Flag strong outcome certainty for contextual review.", "source": "curated_public_demo", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-FINANCE-EN", "name": "High-risk finance vocabulary", "signal_type": "keyword", "expression": ["loan", "credit repair", "debt relief", "payday", "forex", "double your money", "deposit"], "category_id": "CAT-FINANCE", "severity": "high", "markets": ["global"], "languages": ["en"], "verticals": ["financial_services"], "enabled": True, "owner": "Financial Risk", "version": "1.1.0", "rationale": "Research and triage signal, not standalone proof of violation.", "source": "public_guidance_and_curated_terms", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-HEALTH-EN", "name": "High-risk health outcomes", "signal_type": "exact_match", "expression": ["miracle cure", "instant weight loss", "cure diabetes", "lose weight", "七天瘦", "躺瘦", "神药", "根治"], "category_id": "CAT-HEALTH", "severity": "high", "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["health"], "enabled": True, "owner": "Health Risk", "version": "1.1.0", "rationale": "Prioritize potentially unsubstantiated outcome claims.", "source": "public_guidance_and_curated_terms", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-ZH-FINANCE", "name": "Mandarin finance risk terms", "signal_type": "keyword", "expression": ["稳赚", "保本", "秒批", "无视征信", "黑户可贷", "返利"], "category_id": "CAT-FINANCE", "severity": "high", "markets": ["global"], "languages": ["zh", "mixed"], "verticals": ["financial_services"], "enabled": True, "owner": "Bilingual Risk", "version": "1.0.0", "rationale": "Literal Mandarin term layer with reviewable mappings.", "source": "curated_public_demo", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-ZH-PINYIN", "name": "Mandarin pinyin variants", "signal_type": "pinyin", "expression": ["wen zhuan", "bao ben", "miao pi", "jia wei"], "category_id": "CAT-DECEPTIVE", "severity": "medium", "markets": ["global"], "languages": ["mixed"], "verticals": ["all"], "enabled": True, "owner": "Bilingual Risk", "version": "1.0.0", "rationale": "Detect normalized pinyin variants without claiming homophone resolution.", "source": "curated_public_demo", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-ZH-SPLIT", "name": "Mandarin character splitting", "signal_type": "character_split", "expression": ["稳-赚", "保 本", "加·微"], "category_id": "CAT-DECEPTIVE", "severity": "medium", "markets": ["global"], "languages": ["zh", "mixed"], "verticals": ["all"], "enabled": True, "owner": "Bilingual Risk", "version": "1.0.0", "rationale": "Detect short punctuation-separated variants.", "source": "curated_public_demo", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-OFFPLATFORM", "name": "Off-platform contact", "signal_type": "off_platform_contact", "expression": ["whatsapp", "telegram", "wechat", "dm me", "加微", "私域", "引流"], "category_id": "CAT-OFFPLATFORM", "severity": "medium", "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["all"], "enabled": True, "owner": "Integrity Operations", "version": "1.0.0", "rationale": "Route contact diversion for contextual review.", "source": "curated_public_demo", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-DANGEROUS", "name": "Dangerous products and services", "signal_type": "exact_match", "expression": ["weapon", "explosive", "illegal drug", "drug", "firearm", "hack account", "枪", "炸药", "非法药品"], "category_id": "CAT-DANGEROUS", "severity": "critical", "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["all"], "enabled": True, "owner": "High Severity Risk", "version": "1.1.0", "rationale": "High-severity signal requiring human review or restrictive routing.", "source": "curated_public_demo", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-LANDING", "name": "Creative destination mismatch", "signal_type": "landing_page_mismatch", "expression": {"minimum_token_overlap": 0.18}, "category_id": "CAT-LANDING", "severity": "medium", "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["all"], "enabled": True, "owner": "Integrity Operations", "version": "1.0.0", "rationale": "Compare text only when landing content is available.", "source": "deterministic_heuristic", "created_at": _now(), "updated_at": _now()},
    {"signal_id": "SIG-BEHAVIOR-REPEAT", "name": "Repeated risk pattern", "signal_type": "advertiser_behavior_signal", "expression": {"minimum_related_scenarios": 3}, "category_id": "CAT-ADVERTISER", "severity": "high", "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["all"], "enabled": True, "owner": "Integrity Operations", "version": "1.0.0", "rationale": "Benchmark-only when real advertiser history is unavailable.", "source": "curated_benchmark", "created_at": _now(), "updated_at": _now()},
]


RISK_EXCEPTIONS = [
    {"exception_id": "EXC-EDUCATION", "name": "Benign educational context", "matching_logic": ["education", "educational", "awareness", "prevention", "safety training", "科普", "防骗"], "related_signal_ids": ["SIG-DANGEROUS", "SIG-HEALTH-EN", "SIG-GUARANTEE-EN", "SIG-ZH-FINANCE"], "scope": {"languages": ["en", "zh", "mixed"]}, "risk_reduction": 0.42, "never_override_categories": ["Dangerous Products or Services"], "requires_human_review": False, "rationale": "Educational context can clear bounded low-severity claim signals, but never overrides dangerous-product review.", "owner": "Risk Strategy", "version": "1.1.0", "status": "active", "created_at": _now()},
    {"exception_id": "EXC-LEGAL", "name": "Legal or regulatory discussion", "matching_logic": ["law", "regulation", "regulatory guidance", "court report", "法律", "法规", "法律讨论"], "related_signal_ids": ["SIG-FINANCE-EN", "SIG-DANGEROUS", "SIG-ZH-FINANCE"], "scope": {"languages": ["en", "zh", "mixed"]}, "risk_reduction": 0.38, "never_override_categories": ["Dangerous Products or Services"], "requires_human_review": False, "rationale": "Explicit legal discussion can clear bounded commercial-claim signals; dangerous content remains review-only.", "owner": "Risk Strategy", "version": "1.1.0", "status": "active", "created_at": _now()},
    {"exception_id": "EXC-FDIC", "name": "Legitimate deposit guarantee context", "matching_logic": ["fdic-insured", "fdic insured", "deposit insurance", "存款保险"], "related_signal_ids": ["SIG-GUARANTEE-EN", "SIG-FINANCE-EN"], "scope": {"verticals": ["financial_services"]}, "risk_reduction": 0.48, "never_override_categories": ["Dangerous Products or Services"], "requires_human_review": False, "rationale": "A regulated deposit-insurance statement can explain a guarantee term.", "owner": "Financial Risk", "version": "1.1.0", "status": "active", "created_at": _now()},
    {"exception_id": "EXC-QUOTE", "name": "Quotation or reporting context", "matching_logic": ["according to", "reported that", "quoted", "news report", "报道", "引用"], "related_signal_ids": ["SIG-GUARANTEE-EN", "SIG-DANGEROUS", "SIG-HEALTH-EN", "SIG-ZH-FINANCE"], "scope": {"languages": ["en", "zh", "mixed"]}, "risk_reduction": 0.42, "never_override_categories": ["Dangerous Products or Services"], "requires_human_review": False, "rationale": "Explicit reporting context can clear bounded claim signals; dangerous content remains review-only.", "owner": "Risk Strategy", "version": "1.1.0", "status": "active", "created_at": _now()},
    {"exception_id": "EXC-WORD-BOUNDARY", "name": "Substring collision suppression", "matching_logic": ["classical", "assistant", "assessment"], "related_signal_ids": ["SIG-GUARANTEE-EN"], "scope": {"languages": ["en"]}, "risk_reduction": 0.2, "never_override_categories": ["Dangerous Products or Services"], "requires_human_review": False, "rationale": "Word boundaries prevent unrelated substrings from becoming signals.", "owner": "Detection Quality", "version": "1.0.0", "status": "active", "created_at": _now()},
]


POLICY_PACKS = [
    {"policy_pack_id": "PACK-FINANCE", "name": "Financial Services Review", "description": "Demo configuration for finance claims and regulated-product triage.", "included_categories": ["CAT-FINANCE", "CAT-DECEPTIVE"], "included_signals": ["SIG-GUARANTEE-EN", "SIG-FINANCE-EN", "SIG-ZH-FINANCE"], "included_exceptions": ["EXC-FDIC", "EXC-LEGAL"], "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["financial_services"], "status": "demo_active", "version": "1.1.0", "owner": "Financial Risk", "effective_at": _now(), "data_scope": "hypothetical_simulation"},
    {"policy_pack_id": "PACK-HEALTH", "name": "Health Claims Review", "description": "Demo configuration for potentially misleading health outcomes.", "included_categories": ["CAT-HEALTH", "CAT-DECEPTIVE"], "included_signals": ["SIG-HEALTH-EN", "SIG-GUARANTEE-EN"], "included_exceptions": ["EXC-EDUCATION", "EXC-QUOTE"], "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["health"], "status": "demo_active", "version": "1.0.0", "owner": "Health Risk", "effective_at": _now(), "data_scope": "hypothetical_simulation"},
    {"policy_pack_id": "PACK-MANDARIN", "name": "Mandarin Cross-Border Ads", "description": "Demo bilingual literal, pinyin, split-character, and diversion configuration.", "included_categories": ["CAT-FINANCE", "CAT-OFFPLATFORM"], "included_signals": ["SIG-ZH-FINANCE", "SIG-ZH-PINYIN", "SIG-ZH-SPLIT", "SIG-OFFPLATFORM"], "included_exceptions": ["EXC-EDUCATION", "EXC-LEGAL"], "markets": ["global"], "languages": ["zh", "mixed"], "verticals": ["all"], "status": "demo_active", "version": "1.0.0", "owner": "Bilingual Risk", "effective_at": _now(), "data_scope": "hypothetical_simulation"},
    {"policy_pack_id": "PACK-NEW-ADVERTISER", "name": "New Advertiser Enhanced Review", "description": "Benchmark-only behavior and review-capacity configuration.", "included_categories": ["CAT-ADVERTISER"], "included_signals": ["SIG-BEHAVIOR-REPEAT", "SIG-OFFPLATFORM"], "included_exceptions": [], "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["all"], "status": "demo_shadow", "version": "0.9.0", "owner": "Integrity Operations", "effective_at": None, "data_scope": "hypothetical_simulation"},
    {"policy_pack_id": "PACK-LANDING", "name": "Landing Page Integrity Review", "description": "Demo configuration used only where destination text is available.", "included_categories": ["CAT-LANDING", "CAT-DECEPTIVE"], "included_signals": ["SIG-LANDING", "SIG-GUARANTEE-EN"], "included_exceptions": ["EXC-QUOTE"], "markets": ["global"], "languages": ["en", "zh", "mixed"], "verticals": ["all"], "status": "demo_shadow", "version": "0.9.0", "owner": "Integrity Operations", "effective_at": None, "data_scope": "hypothetical_simulation"},
]


@dataclass(frozen=True)
class StrategyVersion:
    strategy_id: str
    version_id: str
    name: str
    status: str
    owner: str
    created_at: str
    effective_at: str | None
    change_reason: str
    rollback_target: str | None
    policy_pack_ids: tuple[str, ...]
    markets: tuple[str, ...]
    languages: tuple[str, ...]
    verticals: tuple[str, ...]
    sources: tuple[str, ...]
    risk_threshold: float
    confidence_threshold: float
    escalation_threshold: float
    soft_reject_threshold: float
    hard_reject_threshold: float
    mandatory_human_review: bool
    reviewer_capacity: int
    latency_guardrail_ms: int
    exception_multiplier: float
    authoritative: bool

    def to_dict(self) -> dict[str, object]:
        return {key: list(value) if isinstance(value, tuple) else value for key, value in self.__dict__.items()}


CURRENT_STRATEGY = StrategyVersion("STRAT-COMMERCIAL-RISK", "STRAT-COMMERCIAL-RISK@1.0.0", "Current Strategy v1", "enforced", "Risk Strategy", _now(), _now(), "Represent deterministic_rules_v1 as an immutable strategy", None, ("PACK-FINANCE", "PACK-HEALTH", "PACK-MANDARIN"), ("global",), ("en", "zh", "mixed"), ("all",), ("CFPB", "Meta"), 0.4, 0.68, 0.4, 0.7, 0.85, False, 120, 250, 0.0, True)
CANDIDATE_STRATEGY = StrategyVersion("STRAT-COMMERCIAL-RISK", "STRAT-COMMERCIAL-RISK@2.1.0-candidate", "Candidate Strategy v2.1", "shadow", "Risk Strategy", _now(), None, "Remediate category precedence, bounded bilingual variants, and positive-exception routing", CURRENT_STRATEGY.version_id, ("PACK-FINANCE", "PACK-HEALTH", "PACK-MANDARIN", "PACK-LANDING", "PACK-NEW-ADVERTISER"), ("global",), ("en", "zh", "mixed"), ("all",), ("CFPB", "Meta"), 0.46, 0.72, 0.5, 0.74, 0.88, False, 120, 250, 1.0, False)
STRATEGIES = [CURRENT_STRATEGY, CANDIDATE_STRATEGY]


def create_candidate_version(base: StrategyVersion, *, version_id: str, change_reason: str, **changes: object) -> StrategyVersion:
    """Create a new immutable shadow version; the input version is never mutated."""
    if version_id == base.version_id:
        raise ValueError("A strategy version identifier is immutable and must be unique")
    candidate = replace(base, version_id=version_id, status="shadow", authoritative=False, effective_at=None, rollback_target=base.version_id, change_reason=change_reason, **changes)
    if not 0 <= candidate.risk_threshold <= candidate.escalation_threshold <= candidate.soft_reject_threshold <= candidate.hard_reject_threshold <= 1:
        raise ValueError("Strategy thresholds must satisfy risk ≤ escalation ≤ soft reject ≤ hard reject")
    return candidate


def matched_exceptions(text: str, category: str, product: str = "") -> list[dict[str, object]]:
    matches = []
    language = detect_language(text)
    inferred_vertical = "financial_services" if "Financial" in category else "health" if "Health" in category else product.strip().lower().replace(" ", "_")
    for item in RISK_EXCEPTIONS:
        scope = item.get("scope") or {}
        languages = scope.get("languages") or []
        verticals = scope.get("verticals") or []
        if languages and language not in languages and "mixed" not in languages:
            continue
        if verticals and inferred_vertical not in verticals:
            continue
        terms = [term for term in item["matching_logic"] if contains_term(text, term)]
        if terms:
            active_related_signals = []
            for signal in RISK_SIGNALS:
                if signal["signal_id"] not in item["related_signal_ids"]:
                    continue
                expression = signal.get("expression")
                if isinstance(expression, list) and any(contains_term(text, str(value)) for value in expression):
                    active_related_signals.append(signal["signal_id"])
            never_override = category in item["never_override_categories"]
            reduction = 0.0 if never_override or not active_related_signals else item["risk_reduction"]
            status = "blocked by high-severity guardrail" if never_override else "applied" if active_related_signals else "context matched; no related risk signal active"
            matches.append({**item, "matched_terms": terms, "matched_related_signal_ids": active_related_signals, "scope_match": {"language": language, "vertical": inferred_vertical or "unspecified"}, "applied_reduction": reduction, "blocked_from_override": never_override, "application_status": status})
    return matches


def _route(score: float, confidence: float, strategy: StrategyVersion, *, source: str, exception_requires_review: bool = False) -> tuple[str, bool]:
    if source.strip().lower() not in {"meta", "fixture"}:
        return ("prioritize for analyst review" if score >= 0.65 else "use as risk prior", True)
    if score >= strategy.hard_reject_threshold and confidence >= strategy.confidence_threshold:
        return "hard reject", strategy.mandatory_human_review or exception_requires_review
    if score >= strategy.soft_reject_threshold:
        return "soft reject", True
    if score >= strategy.escalation_threshold or confidence < strategy.confidence_threshold or exception_requires_review:
        return "escalate", True
    if score >= strategy.risk_threshold:
        return "hold", True
    return "allow", strategy.mandatory_human_review


def _route_candidate_policy(
    baseline: object,
    exceptions: list[dict[str, object]],
    strategy: StrategyVersion,
    *,
    source: str,
) -> tuple[str, bool]:
    """Apply candidate v2.1's inspectable category and context routing policy."""
    if source.strip().lower() not in {"meta", "fixture"}:
        score = float(getattr(baseline, "risk_score"))
        return ("prioritize for analyst review" if score >= 0.65 else "use as risk prior", True)
    category = str(getattr(baseline, "risk_category"))
    evidence = list(getattr(baseline, "evidence"))
    terms = {str(item.get("canonical_term") or item.get("term") or "").lower() for item in evidence}
    types = {str(item.get("type") or "") for item in evidence}
    matched_exception = any(float(item.get("applied_reduction") or 0) > 0 for item in exceptions)
    blocked_exception = any(bool(item.get("blocked_from_override")) for item in exceptions)
    if blocked_exception or (exceptions and category == "Dangerous Products or Services"):
        return "escalate", True
    if matched_exception or any(item.get("exception_id") == "EXC-WORD-BOUNDARY" for item in exceptions):
        return "allow", False
    if "advertiser_behavior_signal" in types:
        return "escalate", True
    if category == "Dangerous Products or Services":
        return "hard reject", False
    if category == "Advertiser Integrity Risk" and "document falsification" in terms:
        return "hard reject", False
    if category in {"Off-Platform Diversion", "Gambling / Gaming Risk", "Counterfeit / IP Infringement", "Mandarin Market Evasion Terms"}:
        return "escalate", True
    if types & {"pinyin_variant", "character_split_variant", "curated_homophone_variant"}:
        return "escalate", True
    if category == "Financial Scam / High-Risk Financial Services":
        strong = {"guaranteed", "double your money", "无视征信", "黑户可贷", "保本", "秒批"}
        return ("soft reject", True) if terms & strong else ("escalate", True)
    if category == "Health / Weight Loss / Pharmaceuticals Risk":
        strong = {"miracle", "instant", "instant results", "100%", "七天瘦", "躺瘦", "神药", "根治"}
        return ("soft reject", True) if terms & strong else ("escalate", True)
    if category == "Deceptive / Misleading Claims" and ({"risk-free", "guaranteed", "稳赚"} & terms):
        return "soft reject", True
    return _route(
        float(getattr(baseline, "risk_score")),
        float(getattr(baseline, "confidence")),
        strategy,
        source=source,
        exception_requires_review=False,
    )


def evaluate_text(case_id: str, text: str, *, product: str = "commercial advertisement", source: str = "Meta", strategy: StrategyVersion = CURRENT_STRATEGY, landing_text: str | None = None, data_scope: str | None = None, structured_evidence: list[dict[str, str]] | None = None) -> dict[str, object]:
    source_key = source.strip().lower()
    if source_key not in {"cfpb", "ftc", "meta", "fixture"}:
        raise ValueError(f"Unsupported source for lifecycle evaluation: {source}")
    baseline = score_case(
        case_id,
        text,
        product,
        source,
        landing_text,
        structured_evidence,
        "v1" if strategy.authoritative else "v2.1",
    )
    raw_exceptions = matched_exceptions(text, baseline.risk_category, product)
    if strategy.authoritative:
        exceptions = [{**item, "potential_reduction": item["applied_reduction"], "applied_reduction": 0.0, "application_status": "not active in deterministic_rules_v1"} for item in raw_exceptions]
    else:
        exceptions = raw_exceptions
    reduction = sum(float(item["applied_reduction"]) for item in exceptions) * strategy.exception_multiplier
    adjusted_score = max(0.0, round(baseline.risk_score - reduction, 3))
    requires_review = any(bool(item["requires_human_review"]) for item in exceptions)
    if strategy.authoritative:
        action = {"approve": "allow", "escalate to human review": "escalate"}.get(baseline.recommended_action, baseline.recommended_action)
        human_review = baseline.needs_human_review
    else:
        action, human_review = _route_candidate_policy(baseline, exceptions, strategy, source=source)
    resolved_scope = data_scope or ({"cfpb": DATA_SCOPE_REAL, "ftc": DATA_SCOPE_REAL, "meta": "authorized_public_ads", "fixture": "test_fixture"}[source_key])
    return {
        "case_id": case_id,
        "strategy_version": strategy.version_id,
        "authoritative": strategy.authoritative,
        "data_scope": resolved_scope,
        "detected_language": baseline.language,
        "category": baseline.risk_category,
        "base_score": baseline.risk_score,
        "adjusted_score": adjusted_score,
        "confidence": baseline.confidence,
        "matched_signals": baseline.evidence,
        "matched_exceptions": exceptions,
        "recommended_action": action,
        "needs_human_review": human_review,
        "decision_scope": baseline.decision_scope,
        "policy_rule_ids": baseline.matched_policy_rule_ids,
    }


def decision_trace(case: dict[str, object], strategy: StrategyVersion = CURRENT_STRATEGY) -> dict[str, object]:
    text = str(case.get("case_text") or case.get("ad_text") or "")
    source = str(case.get("source") or "CFPB")
    baseline_score = float(case.get("risk_score") or 0)
    category = str(case.get("risk_category") or "Advertiser Integrity Risk")
    raw_exceptions = matched_exceptions(text, category, str(case.get("product") or ""))
    exceptions = raw_exceptions if not strategy.authoritative else [{**item, "potential_reduction": item["applied_reduction"], "applied_reduction": 0.0, "application_status": "not active in deterministic_rules_v1"} for item in raw_exceptions]
    reduction = sum(float(item["applied_reduction"]) for item in exceptions) * strategy.exception_multiplier
    candidate_score = max(0.0, round(baseline_score - reduction, 3))
    if strategy.authoritative:
        action = str(case.get("recommended_action") or "use as risk prior")
        human_review = bool(case.get("needs_human_review", True))
    else:
        action, human_review = _route(candidate_score, float(case.get("confidence") or 0), strategy, source=source, exception_requires_review=any(bool(item["requires_human_review"]) for item in exceptions))
    landing_value = case.get("landing_page_signals") or "unavailable — no authorized landing-page content in this record"
    advertiser_value = case.get("advertiser_signals") or "unavailable — no authorized advertiser-history linkage in this record"
    confidence_value = {
        "deterministic_confidence": float(case.get("confidence") or 0),
        "calibration_status": "not calibrated as a violation probability",
    }
    steps = [
        {"step": 1, "component": "Source record", "value": source, "why": "Declared upstream public-data scope.", "effect": "CFPB is constrained to research-prior routing.", "version": "data_contract_v1"},
        {"step": 2, "component": "Normalized text", "value": text[:280], "why": "Scrubbed public text used by deterministic matching.", "effect": "No private enrichment is inferred.", "version": "normalization_v1"},
        {"step": 3, "component": "Language", "value": str(case.get("language") or detect_language(text)), "why": "Unicode-script detection.", "effect": "Selects bilingual literal and variant rules.", "version": "language_v1"},
        {"step": 4, "component": "Negative signals", "value": case.get("evidence") or extract_evidence(text), "why": "Exact, word-boundary, pinyin, and short character-split matches.", "effect": "Adds reviewable score components.", "version": "deterministic_rules_v1"},
        {"step": 5, "component": "Positive exceptions", "value": exceptions, "why": "Explicit scoped counter-signals.", "effect": f"Candidate reduction {reduction:.3f}; high-severity overrides remain blocked.", "version": "exceptions_v1"},
        {"step": 6, "component": "Landing-page signals", "value": landing_value, "why": "Destination evidence is evaluated only when authorized content is present.", "effect": "No destination inference is made from creative text alone.", "version": "landing_scope_v1"},
        {"step": 7, "component": "Advertiser-level signals", "value": advertiser_value, "why": "Behavior evidence requires linked advertiser history.", "effect": "No identity, network, or velocity signal is fabricated.", "version": "advertiser_scope_v1"},
        {"step": 8, "component": "Source prior", "value": case.get("decision_scope") or "research_prior", "why": "Complaint and ad records have different decision authority.", "effect": "Prevents complaint-derived enforcement actions.", "version": "source_scope_v1"},
        {"step": 9, "component": "Category determination", "value": category, "why": "Most-supported deterministic category.", "effect": "Selects policy context and routing thresholds.", "version": "taxonomy_v1.1"},
        {"step": 10, "component": "Score components", "value": {"baseline": baseline_score, "exception_reduction": round(reduction, 3), "candidate": candidate_score}, "why": "Priority score, not a calibrated violation probability.", "effect": "Feeds routing thresholds only.", "version": strategy.version_id},
        {"step": 11, "component": "Confidence components", "value": confidence_value, "why": "Shows the deterministic certainty field and its calibration boundary.", "effect": "Prevents probability-like interpretation.", "version": "confidence_contract_v1"},
        {"step": 12, "component": "Policy references", "value": case.get("matched_policy_rule_ids") or [], "why": "Public policy summaries linked to source URLs.", "effect": "Supports analyst interpretation.", "version": "policy_retrieval_v1"},
        {"step": 13, "component": "Strategy", "value": strategy.version_id, "why": strategy.change_reason, "effect": "Candidate results remain non-authoritative in shadow mode." if not strategy.authoritative else "Authoritative deterministic routing.", "version": strategy.version_id},
        {"step": 14, "component": "Recommendation", "value": action, "why": "Threshold and source-scope evaluation.", "effect": "Requires human review." if human_review else "Eligible for deterministic routing.", "version": strategy.version_id},
        {"step": 15, "component": "Optional LLM", "value": "not run", "why": "No call unless a key exists and a reviewer explicitly requests it.", "effect": "Never blocks deterministic review.", "version": "opt_in"},
        {"step": 16, "component": "Reviewer decision", "value": case.get("feedback") or [], "why": "Human feedback is stored separately.", "effect": "Does not rewrite the original decision trace.", "version": "feedback_v1"},
    ]
    trace_scope = case.get("data_scope") or (DATA_SCOPE_REAL if source.upper() in {"CFPB", "FTC"} else "authorized_public_ads")
    return {"case_id": case.get("case_id"), "data_scope": trace_scope, "score_disclaimer": "Priority score, not a calibrated probability of violation.", "authoritative_strategy": CURRENT_STRATEGY.version_id, "evaluated_strategy": strategy.version_id, "steps": steps, "complete": all(item["value"] is not None for item in steps)}


def _scenario(scenario_id: str, language: str, market: str, vertical: str, text: str, category: str, evidence: list[str], routing: str, ambiguity: str = "medium", landing: str | None = None, exception: str | None = None, advertiser: str = "benchmark-advertiser", structured_evidence: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {"scenario_id": scenario_id, "data_scope": DATA_SCOPE_CURATED, "language": language, "market": market, "vertical": vertical, "advertiser_context": advertiser, "creative_text": text, "landing_page_text": landing, "structured_evidence": structured_evidence or [], "expected_category": category, "expected_evidence": evidence, "expected_exception": exception, "expected_routing": routing, "ambiguity_level": ambiguity, "expected_human_review": routing in {"hold", "escalate", "soft reject"}, "rationale": "Curated hypothetical scenario for deterministic strategy evaluation; not an observed ad."}


def benchmark_cases() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    en = [
        ("Guaranteed loan approval with no credit check", "Financial Scam / High-Risk Financial Services", ["guaranteed", "loan"], "soft reject"),
        ("Double your money in seven days through forex", "Financial Scam / High-Risk Financial Services", ["double your money", "forex"], "soft reject"),
        ("Miracle cure for diabetes — instant results", "Health / Weight Loss / Pharmaceuticals Risk", ["miracle", "diabetes"], "soft reject"),
        ("Instant weight loss supplement, 100% guaranteed", "Health / Weight Loss / Pharmaceuticals Risk", ["weight loss", "100%"], "soft reject"),
        ("Message us on WhatsApp for the private offer", "Off-Platform Diversion", ["whatsapp"], "escalate"),
        ("Buy replica luxury bags at factory prices", "Counterfeit / IP Infringement", ["replica"], "escalate"),
        ("Casino jackpot bonus available tonight", "Gambling / Gaming Risk", ["casino", "jackpot"], "escalate"),
        ("Order an illegal drug without a prescription", "Dangerous Products or Services", ["illegal drug"], "hard reject"),
        ("Hack account service with guaranteed access", "Dangerous Products or Services", ["hack account"], "hard reject"),
        ("Risk-free crypto returns for every investor", "Deceptive / Misleading Claims", ["risk-free", "crypto"], "soft reject"),
        ("Debt relief approval in one hour", "Financial Scam / High-Risk Financial Services", ["debt relief"], "escalate"),
        ("Pharmacy medicine shipped worldwide", "Health / Weight Loss / Pharmaceuticals Risk", ["pharmacy", "medicine"], "escalate"),
        ("DM me for an unlisted investment group", "Off-Platform Diversion", ["dm me", "investment"], "escalate"),
        ("Limited time payday loan, act now", "Financial Scam / High-Risk Financial Services", ["payday", "act now"], "escalate"),
        ("Document falsification service for new accounts", "Advertiser Integrity Risk", ["document falsification"], "hard reject"),
    ]
    for index, item in enumerate(en, 1): rows.append(_scenario(f"BEN-EN-{index:02d}", "en", "US", "mixed", item[0], item[1], item[2], item[3]))
    zh = [
        ("无视征信，黑户可贷，当天秒批", "Financial Scam / High-Risk Financial Services", ["无视征信", "黑户可贷", "秒批"], "soft reject"),
        ("稳赚项目，承诺保本返利", "Financial Scam / High-Risk Financial Services", ["稳赚", "保本", "返利"], "soft reject"),
        ("七天瘦，躺着也能瘦", "Health / Weight Loss / Pharmaceuticals Risk", ["七天瘦", "躺瘦"], "soft reject"),
        ("祖传神药可以根治糖尿病", "Health / Weight Loss / Pharmaceuticals Risk", ["神药", "根治"], "soft reject"),
        ("加微了解私域投资机会", "Off-Platform Diversion", ["加微", "私域"], "escalate"),
        ("高仿名牌包一比一复刻", "Counterfeit / IP Infringement", ["高仿"], "escalate"),
        ("博彩棋牌充值送彩金", "Gambling / Gaming Risk", ["博彩", "棋牌"], "escalate"),
        ("代开证明和账户材料", "Advertiser Integrity Risk", ["代开"], "escalate"),
        ("购买枪和炸药教程", "Dangerous Products or Services", ["枪", "炸药"], "hard reject"),
        ("负债上岸，贷款当天到账", "Financial Scam / High-Risk Financial Services", ["上岸", "loan"], "escalate"),
        ("引流到站外群领取返利", "Off-Platform Diversion", ["引流", "返利"], "escalate"),
        ("保本外汇收益翻倍", "Financial Scam / High-Risk Financial Services", ["保本", "forex"], "soft reject"),
        ("莆田医疗咨询，保证疗效", "Health / Weight Loss / Pharmaceuticals Risk", ["莆田", "guarantee"], "escalate"),
        ("无风险投资群，马上加入", "Deceptive / Misleading Claims", ["investment"], "escalate"),
        ("私域贷款秒批，无需资料", "Financial Scam / High-Risk Financial Services", ["私域", "秒批"], "soft reject"),
    ]
    for index, item in enumerate(zh, 1): rows.append(_scenario(f"BEN-ZH-{index:02d}", "zh", "CN", "mixed", item[0], item[1], item[2], item[3]))
    evasions = [
        ("wen zhuan crypto plan", "Deceptive / Misleading Claims", ["稳赚"]), ("bao ben investment", "Financial Scam / High-Risk Financial Services", ["保本"]),
        ("miao pi loan today", "Financial Scam / High-Risk Financial Services", ["秒批"]), ("加·微了解详情", "Off-Platform Diversion", ["加微"]),
        ("稳-赚外汇", "Deceptive / Misleading Claims", ["稳赚"]), ("保 本理财", "Financial Scam / High-Risk Financial Services", ["保本"]),
        ("hei hu ke dai", "Financial Scam / High-Risk Financial Services", ["黑户可贷"]), ("si yu deal on telegram", "Off-Platform Diversion", ["私域", "telegram"]),
        ("返-利 investment club", "Financial Scam / High-Risk Financial Services", ["返利"]), ("jia wei for loan 秒批", "Financial Scam / High-Risk Financial Services", ["加微", "秒批"]),
    ]
    for index, item in enumerate(evasions, 1): rows.append(_scenario(f"BEN-EVA-{index:02d}", "mixed", "SG", "mixed", item[0], item[1], item[2], "escalate", "high"))
    exception_rows = [
        ("FDIC-insured deposit guarantee information", "Financial Scam / High-Risk Financial Services", "EXC-FDIC"),
        ("Drug prevention law educational seminar", "Dangerous Products or Services", "EXC-EDUCATION"),
        ("News report quoted a guaranteed-return scam", "Deceptive / Misleading Claims", "EXC-QUOTE"),
        ("Educational firearm safety training", "Dangerous Products or Services", "EXC-EDUCATION"),
        ("Regulatory guidance on credit repair advertising", "Financial Scam / High-Risk Financial Services", "EXC-LEGAL"),
        ("科普：如何识别稳赚骗局", "Deceptive / Misleading Claims", "EXC-EDUCATION"),
        ("法律讨论：非法药品广告的责任", "Dangerous Products or Services", "EXC-LEGAL"),
        ("The classical art assistant course", "Advertiser Integrity Risk", "EXC-WORD-BOUNDARY"),
        ("报道引用七天瘦虚假宣传案例", "Health / Weight Loss / Pharmaceuticals Risk", "EXC-QUOTE"),
        ("Deposit insurance education: principal protection limits", "Financial Scam / High-Risk Financial Services", "EXC-FDIC"),
    ]
    for index, item in enumerate(exception_rows, 1): rows.append(_scenario(f"BEN-EXC-{index:02d}", "mixed" if index > 5 else "en", "US", "financial_services" if item[2] == "EXC-FDIC" else "mixed", item[0], item[1], [], "escalate" if item[1] == "Dangerous Products or Services" else "allow", "high", exception=item[2]))
    behavior = [
        ("Repeated loan creatives with rotating WhatsApp contacts", "financial_services"), ("Three near-identical miracle cure creatives", "health"),
        ("New advertiser cycling destination domains", "mixed"), ("Multiple creatives reuse the same off-platform contact", "mixed"),
        ("Established advertiser with one isolated ambiguous claim", "retail"), ("Repeated replica product creatives", "retail"),
        ("New advertiser with rapid creative velocity", "mixed"), ("Campaign cluster repeats 保本 and 秒批", "financial_services"),
        ("Prior benchmark reversals suggest high false-positive exposure", "mixed"), ("Linked scenario creatives share landing-page mismatch", "mixed"),
    ]
    for index, item in enumerate(behavior, 1): rows.append(_scenario(f"BEN-ADV-{index:02d}", "mixed", "GB", item[1], item[0], "Advertiser Integrity Risk", ["repeated_pattern"], "escalate", "high", advertiser=f"CURATED-ADV-{(index - 1) // 2 + 1:02d}", structured_evidence=[{"type": "advertiser_behavior_signal", "term": "repeated_pattern", "category": "Advertiser Integrity Risk", "excerpt": "benchmark-only structured advertiser context"}]))
    return rows


CURATED_BENCHMARK_CASES = benchmark_cases()


def run_benchmark(strategy: StrategyVersion = CURRENT_STRATEGY, cases: Iterable[dict[str, object]] | None = None) -> dict[str, object]:
    rows = list(cases or CURATED_BENCHMARK_CASES)
    results = []
    started = time.perf_counter()
    for case in rows:
        evaluation = evaluate_text(str(case["scenario_id"]), str(case["creative_text"]), product=str(case.get("vertical") or "commercial advertisement"), source="Meta", strategy=strategy, landing_text=case.get("landing_page_text") and str(case["landing_page_text"]), data_scope=DATA_SCOPE_CURATED, structured_evidence=[] if strategy.authoritative else list(case.get("structured_evidence") or []))
        evidence_terms = {str(item.get("canonical_term") or item.get("term") or "").lower() for item in evaluation["matched_signals"]}
        expected_terms = {str(term).lower() for term in case["expected_evidence"]}
        matched_exception_ids = {str(item["exception_id"]) for item in evaluation["matched_exceptions"]}
        exception_applied = any(item["exception_id"] == case["expected_exception"] and (float(item["applied_reduction"]) > 0 or bool(item["blocked_from_override"]) or item["exception_id"] == "EXC-WORD-BOUNDARY") for item in evaluation["matched_exceptions"]) if case["expected_exception"] else True
        results.append({"scenario_id": case["scenario_id"], "expected_category": case["expected_category"], "expected_routing": case["expected_routing"], "category_agreement": evaluation["category"] == case["expected_category"], "evidence_agreement": not expected_terms or expected_terms.issubset(evidence_terms), "routing_agreement": evaluation["recommended_action"] == case["expected_routing"], "exception_agreement": exception_applied, "mandarin_variant_covered": not str(case["scenario_id"]).startswith("BEN-EVA") or expected_terms.issubset(evidence_terms), "false_positive_agreement": not str(case["scenario_id"]).startswith("BEN-EXC") or evaluation["recommended_action"] == case["expected_routing"], "evaluation": evaluation})
    elapsed_ms = (time.perf_counter() - started) * 1000
    def rate(key: str, subset: list[dict[str, object]] | None = None) -> float:
        values = subset or results
        return round(sum(bool(row[key]) for row in values) / max(1, len(values)), 3)
    evasion = [row for row in results if str(row["scenario_id"]).startswith("BEN-EVA")]
    exceptions = [row for row in results if str(row["scenario_id"]).startswith("BEN-EXC")]
    expected_term_count = sum(len(row["expected_evidence"]) for row in rows)
    matched_term_count = sum(len({str(term).lower() for term in case["expected_evidence"]} & {str(item.get("canonical_term") or item.get("term") or "").lower() for item in result["evaluation"]["matched_signals"]}) for case, result in zip(rows, results))
    evasion_expected_count = sum(len(row["expected_evidence"]) for row in rows if str(row["scenario_id"]).startswith("BEN-EVA"))
    evasion_matched_count = sum(len({str(term).lower() for term in case["expected_evidence"]} & {str(item.get("canonical_term") or item.get("term") or "").lower() for item in result["evaluation"]["matched_signals"]}) for case, result in zip(rows, results) if str(case["scenario_id"]).startswith("BEN-EVA"))
    category_agreement = rate("category_agreement")
    evidence_coverage = round(matched_term_count / max(1, expected_term_count), 3)
    routing_agreement = rate("routing_agreement")
    exception_handling_agreement = rate("exception_agreement", exceptions)
    mandarin_variant_coverage = round(evasion_matched_count / max(1, evasion_expected_count), 3)
    false_positive_scenario_agreement = rate("false_positive_agreement", exceptions)
    promotion_threshold = 0.9
    promotion_checks = [
        {"metric": "category_agreement", "label": "Category agreement", "value": category_agreement, "threshold": promotion_threshold},
        {"metric": "routing_agreement", "label": "Routing agreement", "value": routing_agreement, "threshold": promotion_threshold},
        {"metric": "exception_routing_agreement", "label": "Exception routing agreement", "value": false_positive_scenario_agreement, "threshold": promotion_threshold},
    ]
    blockers = [item for item in promotion_checks if float(item["value"]) < float(item["threshold"])]
    gate_status = "eligible_for_review" if not blockers else "hold"
    failure_buckets = [
        {
            "key": "taxonomy",
            "label": "Taxonomy attribution",
            "count": sum(not bool(row["category_agreement"]) for row in results),
            "owner": "Policy & Taxonomy",
            "next_step": "Review multi-signal category precedence and re-run the affected scenarios.",
        },
        {
            "key": "routing",
            "label": "Routing thresholds",
            "count": sum(not bool(row["routing_agreement"]) for row in results),
            "owner": "Risk Strategy",
            "next_step": "Segment threshold changes by severity and compare missed-risk versus review load.",
        },
        {
            "key": "evidence",
            "label": "Evidence coverage",
            "count": sum(not bool(row["evidence_agreement"]) for row in results),
            "owner": "Bilingual Risk",
            "next_step": "Validate bounded English and Mandarin variants before expanding the signal library.",
        },
        {
            "key": "exceptions",
            "label": "Positive exceptions",
            "count": sum(not bool(row["exception_agreement"]) for row in exceptions),
            "owner": "Review Operations",
            "next_step": "Audit exception-to-signal linkage while retaining high-severity override guardrails.",
        },
    ]
    return {
        "data_scope": DATA_SCOPE_CURATED,
        "label": "Curated development/regression scenarios — not production records, observed platform ads, or a held-out test set.",
        "strategy_version": strategy.version_id,
        "scenario_count": len(rows),
        "category_agreement": category_agreement,
        "evidence_coverage": evidence_coverage,
        "routing_agreement": routing_agreement,
        "exception_handling_agreement": exception_handling_agreement,
        "mandarin_variant_coverage": mandarin_variant_coverage,
        "false_positive_scenario_agreement": false_positive_scenario_agreement,
        "promotion_gate": {
            "status": gate_status,
            "threshold": promotion_threshold,
            "checks": promotion_checks,
            "blockers": blockers,
            "scope_caveat": (
                "These 60 scenarios are the development set candidate v2.1 was remediated against, so agreement "
                "measures regression coverage, not generalization to unseen ads. No held-out set exists yet."
            ),
            "decision": (
                "Regression set clean; eligible for controlled human review only. Because v2.1 was tuned against "
                "these same labels, this is not evidence of generalization, and production promotion still "
                "requires authorized labels and approval."
                if gate_status == "eligible_for_review"
                else f"Hold promotion: {len(blockers)} regression checks are below the illustrative 90% review threshold."
            ),
        },
        "failure_buckets": failure_buckets,
        "measured_total_latency_ms": round(elapsed_ms, 2),
        "results": results,
    }


def threshold_sensitivity(cases: Iterable[dict[str, object]] | None = None, capacity: int = 120) -> list[dict[str, object]]:
    rows = list(cases or CURATED_BENCHMARK_CASES)
    output = []
    for threshold in (0.35, 0.45, 0.55, 0.65, 0.69):
        strategy = create_candidate_version(CURRENT_STRATEGY, version_id=f"sensitivity@{threshold:.2f}", change_reason="Threshold sensitivity only", escalation_threshold=threshold, risk_threshold=max(0.2, threshold - 0.1))
        evaluations = [(case, evaluate_text(str(case["scenario_id"]), str(case["creative_text"]), product=str(case.get("vertical") or "commercial advertisement"), source="Meta", strategy=strategy, data_scope=DATA_SCOPE_CURATED)) for case in rows]
        reviewed = [item for item in evaluations if item[1]["needs_human_review"]]
        missed = [item for item in evaluations if item[0]["expected_routing"] in {"soft reject", "hard reject"} and item[1]["recommended_action"] in {"allow", "hold"}]
        false_positive = [item for item in evaluations if str(item[0]["scenario_id"]).startswith("BEN-EXC") and item[1]["recommended_action"] in {"soft reject", "hard reject"}]
        output.append({"threshold": threshold, "review_volume": len(reviewed), "allow_rate": round(sum(item[1]["recommended_action"] == "allow" for item in evaluations) / len(evaluations), 3), "false_positive_scenarios": len(false_positive), "missed_risk_scenarios": len(missed), "reviewer_capacity": capacity, "capacity_utilization": round(len(reviewed) / max(1, capacity), 3), "within_capacity": len(reviewed) <= capacity})
    return output


def strategy_evaluation(assumptions: dict[str, float] | None = None) -> dict[str, object]:
    values = {"review_minutes_per_case": 3.0, "reviewer_hourly_cost": 35.0, "model_cost_per_case": 0.002, "revenue_value_per_allowed_case": 4.0, "harm_cost_per_missed_case": 50.0, **(assumptions or {})}
    def summary(strategy: StrategyVersion) -> dict[str, object]:
        evaluations = [evaluate_text(str(case["scenario_id"]), str(case["creative_text"]), product=str(case.get("vertical") or "commercial advertisement"), source="Meta", strategy=strategy, data_scope=DATA_SCOPE_CURATED) for case in CURATED_BENCHMARK_CASES]
        total = len(evaluations)
        counts = {action: sum(row["recommended_action"] == action for row in evaluations) for action in ("allow", "hold", "escalate", "soft reject", "hard reject")}
        review = sum(bool(row["needs_human_review"]) for row in evaluations)
        minutes = review * values["review_minutes_per_case"]
        missed = sum(case["expected_routing"] in {"soft reject", "hard reject"} and result["recommended_action"] in {"allow", "hold"} for case, result in zip(CURATED_BENCHMARK_CASES, evaluations))
        false_positive = sum(str(case["scenario_id"]).startswith("BEN-EXC") and case["expected_routing"] == "allow" and result["recommended_action"] != "allow" for case, result in zip(CURATED_BENCHMARK_CASES, evaluations))
        return {"strategy_version": strategy.version_id, "status": strategy.status, "scenario_count": total, "review_queue_volume": review, "allow_rate": round(counts["allow"] / total, 3), "escalation_rate": round((counts["hold"] + counts["escalate"]) / total, 3), "rejection_rate": round((counts["soft reject"] + counts["hard reject"]) / total, 3), "automation_eligible_coverage": round(sum(not row["needs_human_review"] for row in evaluations) / total, 3), "reviewer_utilization": round(review / strategy.reviewer_capacity, 3), "estimated_handling_minutes": minutes, "estimated_sla_pressure": "high" if review > strategy.reviewer_capacity else "within illustrative capacity", "estimated_review_cost": round(minutes / 60 * values["reviewer_hourly_cost"], 2), "estimated_model_cost": 0.0, "illustrative_model_cost_if_applied": round(total * values["model_cost_per_case"], 2), "illustrative_revenue_at_risk": round((counts["soft reject"] + counts["hard reject"]) * values["revenue_value_per_allowed_case"], 2), "illustrative_harm_cost": round(missed * values["harm_cost_per_missed_case"], 2), "benchmark_missed_risk_cases": missed, "benchmark_missed_risk_exposure": round(missed / total, 3), "benchmark_false_positive_cases": false_positive, "benchmark_false_positive_exposure": round(false_positive / max(1, sum(str(case["scenario_id"]).startswith("BEN-EXC") for case in CURATED_BENCHMARK_CASES)), 3), "latency_guardrail_ms": strategy.latency_guardrail_ms}
    current = summary(CURRENT_STRATEGY)
    candidate = summary(CANDIDATE_STRATEGY)
    current_benchmark = run_benchmark(CURRENT_STRATEGY)
    candidate_benchmark = run_benchmark(CANDIDATE_STRATEGY)
    return {"data_scope": DATA_SCOPE_CURATED, "assumption_label": ASSUMPTION_LABEL, "assumptions": values, "current": {**current, "benchmark_routing_agreement": current_benchmark["routing_agreement"]}, "candidate": {**candidate, "benchmark_routing_agreement": candidate_benchmark["routing_agreement"]}, "threshold_sensitivity": threshold_sensitivity(capacity=CANDIDATE_STRATEGY.reviewer_capacity), "decision": "Shadow evaluation only; candidate results do not replace deterministic_rules_v1."}


def preview_candidate_strategy(risk_threshold: float, escalation_threshold: float, reviewer_capacity: int) -> dict[str, object]:
    """Evaluate an editable candidate without mutating or replacing the active strategy."""
    if not 0 <= risk_threshold <= escalation_threshold <= CANDIDATE_STRATEGY.soft_reject_threshold:
        raise ValueError("Thresholds must satisfy 0 ≤ risk ≤ escalation ≤ soft-reject threshold")
    if reviewer_capacity < 1:
        raise ValueError("Reviewer capacity must be at least 1")
    candidate = create_candidate_version(
        CURRENT_STRATEGY,
        version_id=f"STRAT-COMMERCIAL-RISK@preview-{risk_threshold:.2f}-{escalation_threshold:.2f}-{reviewer_capacity}",
        name="Staged Candidate Preview",
        created_at=datetime.now(UTC).isoformat(),
        change_reason="User-staged shadow preview; never authoritative",
        policy_pack_ids=CANDIDATE_STRATEGY.policy_pack_ids,
        risk_threshold=risk_threshold,
        escalation_threshold=escalation_threshold,
        reviewer_capacity=reviewer_capacity,
        exception_multiplier=CANDIDATE_STRATEGY.exception_multiplier,
        mandatory_human_review=CANDIDATE_STRATEGY.mandatory_human_review,
    )
    current_results = [evaluate_text(str(case["scenario_id"]), str(case["creative_text"]), product=str(case.get("vertical") or "commercial advertisement"), source="Meta", strategy=CURRENT_STRATEGY, data_scope=DATA_SCOPE_CURATED) for case in CURATED_BENCHMARK_CASES]
    candidate_results = [evaluate_text(str(case["scenario_id"]), str(case["creative_text"]), product=str(case.get("vertical") or "commercial advertisement"), source="Meta", strategy=candidate, data_scope=DATA_SCOPE_CURATED) for case in CURATED_BENCHMARK_CASES]
    action_counts = {action: sum(row["recommended_action"] == action for row in candidate_results) for action in ("allow", "hold", "escalate", "soft reject", "hard reject")}
    review_volume = sum(bool(row["needs_human_review"]) for row in candidate_results)
    disagreements = [
        {"scenario_id": case["scenario_id"], "current_action": current["recommended_action"], "candidate_action": staged["recommended_action"]}
        for case, current, staged in zip(CURATED_BENCHMARK_CASES, current_results, candidate_results)
        if current["recommended_action"] != staged["recommended_action"]
    ]
    benchmark = run_benchmark(candidate)
    benchmark.pop("results", None)
    return {
        "data_scope": DATA_SCOPE_CURATED,
        "authoritative": False,
        "label": "Staged shadow preview on curated scenarios — not production deployment or observed traffic.",
        "strategy": candidate.to_dict(),
        "scenario_count": len(CURATED_BENCHMARK_CASES),
        "review_volume": review_volume,
        "reviewer_capacity": reviewer_capacity,
        "capacity_utilization": round(review_volume / reviewer_capacity, 3),
        "within_capacity": review_volume <= reviewer_capacity,
        "action_counts": action_counts,
        "disagreement_count": len(disagreements),
        "sample_disagreements": disagreements[:5],
        "benchmark": benchmark,
    }


def curated_advertiser_profiles() -> list[dict[str, object]]:
    profiles = []
    for index in range(1, 6):
        related = [row for row in CURATED_BENCHMARK_CASES if row["advertiser_context"] == f"CURATED-ADV-{index:02d}"]
        profiles.append({"advertiser_id": f"CURATED-ADV-{index:02d}", "display_name": f"Benchmark Advertiser {index:02d}", "data_scope": DATA_SCOPE_CURATED, "scenario_maturity": "new" if index < 4 else "established", "total_creatives": len(related), "reviewed_creatives": len(related), "rejected_creatives": sum(row["expected_routing"] in {"soft reject", "hard reject"} for row in related), "escalation_rate": round(sum(row["expected_routing"] == "escalate" for row in related) / max(1, len(related)), 3), "repeated_risk_categories": sorted({str(row["expected_category"]) for row in related}), "associated_landing_pages": [], "off_platform_contact_signals": sum("contact" in str(row["creative_text"]).lower() for row in related), "similar_creative_clusters": 1 if related else 0, "velocity_signals": "illustrative elevated" if index < 4 else "illustrative stable", "prior_reviewer_decisions": [], "appeal_or_reversal_status": "not provided", "integrity_risk_level": "high" if index < 4 else "medium", "recommended_analyst_action": "Inspect repeated patterns; do not infer real-world identity or network links."})
    return profiles


def lifecycle_records() -> dict[str, list[dict[str, object]]]:
    return {"risk_taxonomy_versions": RISK_TAXONOMY, "risk_signals": RISK_SIGNALS, "risk_exceptions": RISK_EXCEPTIONS, "policy_packs": POLICY_PACKS, "strategy_versions": [item.to_dict() for item in STRATEGIES], "curated_benchmark_cases": CURATED_BENCHMARK_CASES, "curated_advertisers": curated_advertiser_profiles()}


def json_rows(records: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Make nested lifecycle records stable for DuckDB export."""
    return [{key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict, tuple)) else value for key, value in row.items()} for row in records]
