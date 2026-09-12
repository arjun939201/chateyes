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


_PROFILE_SIGNALS = frozenset({"nude", "nudes", "porn", "xxx", "sexcam", "nsfw", "onlyfans", "adult"})


def _profile_signal_match(value: str) -> bool:
    """Match adult-content profile/media signals across common separators."""
    compact = value.casefold().replace(" ", "")
    if "18+" in compact:
        return True
    tokens = set(re.findall(r"[a-z0-9]+", value.casefold()))
    return bool(tokens & _PROFILE_SIGNALS)


RULES: tuple[ModerationRule, ...] = (
    ModerationRule(
        "RULE_HARASSMENT_HATE", "CRITICAL", "BAN",
        re.compile(r"\b(?:kill\s+you|i\s+will\s+kill|go\s+kill\s+yourself|mar\s+(?:doonga|dunga|dalunga|deunga)|maar\s+(?:doonga|dunga|dalunga|deunga)|(?:maar|mar)\s+(?:khayega|khaega))\b", re.I),
        0.99, "The message contains a direct threat or violent intimidation.", "Threatening or abusive content"
    ),
    ModerationRule(
        "RULE_SEXUAL_EXPLICIT", "HIGH", "MUTE",
        re.compile(r"\b(?:fuck|fucking|sex|sexy|nude|nudes|dick|pussy|horny|blowjob|porn|chut|lund|choot|randi|jism\s*ka)\b", re.I),
        0.97, "The message contains an explicit or sexually suggestive term.", "Sexually explicit or suggestive content"
    ),
    ModerationRule(
        "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA", "MEDIUM", "REVIEW", None, 0.90,
        "The visible nickname or media description contains a potentially inappropriate adult-content signal and should be reviewed.",
        "Potentially inappropriate nickname or media",
        matcher=_profile_signal_match,
    ),
    ModerationRule(
        "RULE_SPAM_SOLICITATION", "LOW", "WARN",
        re.compile(r"\b(?:like\s*4\s*like|like\s*for\s*like|f4f|sub4sub|follow\s*4\s*follow|gift\s*(?:exchange|for)|dm\s*(?:me|for)|promo(?:te|tion)?\s+me)\b", re.I),
        0.95, "The message requests reciprocal engagement or an unsolicited promotional exchange.", "Spam or solicitation"
    ),
)

_RULE_ORDER = {rule.rule_id: index for index, rule in enumerate(RULES)}
_SEVERITY_RANK: dict[Severity, int] = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def evaluate(text: str, *, username: str = "", media_description: str = "", media_present: bool = False, confidence_threshold: float = 0.80) -> list[RuleMatch]:
    """Evaluate message text and visible profile/media signals deterministically."""
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0 and 1")

    matches: list[RuleMatch] = []
    profile_rule = next(r for r in RULES if r.rule_id == "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA")

    for rule in RULES:
        if rule.rule_id == profile_rule.rule_id:
            continue
        match = rule.match(text)
        if match and match.confidence >= confidence_threshold:
            matches.append(match)

    # Nicknames are always visible profile evidence. Media descriptions are
    # evaluated only when the caller confirms that media is actually present.
    profile_signal = " ".join(part for part in (username, media_description if media_present else "") if part).strip()
    if profile_signal:
        match = profile_rule.match(profile_signal)
        if match and match.confidence >= confidence_threshold:
            matches.append(match)

    if not matches:
        return []
    strongest = max(matches, key=lambda item: (_SEVERITY_RANK[item.severity], item.confidence, -_RULE_ORDER[item.rule_id]))
    return [strongest]
