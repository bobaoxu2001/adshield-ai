from src.risk.policy_retriever import load_policy_rules, retrieve_policy_rules


def test_policy_knowledge_base_has_sources() -> None:
    rules = load_policy_rules()
    assert len(rules) >= 10
    assert all(rule.source_url.startswith("https://") for rule in rules)
    assert all(rule.last_checked != "unknown" for rule in rules)


def test_retrieval_returns_category_rule() -> None:
    rules = retrieve_policy_rules("Financial Scam / High-Risk Financial Services")
    assert rules
    assert rules[0].rule_id == "TT-FIN-001"


def test_retrieval_returns_source_linked_rules() -> None:
    """Retrieved rules must carry a usable source link and human-readable provenance."""
    rules = retrieve_policy_rules("Health / Weight Loss / Pharmaceuticals Risk")
    assert rules
    for rule in rules:
        assert rule.source_url.startswith("https://")
        assert rule.source_name.strip()
        assert rule.summary.strip()
        assert rule.last_checked != "unknown"


def test_unknown_category_falls_back_to_deceptive_rules() -> None:
    rules = retrieve_policy_rules("Nonexistent Category")
    assert rules
    assert all(rule.category == "Deceptive / Misleading Claims" for rule in rules)
