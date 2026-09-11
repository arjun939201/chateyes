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


class ScreenshotAnalysisResponse(BaseModel):
    screenshot_ready: bool
    ocr: OCRResponse
    messages: list[ChatMessage]
    moderation: ModerationResponse
    tasks: list[TaskPlanItem]


def parse_ocr_messages(text: str) -> list[ChatMessage]:
    """Convert common OCR chat-line formats into structured messages."""
    messages: list[ChatMessage] = []
    current: ChatMessage | None = None
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        match = _SPEAKER_RE.match(line)
        if match:
            if current is not None:
                messages.append(current)
            current = ChatMessage(
                username=match.group("username").strip(),
                text=match.group("text").strip(),
            )
        elif current is None:
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
