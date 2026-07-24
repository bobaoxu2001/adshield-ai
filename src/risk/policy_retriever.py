from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.config import settings


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    category: str
    title: str
    summary: str
    source_name: str
    source_url: str
    last_checked: str


def load_policy_rules(policy_dir: Path | None = None) -> list[PolicyRule]:
    policy_dir = policy_dir or settings.policy_dir
    rules: list[PolicyRule] = []
    for path in sorted(policy_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta = dict(re.findall(r"^([a-z_]+):\s*(.+)$", text, flags=re.MULTILINE))
        summary_match = re.search(r"## Summary\s+(.+?)(?:\n##|\Z)", text, flags=re.DOTALL)
        rules.append(PolicyRule(
            rule_id=meta.get("rule_id", path.stem),
            category=meta.get("category", "Deceptive / Misleading Claims"),
            title=meta.get("title", path.stem.replace("_", " ").title()),
            summary=" ".join((summary_match.group(1) if summary_match else text).split()),
            source_name=meta.get("source_name", "Public policy guidance"),
            source_url=meta.get("source_url", ""),
            last_checked=meta.get("last_checked", "unknown"),
        ))
    return rules


def retrieve_policy_rules(category: str, limit: int = 3) -> list[PolicyRule]:
    rules = load_policy_rules()
    matches = [rule for rule in rules if rule.category == category]
    if not matches:
        matches = [rule for rule in rules if rule.category == "Deceptive / Misleading Claims"]
    return matches[:limit]
