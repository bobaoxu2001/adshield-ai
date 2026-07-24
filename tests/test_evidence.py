from src.risk.evidence_extractor import detect_language, extract_evidence, landing_page_mismatch


def test_language_detection() -> None:
    assert detect_language("guaranteed loan") == "en"
    assert detect_language("稳赚保本") == "zh"
    assert detect_language("稳赚 guaranteed") == "mixed"


def test_off_platform_signal() -> None:
    evidence = extract_evidence("加微联系，稳赚保本")
    assert any(item["type"] == "off_platform_contact" for item in evidence)


def test_english_terms_use_word_boundaries() -> None:
    evidence = extract_evidence("The borrower secured a loan.")
    assert not any(item["term"] == "cure" for item in evidence)


def test_landing_page_mismatch_is_only_emitted_when_text_exists() -> None:
    assert landing_page_mismatch("guaranteed loan", None) is None
    assert landing_page_mismatch("guaranteed loan", "buy garden furniture") is not None


def test_pinyin_and_character_split_variants_are_detected() -> None:
    pinyin = extract_evidence("jia wei lian xi, wen zhuan bao ben")
    split = extract_evidence("稳-赚，保 本")
    assert any(item["type"] == "pinyin_variant" and item.get("canonical_term") == "加微" for item in pinyin)
    assert any(item["type"] == "pinyin_variant" and item.get("canonical_term") == "稳赚" for item in pinyin)
    assert any(item["type"] == "character_split_variant" and item.get("canonical_term") == "稳赚" for item in split)
