from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import ModerationResponse

Role = Literal["SUBMOD", "MIT", "MOD1", "MOD2"]
TaskType = Literal[
    "CAPTURE_EVIDENCE",
    "DROP_SIGNATURE",
    "WARN_USER",
    "MOD_WARNING",
    "CALL_MIT_MOD",
    "REPORT_USER",
    "REQUEST_PROFILE_CHANGE",
    "REQUEST_MEDIA_REMOVAL",
    "REQUEST_MUTE",
    "SKIP_DUPLICATE",
]
TaskStatus = Literal["PENDING", "COMPLETED", "SKIPPED"]

_DIRECT_REPORT_FLAGS = {
    "BANNED_USER",
    "EVADE_USER",
    "ABUSE_SPAM",
    "NUDE",
    "SEXUAL_ACTIVITY_MEDIA",
    "HITLER_NAZI_MEDIA",
    "RACISM_OR_RELIGION_MEDIA",
}

_WARNING_TEXT = {
    "RULE_SPAM_SOLICITATION": (
        "Please don't spam @username",
        "Please stop spamming users or action will be taken against you @username",
    ),
    "RULE_SEXUAL_EXPLICIT": (
        "Please don't use explicit language @username",
        "Please avoid using explicit language @username",
    ),
    "RULE_HARASSMENT_HATE": (
        "Please don't abuse or provoke users @username",
        "Please stop provoking or abusing users or action will be taken against you @username",
    ),
    "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA": (
        "Please keep your profile and media appropriate @username",
        "Please keep your profile and media appropriate or action will be taken against you @username",
    ),
}


@dataclass(frozen=True)
class TaskPlanItem:
    task_id: str
    task_type: TaskType
    status: TaskStatus
    username: str
    title: str
    instruction: str
    priority: int
    requires_screenshot: bool = True


def _task(
    task_id: str,
    task_type: TaskType,
    username: str,
    title: str,
    instruction: str,
    priority: int,
    *,
    requires_screenshot: bool = True,
) -> TaskPlanItem:
    return TaskPlanItem(
        task_id=task_id,
        task_type=task_type,
        status="PENDING",
        username=username,
        title=title,
        instruction=instruction,
        priority=priority,
        requires_screenshot=requires_screenshot,
    )


def generate_tasks(
    moderation: ModerationResponse,
    *,
    role: Role = "MIT",
    screenshot_available: bool = True,
    moderator_present: bool = False,
    signature_detected: bool = False,
    warning_count: int = 0,
    user_stopped: bool = False,
    direct_report_flags: set[str] | None = None,
) -> list[TaskPlanItem]:
    """Build an ordered, role-aware task list for a visible captured chat screen.

    This is intentionally a planner, not an automatic moderation action executor.
    It tells the human moderator what to do next while keeping authority boundaries
    explicit. Actual report/mute APIs can consume these task types later.
    """
    if not screenshot_available:
        return []
    if warning_count < 0:
        raise ValueError("warning_count cannot be negative")

    tasks: list[TaskPlanItem] = []
    flags = direct_report_flags or set()

    if moderator_present or signature_detected:
        reason = "Another moderator is already handling this evidence; do not duplicate the report."
        tasks.append(_task("screen-skip-duplicate", "SKIP_DUPLICATE", "", "Do not duplicate report", reason, 1))
        return tasks

    if moderation.violations:
        tasks.append(
            _task(
                "screen-capture-evidence",
                "CAPTURE_EVIDENCE",
                "",
                "Capture evidence",
                "Keep the screenshot showing the profile picture, violating chat, and the moderation message when applicable.",
                1,
            )
        )

        for index, violation in enumerate(moderation.violations, start=1):
            username = violation.username or "target user"
            prefix = f"v{index}-{username}"

            if violation.rule_id == "RULE_INAPPROPRIATE_NICKNAME_OR_MEDIA":
                tasks.append(
                    _task(
                        f"{prefix}-profile-change",
                        "REQUEST_PROFILE_CHANGE",
                        username,
                        "Ask user to change inappropriate profile/media",
                        f"Politely ask @{username} to change the inappropriate profile or media and explain the reason. Escalate to a Mod if it is not changed as required.",
                        2,
                    )
                )
                continue

            if role == "MIT":
                if warning_count < 2 and not user_stopped:
                    warning = _WARNING_TEXT.get(violation.rule_id, ("Please keep the chat appropriate @username", "Please stop violating the rules or action will be taken against you @username"))[min(warning_count, 1)]
                    tasks.append(
                        _task(
                            f"{prefix}-warn-{warning_count + 1}",
                            "WARN_USER",
                            username,
                            f"Give normal warning {warning_count + 1}/2",
                            warning.replace("@username", f"@{username}"),
                            3,
                        )
                    )
                elif warning_count >= 2 and not user_stopped:
                    tasks.append(
                        _task(
                            f"{prefix}-mod-warning",
                            "MOD_WARNING",
                            username,
                            "Give Mod Warning",
                            f"[Mod warn] kindly refrain from violating the chat rules; further violation will result in action being taken against your account @{username}",
                            2,
                        )
                    )
                    tasks.append(
                        _task(
                            f"{prefix}-report-after-mod-warning",
                            "REPORT_USER",
                            username,
                            "Report if violation continues",
                            f"If @{username} continues after the Mod Warning, drop your signature and submit the report with the evidence screenshot.",
                            2,
                        )
                    )
            elif role == "SUBMOD":
                if warning_count < 2 and not user_stopped:
                    warning = _WARNING_TEXT.get(violation.rule_id, ("Please keep the chat appropriate @username", "Please stop violating the rules @username"))[min(warning_count, 1)]
                    tasks.append(
                        _task(
                            f"{prefix}-warn-{warning_count + 1}",
                            "WARN_USER",
                            username,
                            f"Give normal warning {warning_count + 1}/2",
                            warning.replace("@username", f"@{username}"),
                            3,
                        )
                    )
                elif not user_stopped:
                    tasks.append(
                        _task(
                            f"{prefix}-call-mod",
                            "CALL_MIT_MOD",
                            username,
                            "Call an MIT/Mod",
                            f"Stop issuing warnings and call an MIT/Mod in the room to handle @{username}.",
                            2,
                        )
                    )
            else:
                tasks.append(
                    _task(
                        f"{prefix}-review",
                        "REPORT_USER",
                        username,
                        "Review and handle violation",
                        f"Review the evidence for @{username} and apply the appropriate moderator action.",
                        2,
                    )
                )

            if user_stopped and role == "MIT":
                tasks.append(
                    _task(
                        f"{prefix}-close",
                        "DROP_SIGNATURE",
                        username,
                        "Close the handled case",
                        "If no report is required, no further warning is needed; record/retain the evidence according to team procedure.",
                        4,
                    )
                )

    if flags & _DIRECT_REPORT_FLAGS:
        for flag in sorted(flags & _DIRECT_REPORT_FLAGS):
            action_id = flag.lower().replace("_", "-")
            title = "Direct report required"
            instruction = f"Directly report this {flag.replace('_', ' ').lower()} case; no warning is required under the supplied moderation notes."
            tasks.append(_task(f"direct-{action_id}", "REPORT_USER", "", title, instruction, 1))
            if flag == "NUDE":
                tasks.append(_task(f"direct-{action_id}-mute", "REQUEST_MUTE", "", "Request mute", "Request a mute from the appropriate Mod and never redistribute nude evidence in a moderation group.", 1))

    if tasks and not any(task.task_type == "DROP_SIGNATURE" for task in tasks):
        tasks.insert(
            1,
            _task(
                "screen-signature",
                "DROP_SIGNATURE",
                "",
                "Drop your moderation signature",
                "Place your recognizable signature in public chat before reporting or confirming the evidence so other moderators know it is already being handled.",
                2,
            ),
        )

    return sorted(tasks, key=lambda item: (item.priority, item.task_id))
