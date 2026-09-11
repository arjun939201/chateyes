from typing import Literal

from pydantic import BaseModel, Field

RuleId = Literal[
    "RULE_SPAM_SOLICITATION",
    "RULE_SEXUAL_EXPLICIT",
    "RULE_HARASSMENT_HATE",
    "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA",
]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Action = Literal["WARN", "MUTE", "REVIEW", "BAN"]


class Violation(BaseModel):
    username: str
    original_text: str
    detected_language: str
    translated_english_summary: str
    rule_id: RuleId
    severity: Severity
    recommended_action: Action
    justification: str = Field(min_length=1)


class ModerationResponse(BaseModel):
    screen_status: Literal["CLEAN", "VIOLATION_DETECTED"]
    total_violations: int = Field(ge=0)
    violations: list[Violation]


class ChatMessage(BaseModel):
    username: str = ""
    text: str
    detected_language: str = "English"
    translated_english_summary: str = ""


class TextModerationRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class OCRResponse(BaseModel):
    text: str
    engine: str
    language: str
