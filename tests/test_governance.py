from datetime import UTC, datetime, timedelta

import pytest

from src.risk.governance import (
    Actor,
    IndependentLabelingService,
    PromotionController,
    PromotionEvidence,
    promotion_readiness,
)


def test_independent_labels_remain_blind_until_two_reviewers_submit() -> None:
    service = IndependentLabelingService()
    start = datetime(2026, 7, 16, tzinfo=UTC)
    service.assign(Actor("queue-1", "queue_manager"), "case-1", ["reviewer-1", "reviewer-2"], assigned_at=start)
    first = service.submit(Actor("reviewer-1", "reviewer"), "case-1", "reject", submitted_at=start + timedelta(minutes=5))
    assert first["peer_labels_visible"] is False
    assert first["labels"] == []
    second = service.submit(Actor("reviewer-2", "reviewer"), "case-1", "approve", submitted_at=start + timedelta(minutes=8))
    assert second["peer_labels_visible"] is True
    assert second["state"] == "needs_adjudication"
    resolved = service.adjudicate(Actor("policy-1", "policy_owner"), "case-1", "reject")
    assert resolved["state"] == "adjudicated"


def test_rbac_denies_unassigned_and_wrong_role_operations() -> None:
    service = IndependentLabelingService()
    service.assign(Actor("queue-1", "queue_manager"), "case-1", ["reviewer-1", "reviewer-2"])
    with pytest.raises(PermissionError):
        service.submit(Actor("reviewer-3", "reviewer"), "case-1", "reject")
    with pytest.raises(PermissionError):
        service.assign(Actor("reviewer-1", "reviewer"), "case-2", ["reviewer-1", "reviewer-2"])


def test_promotion_fails_closed_and_rollback_is_audited() -> None:
    blocked = PromotionEvidence("candidate", "v1", 0.95, 1.0, 1.0, 0, 0, None, None, None)
    assert promotion_readiness(blocked)["status"] == "hold"
    controller = PromotionController("v1")
    with pytest.raises(PermissionError, match="HOLD"):
        controller.promote(Actor("release-1", "release_manager"), blocked, reason="test")
    ready = PromotionEvidence("candidate", "v1", 0.95, 1.0, 1.0, 100, 100, 0.9, 1.0, 0.98, True)
    with pytest.raises(PermissionError, match="policy-owner approval"):
        controller.promote(Actor("release-1", "release_manager"), ready, reason="all gates approved")
    controller.approve(Actor("policy-1", "policy_owner"), "candidate", reason="quality and policy review passed")
    promoted = controller.promote(Actor("release-1", "release_manager"), ready, reason="all gates approved")
    assert promoted["active_version"] == "candidate"
    rolled_back = controller.rollback(Actor("release-1", "release_manager"), reason="SLA regression")
    assert rolled_back["active_version"] == "v1"
    assert [item["event"] for item in controller.audit_log] == ["strategy.approved", "strategy.promoted", "strategy.rolled_back"]
