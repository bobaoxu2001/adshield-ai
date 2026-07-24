from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

ROLE_PERMISSIONS = {
    "reviewer": frozenset({"review.submit"}),
    "senior_reviewer": frozenset({"review.submit", "review.adjudicate"}),
    "queue_manager": frozenset({"review.assign", "sla.read"}),
    "policy_owner": frozenset({"review.adjudicate", "promotion.approve", "sla.read"}),
    "release_manager": frozenset({"promotion.execute", "rollback.execute", "sla.read"}),
    "auditor": frozenset({"audit.read", "sla.read"}),
}


@dataclass(frozen=True)
class Actor:
    actor_id: str
    role: str

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("Reviewer identity is required")
        if self.role not in ROLE_PERMISSIONS:
            raise ValueError(f"Unsupported role: {self.role}")


def require_permission(actor: Actor, permission: str) -> None:
    if permission not in ROLE_PERMISSIONS[actor.role]:
        raise PermissionError(f"Role {actor.role!r} cannot perform {permission!r}")


@dataclass(frozen=True)
class ReviewLabel:
    case_id: str
    reviewer_id: str
    decision: str
    submitted_at: datetime
    notes: str = ""


@dataclass
class ReviewAssignment:
    case_id: str
    reviewer_ids: tuple[str, ...]
    assigned_at: datetime
    due_at: datetime
    labels: list[ReviewLabel] = field(default_factory=list)
    adjudicated_decision: str | None = None
    adjudicator_id: str | None = None

    @property
    def state(self) -> str:
        if self.adjudicated_decision:
            return "adjudicated"
        if len(self.labels) < 2:
            return "awaiting_independent_labels"
        return "consensus" if len({item.decision for item in self.labels}) == 1 else "needs_adjudication"


class IndependentLabelingService:
    """In-memory domain service used by adapters backed by a governed database."""

    def __init__(self) -> None:
        self.assignments: dict[str, ReviewAssignment] = {}
        self.audit_log: list[dict[str, object]] = []

    def assign(
        self,
        actor: Actor,
        case_id: str,
        reviewer_ids: Iterable[str],
        *,
        assigned_at: datetime | None = None,
        sla_minutes: int = 60,
    ) -> ReviewAssignment:
        require_permission(actor, "review.assign")
        reviewers = tuple(dict.fromkeys(value.strip() for value in reviewer_ids if value.strip()))
        if len(reviewers) < 2:
            raise ValueError("Independent labeling requires at least two distinct reviewers")
        if sla_minutes < 1:
            raise ValueError("SLA minutes must be positive")
        if case_id in self.assignments:
            raise ValueError(f"Review assignment already exists for {case_id}")
        start = assigned_at or datetime.now(UTC)
        assignment = ReviewAssignment(case_id, reviewers, start, start + timedelta(minutes=sla_minutes))
        self.assignments[case_id] = assignment
        self._audit(actor, "review.assigned", case_id, {"reviewer_count": len(reviewers), "sla_minutes": sla_minutes})
        return assignment

    def submit(self, actor: Actor, case_id: str, decision: str, *, notes: str = "", submitted_at: datetime | None = None) -> dict[str, object]:
        require_permission(actor, "review.submit")
        assignment = self._assignment(case_id)
        if actor.actor_id not in assignment.reviewer_ids:
            raise PermissionError("Reviewer is not assigned to this case")
        if any(item.reviewer_id == actor.actor_id for item in assignment.labels):
            raise ValueError("A reviewer may submit only one independent label per case")
        if not decision.strip():
            raise ValueError("A reviewer decision is required")
        label = ReviewLabel(case_id, actor.actor_id, decision.strip(), submitted_at or datetime.now(UTC), notes.strip())
        assignment.labels.append(label)
        self._audit(actor, "review.label_submitted", case_id, {"decision": decision.strip()})
        # Peer decisions remain blind until the minimum independent-label count is met.
        reveal = len(assignment.labels) >= 2
        return {
            "case_id": case_id,
            "state": assignment.state,
            "submitted_labels": len(assignment.labels),
            "peer_labels_visible": reveal,
            "labels": [item.decision for item in assignment.labels] if reveal else [],
        }

    def adjudicate(self, actor: Actor, case_id: str, decision: str) -> dict[str, object]:
        require_permission(actor, "review.adjudicate")
        assignment = self._assignment(case_id)
        if assignment.state != "needs_adjudication":
            raise ValueError("Adjudication is allowed only after two disagreeing independent labels")
        assignment.adjudicated_decision = decision.strip()
        assignment.adjudicator_id = actor.actor_id
        self._audit(actor, "review.adjudicated", case_id, {"decision": decision.strip()})
        return {"case_id": case_id, "state": assignment.state, "decision": assignment.adjudicated_decision}

    def sla_snapshot(self, actor: Actor, *, now: datetime | None = None) -> dict[str, object]:
        require_permission(actor, "sla.read")
        point = now or datetime.now(UTC)
        completed = [item for item in self.assignments.values() if item.state in {"consensus", "adjudicated"}]
        completed_on_time = [item for item in completed if max(label.submitted_at for label in item.labels) <= item.due_at]
        open_items = [item for item in self.assignments.values() if item not in completed]
        overdue = [item for item in open_items if point > item.due_at]
        due_soon = [item for item in open_items if point <= item.due_at <= point + timedelta(minutes=15)]
        return {
            "measurement_scope": "persisted_review_assignments",
            "assignment_count": len(self.assignments),
            "open_count": len(open_items),
            "overdue_count": len(overdue),
            "due_within_15m_count": len(due_soon),
            "completed_on_time_rate": round(len(completed_on_time) / len(completed), 3) if completed else None,
        }

    def _assignment(self, case_id: str) -> ReviewAssignment:
        if case_id not in self.assignments:
            raise LookupError(f"No review assignment exists for {case_id}")
        return self.assignments[case_id]

    def _audit(self, actor: Actor, event: str, subject_id: str, details: dict[str, object]) -> None:
        self.audit_log.append({
            "event_id": len(self.audit_log) + 1,
            "event": event,
            "actor_id": actor.actor_id,
            "actor_role": actor.role,
            "subject_id": subject_id,
            "details": details,
            "recorded_at": datetime.now(UTC).isoformat(),
        })


@dataclass(frozen=True)
class PromotionEvidence:
    candidate_version: str
    rollback_target: str
    category_agreement: float
    routing_agreement: float
    exception_routing_agreement: float
    authorized_ad_records: int
    independently_labeled_ads: int
    independent_label_agreement: float | None
    reviewer_identity_coverage: float | None
    sla_compliance: float | None
    policy_owner_approved: bool = False


def promotion_readiness(evidence: PromotionEvidence) -> dict[str, object]:
    checks = [
        ("category_agreement", evidence.category_agreement >= 0.90, evidence.category_agreement, ">= 90%", "Benchmark"),
        ("routing_agreement", evidence.routing_agreement >= 0.90, evidence.routing_agreement, ">= 90%", "Benchmark"),
        ("exception_routing_agreement", evidence.exception_routing_agreement >= 0.90, evidence.exception_routing_agreement, ">= 90%", "Benchmark"),
        ("authorized_ad_records", evidence.authorized_ad_records >= 100, evidence.authorized_ad_records, ">= 100", "Data Governance"),
        ("independent_labels", evidence.independently_labeled_ads >= 100, evidence.independently_labeled_ads, ">= 100", "Review Operations"),
        ("label_agreement", evidence.independent_label_agreement is not None and evidence.independent_label_agreement >= 0.85, evidence.independent_label_agreement, ">= 85%", "Review Operations"),
        ("reviewer_identity", evidence.reviewer_identity_coverage is not None and evidence.reviewer_identity_coverage == 1.0, evidence.reviewer_identity_coverage, "100%", "Security"),
        ("sla_compliance", evidence.sla_compliance is not None and evidence.sla_compliance >= 0.95, evidence.sla_compliance, ">= 95%", "Queue Operations"),
        ("policy_owner_approval", evidence.policy_owner_approved, evidence.policy_owner_approved, "required", "Policy Owner"),
    ]
    rows = [{"key": key, "passed": passed, "observed": observed, "required": required, "owner": owner} for key, passed, observed, required, owner in checks]
    blockers = [item for item in rows if not item["passed"]]
    return {
        "candidate_version": evidence.candidate_version,
        "rollback_target": evidence.rollback_target,
        "status": "eligible_for_controlled_promotion" if not blockers else "hold",
        "checks": rows,
        "blockers": blockers,
        "decision": "All production gates passed; a release manager may execute controlled promotion." if not blockers else f"HOLD: {len(blockers)} production gates are not satisfied.",
    }


class PromotionController:
    def __init__(self, active_version: str) -> None:
        self.active_version = active_version
        self.previous_version: str | None = None
        self.approvals: dict[str, dict[str, str]] = {}
        self.audit_log: list[dict[str, object]] = []

    def approve(self, actor: Actor, candidate_version: str, *, reason: str) -> dict[str, object]:
        require_permission(actor, "promotion.approve")
        if not reason.strip():
            raise ValueError("Approval reason is required")
        self.approvals[candidate_version] = {"actor_id": actor.actor_id, "reason": reason.strip()}
        self._audit(actor, "strategy.approved", reason, candidate_version)
        return {"candidate_version": candidate_version, "approved_by": actor.actor_id, "status": "approved"}

    def promote(self, actor: Actor, evidence: PromotionEvidence, *, reason: str) -> dict[str, object]:
        require_permission(actor, "promotion.execute")
        if evidence.candidate_version not in self.approvals:
            raise PermissionError("HOLD: policy-owner approval is not recorded")
        readiness = promotion_readiness(replace(evidence, policy_owner_approved=True))
        if readiness["status"] != "eligible_for_controlled_promotion":
            raise PermissionError(readiness["decision"])
        if not reason.strip():
            raise ValueError("Promotion reason is required")
        self.previous_version = self.active_version
        self.active_version = evidence.candidate_version
        self._audit(actor, "strategy.promoted", reason, evidence.rollback_target)
        return {"active_version": self.active_version, "rollback_target": self.previous_version, "status": "enforced"}

    def rollback(self, actor: Actor, *, reason: str) -> dict[str, object]:
        require_permission(actor, "rollback.execute")
        if not self.previous_version:
            raise ValueError("No promoted version is available to roll back")
        if not reason.strip():
            raise ValueError("Rollback reason is required")
        failed_version = self.active_version
        self.active_version, self.previous_version = self.previous_version, self.active_version
        self._audit(actor, "strategy.rolled_back", reason, failed_version)
        return {"active_version": self.active_version, "rolled_back_version": failed_version, "status": "enforced"}

    def _audit(self, actor: Actor, event: str, reason: str, related_version: str) -> None:
        self.audit_log.append({"event": event, "actor_id": actor.actor_id, "actor_role": actor.role, "reason": reason, "related_version": related_version, "recorded_at": datetime.now(UTC).isoformat()})
