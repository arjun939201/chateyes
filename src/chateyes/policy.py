from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModerationRole(StrEnum):
    SUBMOD = "SUBMOD"
    MIT = "MIT"
    MOD1 = "MOD1"
    MOD2 = "MOD2"


class FindingType(StrEnum):
    PERVERT = "PERVERT"
    UNDERAGE = "UNDERAGE"
    SCAM_ADVERTISING = "SCAM_ADVERTISING"
    INAPPROPRIATE_USERNAME = "INAPPROPRIATE_USERNAME"
    INAPPROPRIATE_PROFILE = "INAPPROPRIATE_PROFILE"
    INAPPROPRIATE_TILE = "INAPPROPRIATE_TILE"
    NUDE = "NUDE"
    EVADE = "EVADE"
    BANNED = "BANNED"
    ABUSE_SPAM = "ABUSE_SPAM"
    RUDENESS = "RUDENESS"
    EXPLICIT_LANGUAGE = "EXPLICIT_LANGUAGE"
    PROVOCATION = "PROVOCATION"


@dataclass(frozen=True)
class PolicyDecision:
    finding_type: FindingType
    direct_report: bool
    warning_required: bool
    normal_warnings_before_escalation: int
    escalate_to_mit_or_mod: bool
    request_profile_change: bool
    request_removal: bool
    request_mute: bool
    reason: str


# This table encodes the supplied Submod rulebook as workflow policy. It intentionally
# separates "what was detected" from "what a particular moderation role may do".
_DIRECT_REPORT = {
    FindingType.PERVERT,
    FindingType.UNDERAGE,
    FindingType.SCAM_ADVERTISING,
    FindingType.NUDE,
    FindingType.EVADE,
    FindingType.BANNED,
    FindingType.ABUSE_SPAM,
    FindingType.INAPPROPRIATE_TILE,
}

_PROFILE_CHANGE = {FindingType.INAPPROPRIATE_PROFILE}

_WARNING = {
    FindingType.RUDENESS,
    FindingType.EXPLICIT_LANGUAGE,
    FindingType.PROVOCATION,
}


def policy_for(
    finding_type: FindingType,
    *,
    role: ModerationRole = ModerationRole.SUBMOD,
    warning_count: int = 0,
    profile_changed: bool = False,
    repeated_inappropriate_uploads: int = 0,
) -> PolicyDecision:
    """Return the workflow permitted by the supplied moderation guidance.

    The source material contains different authority rules for Submods and MITs. The
    engine therefore models role explicitly rather than silently assuming one role.
    """
    if warning_count < 0 or repeated_inappropriate_uploads < 0:
        raise ValueError("counts cannot be negative")

    if finding_type in _DIRECT_REPORT:
        return PolicyDecision(
            finding_type=finding_type,
            direct_report=True,
            warning_required=False,
            normal_warnings_before_escalation=0,
            escalate_to_mit_or_mod=role == ModerationRole.SUBMOD,
            request_profile_change=False,
            request_removal=finding_type in {
                FindingType.NUDE,
                FindingType.INAPPROPRIATE_TILE,
            },
            request_mute=finding_type == FindingType.NUDE,
            reason="Direct report under the supplied moderation guidance; no normal warning is required.",
        )

    if finding_type in _PROFILE_CHANGE:
        changed = profile_changed
        remove_after_wait = not changed
        disable_upload = repeated_inappropriate_uploads >= 3
        return PolicyDecision(
            finding_type=finding_type,
            direct_report=remove_after_wait,
            warning_required=not changed,
            normal_warnings_before_escalation=0,
            escalate_to_mit_or_mod=True,
            request_profile_change=not changed,
            request_removal=remove_after_wait,
            request_mute=False,
            reason=(
                "Ask the user to change the inappropriate profile material; if it is not changed, "
                "report it for removal. After repeated inappropriate uploads, escalate for upload restriction."
                + (" Upload restriction threshold reached." if disable_upload else "")
            ),
        )

    if finding_type in _WARNING:
        if role == ModerationRole.SUBMOD:
            escalate = warning_count >= 2
            return PolicyDecision(
                finding_type=finding_type,
                direct_report=False,
                warning_required=not escalate,
                normal_warnings_before_escalation=2,
                escalate_to_mit_or_mod=escalate,
                request_profile_change=False,
                request_removal=False,
                request_mute=False,
                reason="Give up to two normal warnings, then call an MIT/Mod if the user continues.",
            )
        return PolicyDecision(
            finding_type=finding_type,
            direct_report=False,
            warning_required=True,
            normal_warnings_before_escalation=2,
            escalate_to_mit_or_mod=warning_count >= 2,
            request_profile_change=False,
            request_removal=False,
            request_mute=False,
            reason="Use the normal warning sequence described by the supplied rulebook.",
        )

    raise ValueError(f"Unsupported finding type: {finding_type}")


def should_skip_report(*, signature_present: bool, another_moderator_present: bool) -> bool:
    """Prevent duplicate evidence/report ownership when the source signals it."""
    return signature_present or another_moderator_present


def validate_underage(age: int) -> bool:
    """Return whether the supplied age meets the rulebook's 17+ threshold."""
    return age >= 17
