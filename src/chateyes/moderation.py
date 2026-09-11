from __future__ import annotations

import unicodedata

from .language import detect_language, normalize_for_detection
from .models import ChatMessage, ModerationResponse, Violation
from .rules import evaluate


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return normalize_for_detection(text)


def moderate_messages(
    messages: list[ChatMessage], *, confidence_threshold: float = 0.80
) -> ModerationResponse:
    """Moderate messages using normalized text and confidence-aware rules."""
    violations: list[Violation] = []
    for message in messages:
        text = _normalized(message.text)
        detected_language = detect_language(text)
        for match in evaluate(
            text,
            username=_normalized(message.username),
            media_description=_normalized(message.media_description),
            media_present=message.media_present,
            confidence_threshold=confidence_threshold,
        ):
            violations.append(
                Violation(
                    username=message.username,
                    original_text=message.text,
                    detected_language=detected_language,
                    translated_english_summary=message.translated_english_summary or match.summary,
                    rule_id=match.rule_id,
                    severity=match.severity,
                    recommended_action=match.recommended_action,
                    justification=match.justification,
                )
            )
    return ModerationResponse(
        screen_status="VIOLATION_DETECTED" if violations else "CLEAN",
        total_violations=len(violations),
        violations=violations,
    )
