from src.risk.policy_retriever import load_policy_rules, retrieve_policy_rules


def test_policy_knowledge_base_has_sources() -> None:
    rules = load_policy_rules()
    assert len(rules) >= 10
    assert all(rule.source_url.startswith("https://") for rule in rules)
    assert all(rule.last_checked != "unknown" for rule in rules)


def test_retrieval_returns_category_rule() -> None:
    rules = retrieve_policy_rules("Financial Scam / High-Risk Financial Services")
    assert rules
    assert all(rule.category == "Financial Scam / High-Risk Financial Services" for rule in rules)
    # The corpus is multi-platform: the financial category is backed by more than one publisher.
    assert len({rule.source_name for rule in rules}) >= 2


def test_corpus_is_platform_neutral() -> None:
    """No single publisher should dominate the policy knowledge base."""
    rules = load_policy_rules()
    publishers = {"tiktok": 0, "meta": 0, "google": 0, "ftc": 0}
    for rule in rules:
        url = rule.source_url.lower()
        if "tiktok" in url:
            publishers["tiktok"] += 1
        elif "meta.com" in url or "facebook" in url:
            publishers["meta"] += 1
        elif "google" in url:
            publishers["google"] += 1
        elif "ftc.gov" in url:
            publishers["ftc"] += 1
    # At least three distinct major publishers are represented.
    assert sum(count > 0 for count in publishers.values()) >= 3


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
