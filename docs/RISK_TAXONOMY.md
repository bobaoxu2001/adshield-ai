# Bilingual Risk Taxonomy

| English category | 中文 | Example signals |
|---|---|---|
| Deceptive / Misleading Claims | 欺骗性或误导性声明 | guaranteed, risk-free, 稳赚, 保本 |
| Financial Scam / High-Risk Financial Services | 金融诈骗或高风险金融服务 | loan, crypto, 秒批, 无视征信, 黑户可贷, 上岸 |
| Health / Weight Loss / Pharmaceuticals Risk | 健康、减重或药品风险 | miracle cure, 七天瘦, 躺瘦, 神药, 根治, 莆田 |
| Gambling / Gaming Risk | 赌博或博彩风险 | casino, betting, 博彩, 棋牌 |
| Adult / Sexualized Content | 成人或性暗示内容 | adult services, sexualized promotion |
| Counterfeit / IP Infringement | 假货或知识产权侵权 | replica, counterfeit, 高仿 |
| Misinformation / Public Harm | 虚假信息或公共危害 | hoax, harmful unverified claim |
| Dangerous Products or Services | 危险产品或服务 | weapons, illegal drugs, criminal services |
| Advertiser Integrity Risk | 广告主诚信风险 | impersonation, document falsification, 代开 |
| Landing Page Mismatch | 落地页不一致 | redirect, different offer, 货不对板 |
| Off-Platform Diversion | 站外导流 | WhatsApp, Telegram, 加微, 私域, 引流 |
| Mandarin Market Evasion Terms | 中文市场规避词 | 私域, 引流, 加微, 羊毛, 谐音规避, 拼音规避 |
| Uncategorized / Needs Review | 未分类 / 待人工复核 | *(fail-safe fallback; never keyword-matched)* |

## Fail-safe fallback

When an ad matches no signal and carries no product prior, the engine does not invent a specific harm
category. It assigns **Uncategorized / Needs Review** and routes the case to a human — both the
authoritative v1 engine and the candidate escalate rather than auto-approving something they could not
understand. This is a deliberate safety property: an unrecognized ad is a reason to ask a person, not
to guess a label or wave it through.

## Mandarin matching boundary

The frozen v1 layer supports curated literal terms, normalized pinyin, and short character splits such as `稳-赚`. Candidate v2.1 adds four explicit, test-covered homophone substitutions (`稳转`, `保苯`, `秒披`, `家薇`) plus modality-tagged evidence extracted from authorized upstream OCR/ASR text. It does not claim discovery of novel homophones, cultural code words, or native image/audio/video understanding. Those cases route to bilingual or multimodal human review.

Terms are signals, not standalone policy verdicts. Context, market eligibility, licensing, creative/landing-page consistency, and advertiser history can change the decision.
