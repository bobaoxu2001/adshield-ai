import json
from pathlib import Path

from src.risk.scoring import score_case
from src.risk.taxonomy import CATEGORY_NAMES, MANDARIN_TERMS

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "synthetic_cases.json").read_text())

VALID_ACTIONS = {"approve", "soft reject", "hard reject", "escalate to human review"}


def _expected_severity(score: float) -> str:
    return "critical" if score >= 0.85 else "high" if score >= 0.65 else "medium" if score >= 0.4 else "low"


def test_synthetic_fixtures_are_test_only() -> None:
    assert all(item["case_id"].startswith("test-") for item in FIXTURES)


def test_scoring_schema_and_taxonomy() -> None:
    for item in FIXTURES:
        decision = score_case(item["case_id"], item["text"], item["product"], "fixture")
        assert decision.risk_category in CATEGORY_NAMES
        assert 0 <= decision.risk_score <= 1
        assert 0 <= decision.confidence <= 1
        assert decision.evidence
        assert decision.recommended_action in {"approve", "soft reject", "hard reject", "escalate to human review"}


def test_mandarin_detection() -> None:
    decision = score_case("test", "无视征信，黑户可贷，秒批，加微了解。", "loan", "fixture")
    assert decision.language == "zh"
    assert decision.risk_category == "Financial Scam / High-Risk Financial Services"
    assert decision.risk_score >= 0.65


def test_scoring_thresholds_produce_valid_actions() -> None:
    """Every recommended action must be valid and consistent with the documented thresholds."""
    texts = [
        "Thank you for the update on my order.",
        "I disputed a billing error on my credit card statement.",
        "无视征信，黑户可贷，秒批，加微了解。",
        "Guaranteed investment returns, double your money, add me on WhatsApp.",
        "七天瘦，神药根治，100% guaranteed.",
        "casino jackpot betting bonus, telegram to join",
    ]
    for text in texts:
        d = score_case("threshold", text, "loan", "meta")
        assert d.recommended_action in VALID_ACTIONS
        assert d.severity == _expected_severity(d.risk_score)
        assert d.needs_human_review == (0.4 <= d.risk_score < 0.85 or d.confidence < 0.68)
        if d.recommended_action == "hard reject":
            assert d.risk_score >= 0.85 and d.confidence >= 0.75
        elif d.recommended_action == "soft reject":
            assert d.risk_score >= 0.7
            assert not (d.risk_score >= 0.85 and d.confidence >= 0.75)
        elif d.recommended_action == "escalate to human review":
            assert d.risk_score < 0.7 and d.needs_human_review
        else:  # approve
            assert d.risk_score < 0.7 and not d.needs_human_review


def test_mandarin_terms_map_to_valid_categories() -> None:
    """Every Mandarin evasion term resolves to a real taxonomy category."""
    for term, (_pinyin, _gloss, category) in MANDARIN_TERMS.items():
        assert category in CATEGORY_NAMES, f"{term} maps to unknown category {category}"


def test_mandarin_terms_route_to_expected_category() -> None:
    expected = {
        "私域引流加微，谐音规避": "Mandarin Market Evasion Terms",
        "棋牌博彩": "Gambling / Gaming Risk",
        "高仿 replica bags": "Counterfeit / IP Infringement",
        "无视征信，黑户可贷，秒批": "Financial Scam / High-Risk Financial Services",
        "七天瘦，躺瘦，神药": "Health / Weight Loss / Pharmaceuticals Risk",
    }
    for text, category in expected.items():
        assert score_case("zh", text, "", "meta").risk_category == category


def test_cfpb_cases_never_emit_ad_enforcement_actions() -> None:
    decision = score_case("cfpb-test", "Guaranteed investment loan, double your money", "loan", "cfpb")
    assert decision.decision_scope == "risk_prior"
    assert decision.needs_human_review is True
    assert decision.recommended_action in {"prioritize for analyst review", "use as risk prior"}
    assert decision.recommended_action not in {"approve", "soft reject", "hard reject"}


def test_cfpb_source_matching_is_case_insensitive() -> None:
    decision = score_case("cfpb-test", "Guaranteed investment loan, double your money", "loan", "CFPB")
    assert decision.decision_scope == "risk_prior"
    assert decision.recommended_action in {"prioritize for analyst review", "use as risk prior"}


def test_ftc_and_unknown_sources_never_emit_enforcement_actions() -> None:
    for source in ("FTC", "unknown"):
        decision = score_case("prior", "illegal drug guaranteed returns", "loan", source)
        assert decision.decision_scope == "risk_prior"
        assert decision.recommended_action in {"prioritize for analyst review", "use as risk prior"}
        assert decision.recommended_action not in VALID_ACTIONS


def test_duplicate_semantic_terms_do_not_inflate_score_twice() -> None:
    decision = score_case("dedupe", "loan", "loan", "meta")
    assert len([item for item in decision.evidence if item["term"] == "loan"]) == 2
    assert decision.risk_score == 0.315  # base + Meta prior + one semantic evidence term
