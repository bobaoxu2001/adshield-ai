from __future__ import annotations

from dataclasses import asdict, dataclass

from src.risk.evidence_extractor import (
    V1_TAXONOMY_TERMS,
    contains_term,
    detect_language,
    extract_evidence,
    landing_page_mismatch,
)
from src.risk.policy_retriever import retrieve_policy_rules
from src.risk.taxonomy import CATEGORIES, UNCATEGORIZED, category_for_product


@dataclass(frozen=True)
class RiskDecision:
    case_id: str
    language: str
    risk_score: float
    risk_category: str
    severity: str
    evidence: list[dict[str, str]]
    policy_rationale: str
    matched_policy_rule_ids: list[str]
    recommended_action: str
    confidence: float
    business_impact_note: str
    needs_human_review: bool
    decision_scope: str
    engine: str = "deterministic_rules_v1"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _category_v1(text: str, product: str, evidence: list[dict[str, str]]) -> str:
    counts: dict[str, int] = {}
    for item in evidence:
        category = item.get("category")
        if category:
            counts[category] = counts.get(category, 0) + 1
    if counts:
        return max(counts, key=counts.get)
    combined = f"{product} {text}"
    for category in CATEGORIES:
        if any(contains_term(combined, term) for term in V1_TAXONOMY_TERMS.get(category.name, set())):
            return category.name
    return category_for_product(product)


def _category_v21(text: str, product: str, evidence: list[dict[str, str]]) -> str:
    counts: dict[str, int] = {}
    for item in evidence:
        category = item.get("category")
        if category:
            counts[category] = counts.get(category, 0) + 1
    terms = {str(item.get("canonical_term") or item.get("term") or "").lower() for item in evidence}
    types = {str(item.get("type") or "") for item in evidence}
    # Explicit precedence prevents generic guarantees from hiding a more specific
    # dangerous, health, diversion, finance, or advertiser-integrity signal.
    precedence = (
        "Dangerous Products or Services",
        "Advertiser Integrity Risk",
        "Health / Weight Loss / Pharmaceuticals Risk",
        "Counterfeit / IP Infringement",
        "Gambling / Gaming Risk",
    )
    for name in precedence:
        if counts.get(name):
            return name
    if counts.get("Mandarin Market Evasion Terms") and ({"谐音规避", "拼音规避"} & terms):
        return "Mandarin Market Evasion Terms"
    finance_terms = {
        str(item.get("canonical_term") or item.get("term") or "").lower()
        for item in evidence
        if item.get("category") == "Financial Scam / High-Risk Financial Services"
    }
    finance_count = len(finance_terms)
    deceptive_count = counts.get("Deceptive / Misleading Claims", 0)
    if finance_count >= 2:
        return "Financial Scam / High-Risk Financial Services"
    if "off_platform_contact" in types or counts.get("Off-Platform Diversion"):
        return "Off-Platform Diversion"
    if finance_count and (not deceptive_count or not ({"risk-free", "稳赚", "无风险"} & terms)):
        return "Financial Scam / High-Risk Financial Services"
    if deceptive_count:
        return "Deceptive / Misleading Claims"
    if counts:
        return max(counts, key=counts.get)
    combined = f"{product} {text}"
    for category in CATEGORIES:
        if any(contains_term(combined, term) for term in category.keywords):
            return category.name
    return category_for_product(product)


def score_case(
    case_id: str,
    text: str,
    product: str = "",
    source: str = "cfpb",
    landing_text: str | None = None,
    structured_evidence: list[dict[str, str]] | None = None,
    strategy_profile: str = "v1",
) -> RiskDecision:
    source_key = source.strip().lower()
    enforcement_eligible = source_key in {"meta", "fixture"}
    evidence = extract_evidence(text, profile=strategy_profile)
    if structured_evidence:
        evidence.extend(structured_evidence)
    mismatch = landing_page_mismatch(text, landing_text)
    if mismatch:
        evidence.append(mismatch)
    category = _category_v21(text, product, evidence) if strategy_profile == "v2.1" else _category_v1(text, product, evidence)
    semantic_evidence_count = len({
        str(item.get("canonical_term") or item.get("term") or "").strip().lower()
        for item in evidence
        if item.get("canonical_term") or item.get("term")
    })
    finance_prior = 0.22 if source_key == "cfpb" else 0.08
    score = min(0.98, 0.12 + finance_prior + semantic_evidence_count * 0.115)
    if strategy_profile == "v2.1" and category in {"Dangerous Products or Services", "Adult / Sexualized Content"}:
        score = min(0.98, score + 0.30)
    elif strategy_profile == "v2.1" and category in {"Financial Scam / High-Risk Financial Services", "Health / Weight Loss / Pharmaceuticals Risk"} and semantic_evidence_count >= 2:
        score = min(0.98, score + 0.17)
    elif strategy_profile == "v2.1" and category == "Deceptive / Misleading Claims" and semantic_evidence_count >= 2:
        score = min(0.98, score + 0.15)
    elif strategy_profile == "v2.1" and category == "Advertiser Integrity Risk" and any(item.get("term") == "document falsification" for item in evidence):
        score = min(0.98, score + 0.35)
    severity = "critical" if score >= 0.85 else "high" if score >= 0.65 else "medium" if score >= 0.4 else "low"
    confidence = min(0.96, 0.5 + semantic_evidence_count * 0.07 + (0.08 if product else 0.0))
    if not enforcement_eligible:
        # CFPB/FTC/unknown sources are not authorized ad creatives or adjudicated labels.
        # They can prioritize research but must never produce an enforcement-style action.
        needs_human_review = True
        action = "prioritize for analyst review" if score >= 0.65 else "use as risk prior"
        decision_scope = "risk_prior"
        impact_note = (
            "Uses a non-enforcement source as vocabulary and prior evidence for analyst research; "
            "it is not an ad decision or proof of a policy violation."
        )
    elif category == UNCATEGORIZED:
        # Fail-safe: an ad the engine could not categorize is never auto-approved. It goes
        # to a human, who has the context the keyword matcher lacks.
        needs_human_review = True
        action = "escalate to human review"
        decision_scope = "ad_triage"
        impact_note = "No matching signal or product prior; routed to human review rather than assigned a specific harm category."
    else:
        needs_human_review = 0.4 <= score < 0.85 or confidence < 0.68
        action = "hard reject" if score >= 0.85 and confidence >= 0.75 else "soft reject" if score >= 0.7 else "escalate to human review" if needs_human_review else "approve"
        decision_scope = "ad_triage"
        impact_note = "Prioritizes likely consumer-harm ads while retaining human review for ambiguous or context-dependent signals."
    rules = retrieve_policy_rules(category)
    rationale = rules[0].summary if rules else "No category-specific rule is available; escalate for policy review."
    return RiskDecision(
        case_id=case_id,
        language=detect_language(text),
        risk_score=round(score, 3),
        risk_category=category,
        severity=severity,
        evidence=evidence,
        policy_rationale=rationale,
        matched_policy_rule_ids=[rule.rule_id for rule in rules],
        recommended_action=action,
        confidence=round(confidence, 3),
        business_impact_note=impact_note,
        needs_human_review=needs_human_review,
        decision_scope=decision_scope,
    )
