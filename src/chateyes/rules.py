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
        if not matched or self.confidence < 0.0 or self.confidence > 1.0:
            return None
        return RuleMatch(
            rule_id=self.rule_id,
            severity=self.severity,
            recommended_action=self.recommended_action,
            confidence=self.confidence,
            justification=self.justification,
            summary=self.summary,
        )


# The rule engine deliberately keeps matching deterministic. A future ML/LLM classifier
# can supply contextual scores through the same RuleMatch shape without changing the API.
RULES: tuple[ModerationRule, ...] = (
    ModerationRule(
        "RULE_HARASSMENT_HATE", "CRITICAL", "BAN",
        re.compile(r"\b(?:kill\s+you|i\s+will\s+kill|go\s+kill\s+yourself|mar\s+doonga|maar\s+doonga)\b", re.I),
        0.99,
        "The message contains a direct threat or encouragement of violence/self-harm.",
        "Threatening or abusive content",
    ),
    ModerationRule(
        "RULE_SEXUAL_EXPLICIT", "HIGH", "MUTE",
        re.compile(r"\b(?:fuck|fucking|sex|sexy|nude|nudes|dick|pussy|horny|blowjob|porn|chut|lund|choot|randi|jism\s*ka)\b", re.I),
        0.97,
        "The message contains an explicit or sexually suggestive term.",
        "Sexually explicit or suggestive content",
    ),
    ModerationRule(
        "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA", "MEDIUM", "REVIEW",
        re.compile(r"\b(?:nude|nudes|porn|xxx|sexcam|nsfw|onlyfans)\b", re.I),
        0.90,
        "The visible nickname or media-related text contains a potentially inappropriate sexual or adult-content signal and should be reviewed.",
        "Potentially inappropriate nickname or media",
    ),
    ModerationRule(
        "RULE_SPAM_SOLICITATION", "LOW", "WARN",
        re.compile(r"\b(?:like\s*4\s*like|like\s*for\s*like|f4f|sub4sub|follow\s*4\s*follow|gift\s*(?:exchange|for))\b", re.I),
        0.95,
        "The message requests reciprocal engagement or an unsolicited promotional exchange.",
        "Spam or solicitation",
    ),
)

_RULE_ORDER = {rule.rule_id: index for index, rule in enumerate(RULES)}
_SEVERITY_RANK: dict[Severity, int] = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def evaluate(text: str, confidence_threshold: float = 0.80) -> list[RuleMatch]:
    """Evaluate a normalized message and return unique, threshold-qualified hits.

    If multiple rules match the same message, the highest-severity hit is retained.
    This prevents overlapping signals such as an explicit term from producing a
    second, weaker media-review decision for the same visible content.
    """
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0 and 1")

    matches = [match for rule in RULES if (match := rule.match(text)) and match.confidence >= confidence_threshold]
    if not matches:
        return []

    strongest = max(matches, key=lambda item: (_SEVERITY_RANK[item.severity], item.confidence, -_RULE_ORDER[item.rule_id]))
    return [strongest]
