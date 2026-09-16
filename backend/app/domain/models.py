from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    entra_tenant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    entra_object_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    auth_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_credential_provisioned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    owner_password_user_established: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    direct_owner_sessions_valid_after: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    identity_linked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    location_assignments: Mapped[List["UserLocationAssignment"]] = relationship(
        back_populates="admin_user", cascade="all, delete-orphan"
    )


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_development_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    public_registration_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    registration_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user_assignments: Mapped[List["UserLocationAssignment"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )
    host_assignments: Mapped[List["HostLocationAssignment"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )


class UserLocationAssignment(Base):
    __tablename__ = "user_location_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    admin_user: Mapped["AdminUser"] = relationship(back_populates="location_assignments")
    location: Mapped["Location"] = relationship(back_populates="user_assignments")


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_development_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    location_assignments: Mapped[List["HostLocationAssignment"]] = relationship(
        back_populates="host", cascade="all, delete-orphan"
    )


class HostLocationAssignment(Base):
    __tablename__ = "host_location_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    host: Mapped["Host"] = relationship(back_populates="location_assignments")
    location: Mapped["Location"] = relationship(back_populates="host_assignments")


class VisitorType(Base):
    __tablename__ = "visitor_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_vendor_compliance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    po_reference_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Visitor(Base):
    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    privacy_state: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    anonymized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    visitor_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visitor_types.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    visitor_type: Mapped[Optional["VisitorType"]] = relationship()


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    registration_reference: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True, index=True)
    host_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hosts.id"), nullable=True, index=True)
    host_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_duration_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)
    expected_arrival: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    arrival_recorded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    arrival_location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    check_in_location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True)
    check_in_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    checked_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    policy_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registration_metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    scheduled_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    invitation_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    invitation_valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invitation_valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invitation_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    security_clearance_status: Mapped[str] = mapped_column(String(20), nullable=False, default="CLEAR", index=True)
    compliance_status: Mapped[str] = mapped_column(String(30), nullable=False, default="COMPLIANT", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    visitor: Mapped["Visitor"] = relationship()
    host: Mapped[Optional["Host"]] = relationship()
    location: Mapped["Location"] = relationship(foreign_keys=[location_id])
    created_by: Mapped[Optional["AdminUser"]] = relationship(foreign_keys=[created_by_user_id])
    approvals: Mapped[List["VisitApproval"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    host_approval_requests: Mapped[List["HostApprovalRequest"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    badges: Mapped[List["VisitorBadge"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    security_screenings: Mapped[List["SecurityScreening"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    vendor_visit_details: Mapped[Optional["VendorVisitDetails"]] = relationship(
        back_populates="visit", uselist=False, cascade="all, delete-orphan"
    )
    compliance_evaluations: Mapped[List["ComplianceEvaluation"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    visitor_media: Mapped[List["VisitorMedia"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )


class VisitorMedia(Base):
    __tablename__ = "visitor_media"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visitor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visitors.id"), nullable=True, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visits.id"), nullable=True, index=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    media_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="STAGED", index=True)
    storage_rel_path: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), nullable=False)
    retention_category: Mapped[str] = mapped_column(String(30), nullable=False, default="VISITOR_PII")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    visit: Mapped[Optional["Visit"]] = relationship(back_populates="visitor_media")
    visitor: Mapped[Optional["Visitor"]] = relationship()
    location: Mapped[Optional["Location"]] = relationship()


class VisitorBadge(Base):
    __tablename__ = "visitor_badges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, index=True)
    badge_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    issued_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    print_count: Mapped[int] = mapped_column(default=0, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    visit: Mapped["Visit"] = relationship(back_populates="badges")


class VisitApproval(Base):
    __tablename__ = "visit_approvals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ADMIN_USER")
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    actor_host_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hosts.id"), nullable=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    previous_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    visit: Mapped["Visit"] = relationship(back_populates="approvals")


class HostApprovalRequest(Base):
    __tablename__ = "host_approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, index=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id"), nullable=False, index=True)
    host_email_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_for_reason: Mapped[str] = mapped_column(String(20), nullable=False, default="INITIAL")

    visit: Mapped["Visit"] = relationship(back_populates="host_approval_requests")
    host: Mapped["Host"] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="EMAIL")
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visits.id"), nullable=True, index=True)
    host_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hosts.id"), nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    body_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dev_action_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    normalized_mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_level: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    location: Mapped[Optional["Location"]] = relationship()


class SecurityScreening(Base):
    __tablename__ = "security_screenings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, index=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    screened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    screening_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    watchlist_match_count: Mapped[int] = mapped_column(default=0, nullable=False)
    highest_match_confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    matched_watchlist_entry_id: Mapped[Optional[int]] = mapped_column(ForeignKey("watchlist_entries.id"), nullable=True)
    duplicate_signal_level: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    reason_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signals_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    resolution_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    visit: Mapped["Visit"] = relationship(back_populates="security_screenings")
    matches: Mapped[List["WatchlistMatch"]] = relationship(
        back_populates="screening", cascade="all, delete-orphan"
    )


class WatchlistMatch(Base):
    __tablename__ = "watchlist_matches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("security_screenings.id"), nullable=False, index=True)
    watchlist_entry_id: Mapped[int] = mapped_column(ForeignKey("watchlist_entries.id"), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    matched_signals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    screening: Mapped["SecurityScreening"] = relationship(back_populates="matches")


class VendorCompany(Base):
    __tablename__ = "vendor_companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    primary_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_contact_mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    locations: Mapped[List["VendorCompanyLocation"]] = relationship(
        back_populates="vendor_company", cascade="all, delete-orphan"
    )


class VendorCompanyLocation(Base):
    __tablename__ = "vendor_company_locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vendor_company_id: Mapped[int] = mapped_column(ForeignKey("vendor_companies.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vendor_company: Mapped["VendorCompany"] = relationship(back_populates="locations")
    location: Mapped["Location"] = relationship()


class VendorVisitorProfile(Base):
    __tablename__ = "vendor_visitor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id"), nullable=False, index=True)
    vendor_company_id: Mapped[int] = mapped_column(ForeignKey("vendor_companies.id"), nullable=False, index=True)
    employee_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    trade_or_role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supervisor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    visitor: Mapped["Visitor"] = relationship()
    vendor_company: Mapped["VendorCompany"] = relationship()


class VendorVisitDetails(Base):
    __tablename__ = "vendor_visit_details"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, unique=True, index=True)
    vendor_company_id: Mapped[int] = mapped_column(ForeignKey("vendor_companies.id"), nullable=False, index=True)
    work_purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    po_work_order_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    work_area: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vendor_supervisor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_contact_host_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hosts.id"), nullable=True)
    safety_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    safety_acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    safety_policy_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    visit: Mapped["Visit"] = relationship(back_populates="vendor_visit_details")
    vendor_company: Mapped["VendorCompany"] = relationship()


class ComplianceRequirement(Base):
    __tablename__ = "compliance_requirements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visitor_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visitor_types.id"), nullable=True, index=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default="GLOBAL")
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    document_owner_type: Mapped[str] = mapped_column(String(20), nullable=False, default="VISITOR")
    document_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validity_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    safety_acknowledgement_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expiry_warning_days: Mapped[int] = mapped_column(default=30, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ComplianceDocument(Base):
    __tablename__ = "compliance_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("compliance_requirements.id"), nullable=False, index=True)
    visitor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visitors.id"), nullable=True, index=True)
    vendor_company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendor_companies.id"), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    uploaded_by_actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ADMIN_USER")
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_VERIFICATION", index=True)
    scan_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    storage_state: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="STORED")
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    encryption_version: Mapped[Optional[int]] = mapped_column(nullable=True)
    purged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    malware_scan_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    malware_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    rejection_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supersedes_id: Mapped[Optional[int]] = mapped_column(ForeignKey("compliance_documents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    requirement: Mapped["ComplianceRequirement"] = relationship()


class ComplianceEvaluation(Base):
    __tablename__ = "compliance_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    evaluation_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signals_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    visit: Mapped["Visit"] = relationship(back_populates="compliance_evaluations")


class EmergencyEvent(Base):
    __tablename__ = "emergency_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_by_user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visitor_snapshot_count: Mapped[int] = mapped_column(nullable=False, default=0)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    closure_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    location: Mapped["Location"] = relationship(foreign_keys=[location_id])
    roll_call_entries: Mapped[List["EmergencyRollCallEntry"]] = relationship(back_populates="emergency_event")


class EmergencyRollCallEntry(Base):
    __tablename__ = "emergency_roll_call_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    emergency_event_id: Mapped[int] = mapped_column(ForeignKey("emergency_events.id"), nullable=False, index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, index=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id"), nullable=False, index=True)
    snapshot_visitor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    snapshot_visitor_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    snapshot_host_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    snapshot_mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    snapshot_registration_reference: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    snapshot_badge_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    snapshot_checked_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="UNACCOUNTED", index=True)
    status_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status_updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    visit_checked_out_after_start: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    emergency_event: Mapped["EmergencyEvent"] = relationship(back_populates="roll_call_entries")
    visit: Mapped["Visit"] = relationship(foreign_keys=[visit_id])
    actions: Mapped[List["EmergencyRollCallAction"]] = relationship(back_populates="roll_call_entry")


class EmergencyRollCallAction(Base):
    __tablename__ = "emergency_roll_call_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    emergency_event_id: Mapped[int] = mapped_column(ForeignKey("emergency_events.id"), nullable=False, index=True)
    roll_call_entry_id: Mapped[int] = mapped_column(ForeignKey("emergency_roll_call_entries.id"), nullable=False, index=True)
    old_status: Mapped[str] = mapped_column(String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), nullable=False)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    roll_call_entry: Mapped["EmergencyRollCallEntry"] = relationship(back_populates="actions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True, index=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    integrity_sequence: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    previous_integrity_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    integrity_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    integrity_version: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AuditIntegrityChain(Base):
    __tablename__ = "audit_integrity_chain"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    last_sequence: Mapped[int] = mapped_column(default=0, nullable=False)
    last_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    version: Mapped[int] = mapped_column(default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default="GLOBAL")
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True)
    retention_days: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DataRetentionRun(Base):
    __tablename__ = "data_retention_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("data_retention_policies.id"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    eligible_count: Mapped[int] = mapped_column(default=0, nullable=False)
    processed_count: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataRetentionRunDedupe(Base):
    __tablename__ = "data_retention_run_dedupe"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("data_retention_policies.id"), nullable=False)
    scheduled_date: Mapped[str] = mapped_column(String(10), nullable=False)
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_retention_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visits.id"), nullable=True, index=True)
    visitor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visitors.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="INFORMATION", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    rules_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AISession(Base):
    __tablename__ = "ai_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AIInteraction(Base):
    __tablename__ = "ai_interactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), nullable=False, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_sessions.id"), nullable=True, index=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    location_scope_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    question_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="COMPLETED")
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class LocationAccessConfiguration(Base):
    __tablename__ = "location_access_configurations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, unique=True, index=True)
    access_control_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_key: Mapped[str] = mapped_column(String(50), nullable=False, default="disabled")
    default_access_profile_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    credential_grace_minutes: Mapped[int] = mapped_column(default=30, nullable=False)
    max_credential_duration_minutes: Mapped[int] = mapped_column(default=720, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    location: Mapped["Location"] = relationship()


class AccessProfile(Base):
    __tablename__ = "access_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_external_profile_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    location: Mapped["Location"] = relationship()


class VisitorTypeAccessProfile(Base):
    __tablename__ = "visitor_type_access_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    visitor_type_id: Mapped[int] = mapped_column(ForeignKey("visitor_types.id"), nullable=False, index=True)
    access_profile_id: Mapped[int] = mapped_column(ForeignKey("access_profiles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VisitorAccessCredential(Base):
    __tablename__ = "visitor_access_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, index=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    access_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("access_profiles.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    provider_key: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_credential_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provisioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AccessProvisioningAttempt(Base):
    __tablename__ = "access_provisioning_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    access_credential_id: Mapped[int] = mapped_column(ForeignKey("visitor_access_credentials.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(default=1, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BadgePrinter(Base):
    __tablename__ = "badge_printers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_external_printer_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BadgePrintJob(Base):
    __tablename__ = "badge_print_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visitor_badge_id: Mapped[int] = mapped_column(ForeignKey("visitor_badges.id"), nullable=False, index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("badge_printers.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_job_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RuntimeLease(Base):
    __tablename__ = "runtime_leases"

    lease_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    leased_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(default=0, nullable=False)
    last_cycle_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_cycle_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
