from __future__ import annotations

import re

from pydantic import BaseModel

from .models import ChatMessage, ModerationResponse, OCRResponse
from .ocr import OCRResult, TesseractOCR
from .tasks import Role, TaskPlanItem, generate_tasks

_SPEAKER_RE = re.compile(
    r"^(?:\[\s*\d{1,2}:\d{2}(?::\d{2})?\s*\]\s*)?"
    r"(?P<username>[^:\n]{1,64})\s*(?:[:>]|\s-\s)\s*(?P<text>.+)$"
)
_TIME_ONLY_RE = re.compile(r"^(?:\[?\s*)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*\]?|\s+\d+.*)$")
_UI_RE = re.compile(
    r"^(?:feed|write\s+.*message|chat\s*=|board|send|search|settings|menu|home|back|"
    r"[©®]?\s*\d+(?:\.\d+)?\s*(?:am|pm)?|\d+%|\d+\s*vo\b).*$",
    re.I,
)


class ScreenshotAnalysisResponse(BaseModel):
    screenshot_ready: bool
    ocr: OCRResponse
    messages: list[ChatMessage]
    moderation: ModerationResponse
    tasks: list[TaskPlanItem]


def _clean_line(raw_line: str) -> str:
    return " ".join(raw_line.split()).strip()


def _looks_like_ui(line: str) -> bool:
    """Reject obvious status-bar/composer/navigation OCR instead of chat."""
    if not line or _TIME_ONLY_RE.match(line):
        return True
    return bool(_UI_RE.match(line))


def _valid_speaker(username: str) -> bool:
    username = username.strip()
    if not username or _TIME_ONLY_RE.match(username):
        return False
    return any(char.isalpha() for char in username)


def parse_ocr_messages(text: str) -> list[ChatMessage]:
    """Convert OCR into structured chat candidates while filtering UI noise.

    Explicit speaker boundaries start new messages. Non-speaker lines after a
    valid speaker remain continuations, matching normal multiline chat behavior.
    Standalone OCR lines are retained anonymously so moderation can still inspect
    them without inventing a username.
    """
    messages: list[ChatMessage] = []
    current: ChatMessage | None = None

    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line or _looks_like_ui(line):
            continue

        match = _SPEAKER_RE.match(line)
        if match and _valid_speaker(match.group("username")):
            if current is not None:
                messages.append(current)
            current = ChatMessage(
                username=match.group("username").strip(),
                text=match.group("text").strip(),
            )
            continue

        if current is None:
            messages.append(ChatMessage(text=line))
        else:
            current.text = f"{current.text} {line}".strip()

    if current is not None:
        messages.append(current)
    return messages


def analyze_screenshot(
    image_bytes: bytes,
    *,
    role: Role = "MIT",
    warning_count: int = 0,
    moderator_present: bool = False,
    signature_detected: bool = False,
    user_stopped: bool = False,
    direct_report_flags: set[str] | None = None,
    ocr: TesseractOCR | None = None,
) -> ScreenshotAnalysisResponse:
    """Run OCR, message reconstruction, moderation, and task planning."""
    engine = ocr or TesseractOCR()
    result: OCRResult = engine.extract_text(image_bytes)
    messages = parse_ocr_messages(result.text)

    from .moderation import moderate_messages

    moderation = moderate_messages(messages)
    tasks = generate_tasks(
        moderation,
        role=role,
        screenshot_available=True,
        moderator_present=moderator_present,
        signature_detected=signature_detected,
        warning_count=warning_count,
        user_stopped=user_stopped,
        direct_report_flags=direct_report_flags,
    )
    return ScreenshotAnalysisResponse(
        screenshot_ready=True,
        ocr=OCRResponse(text=result.text, engine=result.engine, language=result.language),
        messages=messages,
        moderation=moderation,
        tasks=tasks,
    )
