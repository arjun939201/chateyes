import pytest

from chateyes.policy import (
    FindingType,
    ModerationRole,
    policy_for,
    should_skip_report,
    validate_underage,
)


def test_direct_report_finding_skips_normal_warning() -> None:
    decision = policy_for(FindingType.UNDERAGE)
    assert decision.direct_report is True
    assert decision.warning_required is False
    assert decision.normal_warnings_before_escalation == 0


def test_nude_report_requests_mute_and_removal() -> None:
    decision = policy_for(FindingType.NUDE)
    assert decision.direct_report is True
    assert decision.request_removal is True
    assert decision.request_mute is True


def test_submod_normal_warning_sequence_escalates_after_two() -> None:
    first = policy_for(FindingType.RUDENESS, warning_count=0)
    second = policy_for(FindingType.RUDENESS, warning_count=1)
    third = policy_for(FindingType.RUDENESS, warning_count=2)
    assert first.warning_required is True
    assert second.warning_required is True
    assert third.warning_required is False
    assert third.escalate_to_mit_or_mod is True


def test_inappropriate_profile_requires_change_before_removal() -> None:
    decision = policy_for(FindingType.INAPPROPRIATE_PROFILE, profile_changed=False)
    assert decision.warning_required is True
    assert decision.request_profile_change is True
    assert decision.request_removal is True


def test_three_inappropriate_uploads_reaches_restriction_threshold() -> None:
    decision = policy_for(
        FindingType.INAPPROPRIATE_PROFILE,
        repeated_inappropriate_uploads=3,
    )
    assert decision.escalate_to_mit_or_mod is True
    assert "restriction" in decision.reason.lower()


def test_signature_or_existing_moderator_blocks_duplicate_report() -> None:
    assert should_skip_report(signature_present=True, another_moderator_present=False)
    assert should_skip_report(signature_present=False, another_moderator_present=True)
    assert not should_skip_report(signature_present=False, another_moderator_present=False)


def test_underage_threshold_is_strictly_below_seventeen() -> None:
    assert validate_underage(16) is False
    assert validate_underage(17) is True


def test_negative_counts_are_rejected() -> None:
    with pytest.raises(ValueError):
        policy_for(FindingType.RUDENESS, warning_count=-1)
