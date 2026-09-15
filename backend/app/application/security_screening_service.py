"""Deterministic security screening engine."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.identity_normalization import (
    name_similarity,
    normalize_company,
    normalize_email,
    normalize_mobile,
    normalize_person_name,
)
from app.core.config import settings
from app.domain.enums import (
    DuplicateSignalLevel,
    MatchConfidence,
    SecurityClearanceStatus,
    SecurityOutcome,
    SecurityResolution,
    VisitStatus,
)
from app.domain.models import SecurityScreening, Visit, Visitor, WatchlistEntry, WatchlistMatch


class SecurityScreeningError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _entry_effective(entry: WatchlistEntry, now: datetime) -> bool:
    if entry.status != "ACTIVE":
        return False
    vf = _as_utc(entry.valid_from)
    if vf > now:
        return False
    if entry.valid_until and _as_utc(entry.valid_until) < now:
        return False
    return True


def _is_name_only_entry(entry: WatchlistEntry) -> bool:
    return not entry.normalized_mobile and not entry.normalized_email


def _match_watchlist_entry(
    entry: WatchlistEntry,
    v_name: str,
    v_mobile: Optional[str],
    v_email: Optional[str],
    v_company: Optional[str],
) -> Tuple[MatchConfidence, List[str]]:
    signals: List[str] = []
    mobile_exact = v_mobile and entry.normalized_mobile and v_mobile == entry.normalized_mobile
    email_exact = v_email and entry.normalized_email and v_email == entry.normalized_email
    name_score = name_similarity(v_name, entry.normalized_name)
    company_score = name_similarity(v_company, entry.normalized_company) if v_company and entry.normalized_company else 0

    if mobile_exact:
        signals.append("Mobile exact match")
    if email_exact:
        signals.append("Email exact match")
    if name_score >= settings.name_strong_match_threshold:
        signals.append("Name strong similarity")
    elif name_score >= settings.name_possible_match_threshold:
        signals.append("Name possible similarity")
    if company_score >= settings.name_strong_match_threshold:
        signals.append("Company strong similarity")
    elif company_score >= settings.name_possible_match_threshold:
        signals.append("Company possible similarity")

    if _is_name_only_entry(entry):
        if name_score >= settings.name_possible_match_threshold:
            return MatchConfidence.POSSIBLE, signals
        return MatchConfidence.NONE, signals

    if mobile_exact and (name_score >= settings.name_possible_match_threshold or not entry.normalized_name):
        return MatchConfidence.EXACT, signals
    if email_exact and (name_score >= settings.name_possible_match_threshold or not entry.normalized_name):
        return MatchConfidence.EXACT, signals
    if mobile_exact:
        return MatchConfidence.STRONG, signals
    if email_exact:
        return MatchConfidence.STRONG, signals
    if name_score >= settings.name_strong_match_threshold and (mobile_exact or email_exact):
        return MatchConfidence.STRONG, signals
    if name_score >= settings.name_strong_match_threshold:
        return MatchConfidence.STRONG, signals
    if name_score >= settings.name_possible_match_threshold or company_score >= settings.name_possible_match_threshold:
        return MatchConfidence.POSSIBLE, signals
    return MatchConfidence.NONE, signals


def _confidence_rank(conf: MatchConfidence) -> int:
    return {
        MatchConfidence.NONE: 0,
        MatchConfidence.POSSIBLE: 1,
        MatchConfidence.STRONG: 2,
        MatchConfidence.EXACT: 3,
    }[conf]


def _outcome_from_watchlist(action_level: str, confidence: MatchConfidence) -> SecurityOutcome:
    if confidence == MatchConfidence.NONE:
        return SecurityOutcome.CLEAR
    if action_level == "BLOCK":
        if confidence == MatchConfidence.EXACT:
            return SecurityOutcome.BLOCKED
        return SecurityOutcome.REVIEW
    return SecurityOutcome.REVIEW


def _find_duplicate_visitor_signals(db: Session, visitor: Visitor, v_name: str, v_mobile: Optional[str], v_email: Optional[str], v_company: Optional[str]) -> Tuple[DuplicateSignalLevel, List[str]]:
    signals: List[str] = []
    others = db.query(Visitor).filter(Visitor.id != visitor.id).all()
    best = DuplicateSignalLevel.NONE
    for other in others:
        o_mobile = normalize_mobile(other.phone)
        o_email = normalize_email(other.email)
        o_name = normalize_person_name(other.full_name)
        o_company = normalize_company(other.company)
        if v_mobile and o_mobile and v_mobile == o_mobile:
            signals.append(f"Existing visitor record with same mobile (ID {other.id})")
            best = DuplicateSignalLevel.EXACT
        if v_email and o_email and v_email == o_email:
            signals.append(f"Existing visitor record with same email (ID {other.id})")
            if best != DuplicateSignalLevel.EXACT:
                best = DuplicateSignalLevel.STRONG
        ns = name_similarity(v_name, o_name)
        if ns >= settings.name_strong_match_threshold and (v_mobile == o_mobile or v_email == o_email):
            signals.append(f"Strong name match with existing visitor (ID {other.id})")
            if best in (DuplicateSignalLevel.NONE, DuplicateSignalLevel.POSSIBLE):
                best = DuplicateSignalLevel.STRONG
        elif ns >= settings.name_possible_match_threshold:
            if o_company and v_company and name_similarity(v_company, o_company) >= settings.name_possible_match_threshold:
                signals.append(f"Possible duplicate: similar name and company (ID {other.id})")
                if best == DuplicateSignalLevel.NONE:
                    best = DuplicateSignalLevel.POSSIBLE
    return best, signals


def _duplicate_visit_signals(db: Session, visit: Visit) -> Tuple[DuplicateSignalLevel, List[str]]:
    window = timedelta(minutes=settings.duplicate_visit_window_minutes)
    cutoff = _now() - window
    similar = (
        db.query(Visit)
        .filter(
            Visit.visitor_id == visit.visitor_id,
            Visit.location_id == visit.location_id,
            Visit.id != visit.id,
            Visit.created_at >= cutoff,
        )
        .all()
    )
    if not similar:
        return DuplicateSignalLevel.NONE, []
    signals = [f"Another visit for same visitor at this location within {settings.duplicate_visit_window_minutes} minutes"]
    if visit.host_id and any(v.host_id == visit.host_id for v in similar):
        signals.append("Same host in recent visit attempt")
    return DuplicateSignalLevel.LIKELY_DUPLICATE, signals


def _prior_rejection_signal(db: Session, visitor_id: int) -> List[str]:
    count = db.query(Visit).filter(
        Visit.visitor_id == visitor_id,
        Visit.status == VisitStatus.REJECTED.value,
    ).count()
    if count:
        return [f"Visitor has {count} previous rejected visit(s) — informational only"]
    return []


def screen_visit(db: Session, visit_id: int, trigger: str = "registration") -> SecurityScreening:
    visit = (
        db.query(Visit)
        .options(joinedload(Visit.visitor))
        .filter(Visit.id == visit_id)
        .first()
    )
    if not visit or not visit.visitor:
        raise SecurityScreeningError("VISIT_NOT_FOUND", "Visit not found.", 404)

    visitor = visit.visitor
    now = _now()
    v_name = normalize_person_name(visitor.full_name) or ""
    v_mobile = normalize_mobile(visitor.phone)
    v_email = normalize_email(visitor.email)
    v_company = normalize_company(visitor.company)

    all_signals: List[str] = []
    best_confidence = MatchConfidence.NONE
    best_entry: Optional[WatchlistEntry] = None
    match_records: List[Tuple[WatchlistEntry, MatchConfidence, List[str]]] = []

    entries = db.query(WatchlistEntry).filter(WatchlistEntry.status == "ACTIVE").all()
    for entry in entries:
        if not _entry_effective(entry, now):
            continue
        if entry.scope_type == "LOCATION" and entry.location_id != visit.location_id:
            continue
        conf, sigs = _match_watchlist_entry(entry, v_name, v_mobile, v_email, v_company)
        if conf != MatchConfidence.NONE:
            match_records.append((entry, conf, sigs))
            if _confidence_rank(conf) > _confidence_rank(best_confidence):
                best_confidence = conf
                best_entry = entry

    outcome = SecurityOutcome.CLEAR
    reason_summary = "No security concerns detected."

    if best_entry and best_confidence != MatchConfidence.NONE:
        outcome = _outcome_from_watchlist(best_entry.action_level, best_confidence)
        reason_summary = "Watchlist match detected"
        all_signals.extend([f"Watchlist: {s}" for s in match_records[0][2] if match_records])

    dup_level, dup_sigs = _find_duplicate_visitor_signals(db, visitor, v_name, v_mobile, v_email, v_company)
    visit_dup_level, visit_dup_sigs = _duplicate_visit_signals(db, visit)
    rejection_sigs = _prior_rejection_signal(db, visitor.id)

    combined_dup = dup_level
    if visit_dup_level != DuplicateSignalLevel.NONE:
        combined_dup = visit_dup_level
        all_signals.extend(visit_dup_sigs)

    if dup_sigs:
        all_signals.extend(dup_sigs)

    if rejection_sigs:
        all_signals.extend(rejection_sigs)

    if combined_dup in (DuplicateSignalLevel.EXACT, DuplicateSignalLevel.STRONG, DuplicateSignalLevel.LIKELY_DUPLICATE):
        if outcome == SecurityOutcome.CLEAR:
            outcome = SecurityOutcome.REVIEW
            reason_summary = "Duplicate visitor or visit signals require review"
    elif combined_dup == DuplicateSignalLevel.POSSIBLE and outcome == SecurityOutcome.CLEAR:
        outcome = SecurityOutcome.REVIEW
        reason_summary = "Possible duplicate visitor signal"

    clearance = SecurityClearanceStatus.CLEAR.value
    if outcome == SecurityOutcome.BLOCKED:
        clearance = SecurityClearanceStatus.BLOCKED.value
    elif outcome == SecurityOutcome.REVIEW:
        clearance = SecurityClearanceStatus.REVIEW.value

    prior_latest = get_latest_screening(db, visit.id)
    manual_clear = (
        visit.security_clearance_status == SecurityClearanceStatus.CLEAR.value
        and prior_latest
        and prior_latest.resolution == SecurityResolution.CLEAR_VISITOR.value
    )
    if manual_clear and outcome == SecurityOutcome.REVIEW:
        outcome = SecurityOutcome.CLEAR
        clearance = SecurityClearanceStatus.CLEAR.value
        reason_summary = "Prior manual security clearance retained for this visit"

    screening = SecurityScreening(
        visit_id=visit.id,
        visitor_id=visitor.id,
        location_id=visit.location_id,
        outcome=outcome.value,
        screened_at=now,
        screening_version=settings.security_screening_version,
        watchlist_match_count=len(match_records),
        highest_match_confidence=best_confidence.value if best_confidence != MatchConfidence.NONE else None,
        matched_watchlist_entry_id=best_entry.id if best_entry else None,
        duplicate_signal_level=combined_dup.value if combined_dup != DuplicateSignalLevel.NONE else None,
        reason_summary=reason_summary,
        signals_json=json.dumps(all_signals),
        trigger=trigger,
    )
    db.add(screening)
    db.flush()

    for entry, conf, sigs in match_records:
        db.add(
            WatchlistMatch(
                screening_id=screening.id,
                watchlist_entry_id=entry.id,
                confidence=conf.value,
                matched_signals=json.dumps(sigs),
            )
        )

    visit.security_clearance_status = clearance

    audit = AuditService(db)
    audit.record(
        action="SECURITY_SCREENING_COMPLETED",
        entity_type="security_screening",
        entity_id=str(screening.id),
        location_id=visit.location_id,
        after_value={"outcome": outcome.value, "trigger": trigger, "visit_id": visit.id},
    )
    if match_records:
        audit.record(
            action="WATCHLIST_MATCH_DETECTED",
            entity_type="visit",
            entity_id=str(visit.id),
            location_id=visit.location_id,
            after_value={"confidence": best_confidence.value, "watchlist_entry_id": best_entry.id if best_entry else None},
        )
    if combined_dup != DuplicateSignalLevel.NONE:
        audit.record(
            action="DUPLICATE_VISITOR_DETECTED",
            entity_type="visit",
            entity_id=str(visit.id),
            location_id=visit.location_id,
            after_value={"level": combined_dup.value},
        )

    return screening


def get_latest_screening(db: Session, visit_id: int) -> Optional[SecurityScreening]:
    return (
        db.query(SecurityScreening)
        .filter(SecurityScreening.visit_id == visit_id)
        .order_by(SecurityScreening.screened_at.desc())
        .first()
    )


def ensure_allows_approval(db: Session, visit_id: int) -> None:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise SecurityScreeningError("not_found", "Visit not found.", 404)
    status = visit.security_clearance_status or SecurityClearanceStatus.CLEAR.value
    if status == SecurityClearanceStatus.BLOCKED.value:
        raise SecurityScreeningError(
            "SECURITY_ACCESS_BLOCKED",
            "This visitor is blocked by security screening.",
            403,
        )
    if status == SecurityClearanceStatus.REVIEW.value:
        latest = get_latest_screening(db, visit_id)
        if not latest or not latest.resolution:
            raise SecurityScreeningError(
                "SECURITY_REVIEW_REQUIRED",
                "Security review must be completed before this visitor can be approved.",
                403,
            )


def ensure_allows_checkin(db: Session, visit_id: int) -> None:
    screen_visit(db, visit_id, trigger="check_in")
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise SecurityScreeningError("VISIT_NOT_FOUND", "Visit not found.", 404)
    status = visit.security_clearance_status
    if status == SecurityClearanceStatus.BLOCKED.value:
        raise SecurityScreeningError(
            "SECURITY_ACCESS_BLOCKED",
            "Check-in blocked by security screening.",
            403,
        )
    if status == SecurityClearanceStatus.REVIEW.value:
        latest = get_latest_screening(db, visit_id)
        if not latest or not latest.resolution:
            raise SecurityScreeningError(
                "SECURITY_REVIEW_REQUIRED",
                "Security review must be completed before check-in.",
                403,
            )


def screening_summary_for_visit(db: Session, visit_id: int) -> Dict[str, Any]:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        return {"security_status": SecurityClearanceStatus.CLEAR.value}
    latest = get_latest_screening(db, visit_id)
    signals: List[str] = []
    if latest and latest.signals_json:
        try:
            signals = json.loads(latest.signals_json)
        except json.JSONDecodeError:
            signals = []
    return {
        "security_status": visit.security_clearance_status,
        "screening_outcome": latest.outcome if latest else SecurityOutcome.CLEAR.value,
        "match_confidence": latest.highest_match_confidence if latest else None,
        "reason_summary": latest.reason_summary if latest else None,
        "signals": signals,
        "resolved": bool(latest and latest.resolution),
    }
