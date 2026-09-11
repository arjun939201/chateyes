import re
import unicodedata

from .models import ChatMessage, ModerationResponse, Violation

_RULES = (
    (
        "RULE_SPAM_SOLICITATION",
        "LOW",
        "WARN",
        re.compile(r"\b(?:like\s*4\s*like|like\s*for\s*like|f4f|sub4sub|follow\s*4\s*follow|gift\s*(?:exchange|for))\b", re.I),
        "The message requests reciprocal engagement or an unsolicited promotional exchange.",
        "Spam or solicitation",
    ),
    (
        "RULE_SEXUAL_EXPLICIT",
        "HIGH",
        "MUTE",
        re.compile(r"\b(?:fuck|fucking|sex|sexy|nude|nudes|dick|pussy|horny|blowjob|porn)\b", re.I),
        "The message contains an explicit or sexually suggestive term.",
        "Sexually explicit or suggestive content",
    ),
    (
        "RULE_HARASSMENT_HATE",
        "CRITICAL",
        "BAN",
        re.compile(r"\b(?:kill\s+you|i\s+will\s+kill|go\s+kill\s+yourself)\b", re.I),
        "The message contains a direct threat or encouragement of violence/self-harm.",
        "Threatening or abusive content",
    ),
)


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def moderate_messages(messages: list[ChatMessage]) -> ModerationResponse:
    violations: list[Violation] = []
    for message in messages:
        text = _normalized(message.text)
        for rule_id, severity, action, pattern, justification, summary in _RULES:
            if pattern.search(text):
                violations.append(
                    Violation(
                        username=message.username,
                        original_text=message.text,
                        detected_language=message.detected_language,
                        translated_english_summary=message.translated_english_summary or summary,
                        rule_id=rule_id,
                        severity=severity,
                        recommended_action=action,
                        justification=justification,
                    )
                )
    return ModerationResponse(
        screen_status="VIOLATION_DETECTED" if violations else "CLEAN",
        total_violations=len(violations),
        violations=violations,
    )
