import pytest

from src.app.repository import VALID_DECISIONS, validate_feedback_decision


def test_valid_decisions_are_accepted() -> None:
    for decision in VALID_DECISIONS:
        assert validate_feedback_decision(decision) == decision


def test_expected_decision_vocabulary_is_present() -> None:
    # The reviewer UI offers exactly these options; keep them in sync.
    assert VALID_DECISIONS == {
        "approve", "reject", "escalate", "wrong category", "false positive", "false negative",
        "relevant prior", "not relevant", "needs specialist review",
    }


def test_invalid_decision_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_feedback_decision("definitely-not-a-decision")
    with pytest.raises(ValueError):
        validate_feedback_decision("")
