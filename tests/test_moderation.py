from io import BytesIO

from PIL import Image
from fastapi.testclient import TestClient

from chateyes.main import app
from chateyes.ocr import TesseractOCR

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_clean_response_matches_contract() -> None:
    response = client.post("/moderate", json={"messages": [{"username": "alice", "text": "Hello everyone"}]})
    assert response.status_code == 200
    assert response.json() == {"screen_status": "CLEAN", "total_violations": 0, "violations": []}


def test_spam_violation() -> None:
    response = client.post("/moderate", json={"messages": [{"username": "bob", "text": "like for like"}]})
    body = response.json()
    assert body["violations"][0]["rule_id"] == "RULE_SPAM_SOLICITATION"
    assert body["violations"][0]["recommended_action"] == "WARN"


def test_sexual_violation() -> None:
    response = client.post("/moderate", json={"messages": [{"username": "eve", "text": "send nude pics"}]})
    body = response.json()
    assert body["violations"][0]["rule_id"] == "RULE_SEXUAL_EXPLICIT"
    assert body["violations"][0]["severity"] == "HIGH"


def test_threat_violation() -> None:
    response = client.post("/moderate", json={"messages": [{"username": "mallory", "text": "I will kill you"}]})
    body = response.json()
    assert body["violations"][0]["rule_id"] == "RULE_HARASSMENT_HATE"
    assert body["violations"][0]["recommended_action"] == "BAN"


def _png_bytes() -> bytes:
    image = Image.new("RGB", (320, 100), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_ocr_adapter_normalizes_engine_output(monkeypatch) -> None:
    import pytesseract

    monkeypatch.setattr(pytesseract, "image_to_string", lambda image, lang: " Alice: Hello  \n\nBob: hi ")
    result = TesseractOCR().extract_text(_png_bytes())
    assert result.engine == "tesseract"
    assert result.language == "eng"
    assert result.text == "Alice: Hello\nBob: hi"


def test_ocr_endpoint_rejects_unsupported_media_type() -> None:
    response = client.post(
        "/ocr",
        files={"file": ("message.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_ocr_endpoint_rejects_empty_image() -> None:
    response = client.post(
        "/ocr",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400
