from __future__ import annotations

from app.domain.enums import VisitStatus

VALID_TRANSITIONS: dict[VisitStatus, frozenset[VisitStatus]] = {
    VisitStatus.DRAFT: frozenset({
        VisitStatus.PENDING_APPROVAL,
        VisitStatus.CANCELLED,
    }),
    VisitStatus.PENDING_APPROVAL: frozenset({
        VisitStatus.APPROVED,
        VisitStatus.REJECTED,
        VisitStatus.CANCELLED,
    }),
    VisitStatus.APPROVED: frozenset({
        VisitStatus.ARRIVED,
        VisitStatus.EXPECTED,
        VisitStatus.CANCELLED,
        VisitStatus.EXPIRED,
    }),
    VisitStatus.EXPECTED: frozenset({
        VisitStatus.ARRIVED,
        VisitStatus.CHECKED_IN,
        VisitStatus.CANCELLED,
        VisitStatus.EXPIRED,
        VisitStatus.BLOCKED,
    }),
    VisitStatus.ARRIVED: frozenset({
        VisitStatus.CHECKED_IN,
        VisitStatus.ONSITE,
        VisitStatus.BLOCKED,
    }),
    VisitStatus.CHECKED_IN: frozenset({
        VisitStatus.ONSITE,
        VisitStatus.CHECKED_OUT,
    }),
    VisitStatus.ONSITE: frozenset({
        VisitStatus.CHECKED_OUT,
        VisitStatus.OVERSTAYED,
    }),
    VisitStatus.CHECKED_OUT: frozenset(),
    VisitStatus.REJECTED: frozenset(),
    VisitStatus.CANCELLED: frozenset(),
    VisitStatus.EXPIRED: frozenset(),
    VisitStatus.BLOCKED: frozenset(),
    VisitStatus.OVERSTAYED: frozenset({
        VisitStatus.CHECKED_OUT,
    }),
}


class VisitStateError(Exception):
    def __init__(self, from_status: VisitStatus, to_status: VisitStatus, message: str | None = None):
        self.from_status = from_status
        self.to_status = to_status
        self.message = message or f"Invalid transition: {from_status.value} -> {to_status.value}"
        super().__init__(self.message)


def can_transition(from_status: VisitStatus, to_status: VisitStatus) -> bool:
    allowed = VALID_TRANSITIONS.get(from_status, frozenset())
    return to_status in allowed


def validate_transition(from_status: VisitStatus, to_status: VisitStatus) -> None:
    if not can_transition(from_status, to_status):
        raise VisitStateError(from_status, to_status)
