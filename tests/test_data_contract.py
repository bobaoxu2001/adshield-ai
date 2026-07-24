from src.risk.taxonomy import CATEGORY_NAMES
from src.risk.scoring import score_case


def test_required_score_contract() -> None:
    columns = {
        "case_id", "language", "risk_score", "risk_category", "severity", "policy_rationale",
        "recommended_action", "confidence", "business_impact_note", "needs_human_review",
    }
    actual = score_case("contract", "guaranteed loan", "loan", "meta").to_dict()
    assert columns.issubset(actual)
    assert actual["decision_scope"] == "ad_triage"
    assert "Financial Scam / High-Risk Financial Services" in CATEGORY_NAMES
