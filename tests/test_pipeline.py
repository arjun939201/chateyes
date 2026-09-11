from io import BytesIO

from PIL import Image

from chateyes.pipeline import parse_ocr_messages


def test_parse_ocr_messages_recognizes_common_chat_formats() -> None:
    messages = parse_ocr_messages("[12:30] Alice: hello\nBob > like for like\nAlice: second line")
    assert [(item.username, item.text) for item in messages] == [
        ("Alice", "hello"),
        ("Bob", "like for like"),
        ("Alice", "second line"),
    ]


def test_parse_ocr_messages_keeps_unmatched_lines() -> None:
    messages = parse_ocr_messages("system notice\nAlice: hello\ncontinuation")
    assert messages[0].username == ""
    assert messages[0].text == "system notice"
    assert messages[1].text == "hello continuation"


def test_analyze_screenshot_pipeline_returns_tasks() -> None:
    from chateyes import pipeline
    from chateyes.ocr import OCRResult

    class FakeOCR:
        def extract_text(self, image_bytes: bytes) -> OCRResult:
            assert image_bytes == b"image"
            return OCRResult("Bob: like for like", "fake", "eng")

    result = pipeline.analyze_screenshot(b"image", ocr=FakeOCR())
    assert result.screenshot_ready is True
    assert result.messages[0].username == "Bob"
    assert result.moderation.screen_status == "VIOLATION_DETECTED"
    assert any(task.task_type == "WARN_USER" for task in result.tasks)


def test_analyze_screenshot_endpoint_rejects_bad_media() -> None:
    from fastapi.testclient import TestClient
    from chateyes.main import app

    response = TestClient(app).post(
        "/analyze-screenshot",
        files={"file": ("chat.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_analyze_screenshot_endpoint_uses_pipeline(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from chateyes import main
    from chateyes.models import ModerationResponse, OCRResponse
    from chateyes.pipeline import ScreenshotAnalysisResponse

    response_model = ScreenshotAnalysisResponse(
        screenshot_ready=True,
        ocr=OCRResponse(text="Alice: hello", engine="fake", language="eng"),
        messages=[],
        moderation=ModerationResponse(screen_status="CLEAN", total_violations=0, violations=[]),
        tasks=[],
    )
    monkeypatch.setattr(main, "analyze_screenshot", lambda image_bytes, role, warning_count: response_model)
    image = Image.new("RGB", (20, 20), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    response = TestClient(main.app).post(
        "/analyze-screenshot",
        files={"file": ("chat.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["ocr"]["engine"] == "fake"
