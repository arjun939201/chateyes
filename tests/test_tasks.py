from fastapi.testclient import TestClient

from chateyes.main import app
from chateyes.models import ModerationResponse
from chateyes.tasks import generate_tasks

client = TestClient(app)


def test_tasks_wait_for_screenshot() -> None:
    response = client.post(
        "/tasks",
        json={"messages": [{"username": "bob", "text": "like for like"}], "screenshot_available": False},
    )
    assert response.status_code == 200
    assert response.json() == {"screenshot_ready": False, "total_tasks": 0, "tasks": []}


def test_mit_gets_first_warning_after_capture() -> None:
    response = client.post(
        "/tasks",
        json={"messages": [{"username": "bob", "text": "like for like"}], "role": "MIT", "screenshot_available": True},
    )
    body = response.json()
    types = [task["task_type"] for task in body["tasks"]]
    assert "CAPTURE_EVIDENCE" in types
    assert "DROP_SIGNATURE" in types
    assert "WARN_USER" in types
    assert "MOD_WARNING" not in types


def test_mit_after_two_warnings_gets_mod_warning_and_report_path() -> None:
    response = client.post(
        "/tasks",
        json={"messages": [{"username": "bob", "text": "like for like"}], "role": "MIT", "warning_count": 2},
    )
    types = [task["task_type"] for task in response.json()["tasks"]]
    assert "MOD_WARNING" in types
    assert "REPORT_USER" in types


def test_submod_escalates_after_two_warnings() -> None:
    moderation = ModerationResponse.model_validate({
        "screen_status": "VIOLATION_DETECTED",
        "total_violations": 1,
        "violations": [{
            "username": "bob",
            "original_text": "like for like",
            "detected_language": "English",
            "translated_english_summary": "Spam or solicitation",
            "rule_id": "RULE_SPAM_SOLICITATION",
            "severity": "LOW",
            "recommended_action": "WARN",
            "justification": "Spam",
        }],
    })
    tasks = generate_tasks(moderation, role="SUBMOD", warning_count=2)
    assert any(task.task_type == "CALL_MIT_MOD" for task in tasks)
    assert not any(task.task_type == "MOD_WARNING" for task in tasks)


def test_signature_or_moderator_presence_prevents_duplicate_report() -> None:
    response = client.post(
        "/tasks",
        json={"messages": [{"username": "bob", "text": "like for like"}], "signature_detected": True},
    )
    body = response.json()
    assert body["total_tasks"] == 1
    assert body["tasks"][0]["task_type"] == "SKIP_DUPLICATE"


def test_direct_nude_report_adds_mute_request() -> None:
    response = client.post(
        "/tasks",
        json={
            "messages": [{"username": "bob", "text": "shared a photo"}],
            "direct_report_flags": ["NUDE"],
        },
    )
    types = [task["task_type"] for task in response.json()["tasks"]]
    assert "REPORT_USER" in types
    assert "REQUEST_MUTE" in types
