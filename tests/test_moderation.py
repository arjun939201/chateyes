from io import BytesIO

from PIL import Image
from fastapi.testclient import TestClient

from chateyes.language import detect_language, normalize_for_detection
from chateyes.main import app
from chateyes.ocr import TesseractOCR
from chateyes.rules import evaluate

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


def test_unicode_normalization_removes_zero_width_obfuscation() -> None:
    assert normalize_for_detection("s\u200bex") == "sex"


def test_script_language_detection() -> None:
    assert detect_language("नमस्ते") == "Hindi"
    assert detect_language("שלום") == "Hebrew"
    assert detect_language("مرحبا") == "Arabic"


def test_transliterated_language_detection() -> None:
    assert detect_language("aap kya hai") == "Transliterated Hindi"
    assert detect_language("ana habibi shukran") == "Transliterated Arabic"


def test_multilingual_metadata_is_attached_to_violation() -> None:
    response = client.post(
        "/moderate",
        json={"messages": [{"username": "user1", "text": "send nude pics", "detected_language": "Hindi"}]},
    )
    body = response.json()
    assert body["violations"][0]["detected_language"] == "English"


def test_transliterated_explicit_term_is_detected() -> None:
    response = client.post("/moderate", json={"messages": [{"username": "user2", "text": "chut"}]})
    body = response.json()
    assert body["violations"][0]["rule_id"] == "RULE_SEXUAL_EXPLICIT"
    assert body["violations"][0]["severity"] == "HIGH"


def test_all_four_rule_ids_are_registered() -> None:
    from chateyes.rules import RULES

    assert {rule.rule_id for rule in RULES} == {
        "RULE_SPAM_SOLICITATION",
        "RULE_SEXUAL_EXPLICIT",
        "RULE_HARASSMENT_HATE",
        "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA",
    }


def test_rule_precedence_keeps_strongest_match() -> None:
    matches = evaluate("send nude pics and like for like")
    assert len(matches) == 1
    assert matches[0].rule_id == "RULE_SEXUAL_EXPLICIT"
    assert matches[0].severity == "HIGH"


def test_confidence_threshold_can_suppress_rule() -> None:
    assert evaluate("like for like", confidence_threshold=0.96) == []
    assert evaluate("like for like", confidence_threshold=0.95)[0].rule_id == "RULE_SPAM_SOLICITATION"


def test_inappropriate_media_signal_is_reviewed() -> None:
    response = client.post(
        "/moderate",
        json={
            "messages": [{
                "username": "normal_user",
                "text": "shared a photo",
                "media_present": True,
                "media_description": "NSFW adult image",
            }]
        },
    )
    body = response.json()
    assert body["violations"][0]["rule_id"] == "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA"
    assert body["violations"][0]["recommended_action"] == "REVIEW"


def test_inappropriate_nickname_signal_is_reviewed() -> None:
    response = client.post(
        "/moderate",
        json={"messages": [{"username": "xxx_porn_star", "text": "hello", "media_present": True}]},
    )
    assert response.json()["violations"][0]["rule_id"] == "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA"


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
    response = client.post("/ocr", files={"file": ("message.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_ocr_endpoint_rejects_empty_image() -> None:
    response = client.post("/ocr", files={"file": ("empty.png", b"", "image/png")})
    assert response.status_code == 400
