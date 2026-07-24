from __future__ import annotations

import re
import unicodedata

from src.risk.taxonomy import CATEGORIES, MANDARIN_TERMS

SIGNAL_GROUPS_V1 = {
    "urgency_or_guarantee": ("guaranteed", "instant", "limited time", "act now", "100%", "稳赚", "保本", "秒批"),
    "regulated_product": ("loan", "credit", "investment", "crypto", "pharmacy", "supplement", "gambling", "mortgage", "student loan"),
    "off_platform_contact": ("whatsapp", "telegram", "wechat", "dm me", "加微", "私域", "引流"),
}

SIGNAL_GROUPS_V21 = {
    "urgency_or_guarantee": ("guaranteed", "instant", "limited time", "act now", "100%", "稳赚", "保本", "秒批", "保证"),
    "regulated_product": ("loan", "credit", "investment", "crypto", "pharmacy", "supplement", "gambling", "mortgage", "student loan", "贷款", "投资", "外汇"),
    "off_platform_contact": ("whatsapp", "telegram", "wechat", "dm me", "加微", "私域", "引流", "站外"),
}

V1_TAXONOMY_TERMS = {
    "Deceptive / Misleading Claims": {"guaranteed", "guarantee", "risk-free", "instant results", "miracle", "no risk", "100%", "稳赚", "保本", "根治"},
    "Financial Scam / High-Risk Financial Services": {"investment", "crypto", "loan", "credit repair", "debt relief", "payday", "forex", "double your money", "秒批", "无视征信", "黑户可贷", "上岸", "返利"},
    "Health / Weight Loss / Pharmaceuticals Risk": {"weight loss", "lose weight", "supplement", "pharmacy", "cure", "medicine", "diabetes", "七天瘦", "躺瘦", "神药", "根治", "莆田"},
    "Gambling / Gaming Risk": {"gambling", "casino", "betting", "jackpot", "博彩", "棋牌"},
    "Adult / Sexualized Content": {"adult", "sexual", "escort", "色情", "裸聊"},
    "Counterfeit / IP Infringement": {"counterfeit", "replica", "fake brand", "高仿", "代开"},
    "Misinformation / Public Harm": {"conspiracy", "fake news", "hoax", "misinformation", "谣言"},
    "Dangerous Products or Services": {"weapon", "explosive", "illegal drug", "hack account", "枪", "炸药"},
    "Advertiser Integrity Risk": {"impersonat", "fake identity", "document falsification", "multiple accounts", "冒充", "代开"},
    "Landing Page Mismatch": {"landing mismatch", "different offer", "redirect", "跳转", "货不对板"},
    "Mandarin Market Evasion Terms": {"谐音规避", "拼音规避", "私域", "引流", "加微", "羊毛"},
}

SIGNAL_CATEGORIES = {
    "regulated_product": "Financial Scam / High-Risk Financial Services",
    "off_platform_contact": "Off-Platform Diversion",
}

# Bounded, inspectable mappings only. These are not a claim of general translation,
# phonetic understanding, or discovery of novel evasion language.
LITERAL_CANONICALS = {
    "贷款": "loan",
    "投资": "investment",
    "外汇": "forex",
    "保证": "guarantee",
    "躺着也能瘦": "躺瘦",
}

CURATED_HOMOPHONE_VARIANTS = {
    "稳转": ("稳赚", "Deceptive / Misleading Claims"),
    "保苯": ("保本", "Financial Scam / High-Risk Financial Services"),
    "秒披": ("秒批", "Financial Scam / High-Risk Financial Services"),
    "家薇": ("加微", "Off-Platform Diversion"),
}

MANDARIN_CATEGORY_OVERRIDES = {
    "加微": "Off-Platform Diversion",
    "私域": "Off-Platform Diversion",
    "引流": "Off-Platform Diversion",
}


def contains_term(text: str, term: str) -> bool:
    if re.search(r"[A-Za-z]", term):
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, flags=re.IGNORECASE))
    return term in text


def detect_language(text: str) -> str:
    has_zh = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_en = bool(re.search(r"[A-Za-z]", text))
    return "mixed" if has_zh and has_en else "zh" if has_zh else "en"


def _latin_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).lower()
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", without_marks)


def _split_character_match(text: str, term: str) -> bool:
    """Match short Mandarin terms split by whitespace or punctuation, e.g. `稳-赚`."""
    if len(term) < 2 or term in text:
        return False
    separator = r"[\s\W_]{1,2}"
    return bool(re.search(separator.join(re.escape(char) for char in term), text))


def extract_evidence(text: str, *, profile: str = "v1") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    groups = SIGNAL_GROUPS_V21 if profile == "v2.1" else SIGNAL_GROUPS_V1
    for signal_type, terms in groups.items():
        for term in terms:
            if contains_term(text, term) and (signal_type, term) not in seen:
                item = {"type": signal_type, "term": term, "excerpt": term}
                if profile == "v2.1" and signal_type in SIGNAL_CATEGORIES:
                    item["category"] = SIGNAL_CATEGORIES[signal_type]
                if profile == "v2.1" and term in LITERAL_CANONICALS:
                    item["canonical_term"] = LITERAL_CANONICALS[term]
                found.append(item)
                seen.add((signal_type, term))
    for category in CATEGORIES:
        for term in category.keywords:
            if profile != "v2.1" and term not in V1_TAXONOMY_TERMS.get(category.name, set()):
                continue
            if contains_term(text, term) and (category.name, term) not in seen:
                found.append({"type": "taxonomy_match", "term": term, "category": category.name, "excerpt": term})
                seen.add((category.name, term))
    if profile == "v2.1":
        for literal, canonical in LITERAL_CANONICALS.items():
            if literal in text and ("literal_canonical", canonical) not in seen:
                found.append({
                    "type": "literal_canonical",
                    "term": literal,
                    "canonical_term": canonical,
                    "excerpt": literal,
                })
                seen.add(("literal_canonical", canonical))
        for variant, (canonical, category) in CURATED_HOMOPHONE_VARIANTS.items():
            if variant in text and ("curated_homophone_variant", canonical) not in seen:
                found.append({
                    "type": "curated_homophone_variant",
                    "term": variant,
                    "canonical_term": canonical,
                    "category": category,
                    "excerpt": variant,
                })
                seen.add(("curated_homophone_variant", canonical))
    latin_text = _latin_key(text)
    for term, (pinyin, _gloss, category) in MANDARIN_TERMS.items():
        pinyin_key = _latin_key(pinyin)
        if pinyin_key and len(pinyin_key) >= 5 and pinyin_key in latin_text and ("pinyin_variant", term) not in seen:
            found.append({
                "type": "pinyin_variant",
                "term": pinyin,
                "canonical_term": term,
                "category": MANDARIN_CATEGORY_OVERRIDES.get(term, category) if profile == "v2.1" else category,
                "excerpt": pinyin,
            })
            seen.add(("pinyin_variant", term))
        elif _split_character_match(text, term) and ("character_split_variant", term) not in seen:
            found.append({
                "type": "character_split_variant",
                "term": term,
                "canonical_term": term,
                "category": MANDARIN_CATEGORY_OVERRIDES.get(term, category) if profile == "v2.1" else category,
                "excerpt": term,
            })
            seen.add(("character_split_variant", term))
    return found


def extract_multimodal_text_evidence(
    creative_text: str,
    *,
    ocr_text: str | None = None,
    asr_text: str | None = None,
) -> dict[str, object]:
    """Extract evidence from authorized upstream text channels with provenance.

    This function does not inspect pixels, audio, or video. It accepts OCR/ASR text
    only when another authorized system supplied it and keeps each modality visible
    in the trace so text-derived evidence is never presented as native vision/audio.
    """
    channels = {"creative_text": creative_text, "ocr_text": ocr_text, "asr_text": asr_text}
    available = {name: bool(value and value.strip()) for name, value in channels.items()}
    evidence: list[dict[str, str]] = []
    for modality, value in channels.items():
        if not value or not value.strip():
            continue
        for item in extract_evidence(value, profile="v2.1"):
            evidence.append({**item, "modality": modality})
    return {
        "evidence": evidence,
        "modality_availability": available,
        "provenance_note": "OCR and ASR text must come from an authorized upstream service; raw-media understanding is not claimed.",
    }


def landing_page_mismatch(ad_text: str, landing_text: str | None) -> dict[str, str] | None:
    if not landing_text:
        return None
    ad_tokens = set(re.findall(r"[A-Za-z\u4e00-\u9fff]{2,}", ad_text.lower()))
    landing_tokens = set(re.findall(r"[A-Za-z\u4e00-\u9fff]{2,}", landing_text.lower()))
    overlap = len(ad_tokens & landing_tokens) / max(1, len(ad_tokens))
    if overlap < 0.18:
        return {"type": "landing_page_mismatch", "term": "low semantic overlap", "category": "Landing Page Mismatch", "excerpt": f"Token overlap {overlap:.0%}"}
    return None
