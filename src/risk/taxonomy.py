from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskCategory:
    name: str
    name_zh: str
    keywords: tuple[str, ...]


CATEGORIES = (
    RiskCategory("Deceptive / Misleading Claims", "欺骗性或误导性声明", ("guaranteed", "guarantee", "risk-free", "instant results", "miracle", "no risk", "100%", "稳赚", "保本", "根治", "无风险")),
    RiskCategory("Financial Scam / High-Risk Financial Services", "金融诈骗或高风险金融服务", ("investment", "crypto", "loan", "credit repair", "debt relief", "payday", "forex", "double your money", "deposit", "秒批", "无视征信", "黑户可贷", "上岸", "返利", "贷款", "投资", "外汇")),
    RiskCategory("Health / Weight Loss / Pharmaceuticals Risk", "健康、减重或药品风险", ("weight loss", "lose weight", "supplement", "pharmacy", "cure", "medicine", "diabetes", "七天瘦", "躺瘦", "神药", "根治", "莆田")),
    RiskCategory("Gambling / Gaming Risk", "赌博或博彩风险", ("gambling", "casino", "betting", "jackpot", "博彩", "棋牌")),
    RiskCategory("Adult / Sexualized Content", "成人或性暗示内容", ("adult", "sexual", "escort", "色情", "裸聊")),
    RiskCategory("Counterfeit / IP Infringement", "假货或知识产权侵权", ("counterfeit", "replica", "fake brand", "高仿", "代开")),
    RiskCategory("Misinformation / Public Harm", "虚假信息或公共危害", ("conspiracy", "fake news", "hoax", "misinformation", "谣言")),
    RiskCategory("Dangerous Products or Services", "危险产品或服务", ("weapon", "explosive", "illegal drug", "drug", "firearm", "hack account", "枪", "炸药", "非法药品")),
    RiskCategory("Advertiser Integrity Risk", "广告主诚信风险", ("impersonat", "fake identity", "document falsification", "multiple accounts", "冒充", "代开")),
    RiskCategory("Landing Page Mismatch", "落地页不一致", ("landing mismatch", "different offer", "redirect", "跳转", "货不对板")),
    RiskCategory("Off-Platform Diversion", "站外导流", ("whatsapp", "telegram", "wechat", "dm me", "加微", "私域", "引流", "站外")),
    RiskCategory("Mandarin Market Evasion Terms", "中文市场规避词", ("谐音规避", "拼音规避", "私域", "引流", "加微", "羊毛")),
    # Fail-safe bucket: never matched by keywords, only assigned as a fallback when nothing
    # else applies. It makes no specific harm accusation and always routes to human review.
    RiskCategory("Uncategorized / Needs Review", "未分类 / 待人工复核", ()),
)

UNCATEGORIZED = "Uncategorized / Needs Review"

CATEGORY_NAMES = tuple(category.name for category in CATEGORIES)
MANDARIN_TERMS = {
    "稳赚": ("wěn zhuàn", "guaranteed profit", "Deceptive / Misleading Claims"),
    "保本": ("bǎo běn", "principal guaranteed", "Financial Scam / High-Risk Financial Services"),
    "秒批": ("miǎo pī", "instant approval", "Financial Scam / High-Risk Financial Services"),
    "无视征信": ("wú shì zhēng xìn", "no credit check", "Financial Scam / High-Risk Financial Services"),
    "黑户可贷": ("hēi hù kě dài", "loans despite blacklisted credit", "Financial Scam / High-Risk Financial Services"),
    "七天瘦": ("qī tiān shòu", "slim in seven days", "Health / Weight Loss / Pharmaceuticals Risk"),
    "躺瘦": ("tǎng shòu", "lose weight without effort", "Health / Weight Loss / Pharmaceuticals Risk"),
    "神药": ("shén yào", "miracle drug", "Health / Weight Loss / Pharmaceuticals Risk"),
    "根治": ("gēn zhì", "complete cure", "Health / Weight Loss / Pharmaceuticals Risk"),
    "代开": ("dài kāi", "document/invoice proxy", "Advertiser Integrity Risk"),
    "高仿": ("gāo fǎng", "high-grade counterfeit", "Counterfeit / IP Infringement"),
    "莆田": ("pú tián", "context-sensitive medical-service signal", "Health / Weight Loss / Pharmaceuticals Risk"),
    "上岸": ("shàng àn", "get out of debt", "Financial Scam / High-Risk Financial Services"),
    "博彩": ("bó cǎi", "gambling", "Gambling / Gaming Risk"),
    "棋牌": ("qí pái", "card/board gaming; contextual gambling signal", "Gambling / Gaming Risk"),
    "返利": ("fǎn lì", "rebate/commission", "Financial Scam / High-Risk Financial Services"),
    "羊毛": ("yáng máo", "promotion exploitation", "Mandarin Market Evasion Terms"),
    "私域": ("sī yù", "private-domain traffic", "Mandarin Market Evasion Terms"),
    "引流": ("yǐn liú", "traffic diversion", "Mandarin Market Evasion Terms"),
    "加微": ("jiā wēi", "add on WeChat", "Mandarin Market Evasion Terms"),
    "谐音规避": ("xié yīn guī bì", "homophone evasion", "Mandarin Market Evasion Terms"),
    "拼音规避": ("pīn yīn guī bì", "pinyin evasion", "Mandarin Market Evasion Terms"),
}


def category_for_product(product: str) -> str:
    value = product.lower()
    if any(term in value for term in ("loan", "credit", "debt", "mortgage", "money", "bank")):
        return "Financial Scam / High-Risk Financial Services"
    # No signal and no product prior: do not invent a specific harm category. Mark it
    # uncategorized so the fail-safe routing sends it to a human instead of guessing.
    return UNCATEGORIZED
