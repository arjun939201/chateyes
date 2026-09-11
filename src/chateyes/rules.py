from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Pattern

from .models import Action, RuleId, Severity


@dataclass(frozen=True)
class RuleMatch:
    rule_id: RuleId
    severity: Severity
    recommended_action: Action
    confidence: float
    justification: str
    summary: str


@dataclass(frozen=True)
class ModerationRule:
    rule_id: RuleId
    severity: Severity
    recommended_action: Action
    pattern: Pattern[str] | None
    confidence: float
    justification: str
    summary: str
    matcher: Callable[[str], bool] | None = None

    def match(self, text: str) -> RuleMatch | None:
        matched = self.matcher(text) if self.matcher else bool(self.pattern and self.pattern.search(text))
        if not matched:
            return None
        return RuleMatch(self.rule_id, self.severity, self.recommended_action, self.confidence, self.justification, self.summary)


RULES: tuple[ModerationRule, ...] = (
    ModerationRule("RULE_HARASSMENT_HATE", "CRITICAL", "BAN", re.compile(r"\b(?:kill\s+you|i\s+will\s+kill|go\s+kill\s+yourself|mar\s+doonga|maar\s+doonga)\b", re.I), 0.99, "The message contains a direct threat or encouragement of violence/self-harm.", "Threatening or abusive content"),
    ModerationRule("RULE_SEXUAL_EXPLICIT", "HIGH", "MUTE", re.compile(r"\b(?:fuck|fucking|sex|sexy|nude|nudes|dick|pussy|horny|blowjob|porn|chut|lund|choot|randi|jism\s*ka)\b", re.I), 0.97, "The message contains an explicit or sexually suggestive term.", "Sexually explicit or suggestive content"),
    ModerationRule("RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA", "MEDIUM", "REVIEW", None, 0.90, "The visible nickname or media description contains a potentially inappropriate adult-content signal and should be reviewed.", "Potentially inappropriate nickname or media", matcher=lambda value: bool(re.search(r"\b(?:nude|nudes|porn|xxx|sexcam|nsfw|onlyfans)\b", value, re.I))),
    ModerationRule("RULE_SPAM_SOLICITATION", "LOW", "WARN", re.compile(r"\b(?:like\s*4\s*like|like\s*for\s*like|f4f|sub4sub|follow\s*4\s*follow|gift\s*(?:exchange|for))\b", re.I), 0.95, "The message requests reciprocal engagement or an unsolicited promotional exchange.", "Spam or solicitation"),
)

_RULE_ORDER = {rule.rule_id: index for index, rule in enumerate(RULES)}
_SEVERITY_RANK: dict[Severity, int] = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def evaluate(text: str, *, username: str = "", media_description: str = "", media_present: bool = False, confidence_threshold: float = 0.80) -> list[RuleMatch]:
    """Evaluate text plus optional nickname/media signals and keep the strongest hit."""
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0 and 1")

    matches: list[RuleMatch] = []
    for rule in RULES:
        if rule.rule_id == "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA":
            continue
        match = rule.match(text)
        if match and match.confidence >= confidence_threshold:
            matches.append(match)

    if media_present and (username or media_description):
        rule = next(r for r in RULES if r.rule_id == "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA")
        match = rule.match(" ".join(part for part in (username, media_description) if part))
        if match and match.confidence >= confidence_threshold:
            matches.append(match)

    if not matches:
        return []
    strongest = max(matches, key=lambda item: (_SEVERITY_RANK[item.severity], item.confidence, -_RULE_ORDER[item.rule_id]))
    return [strongest]
