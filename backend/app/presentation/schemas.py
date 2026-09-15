from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: Optional[str] = None


class LocationResponse(BaseModel):
    id: int
    name: str
    code: str
    city: Optional[str] = None
    timezone: Optional[str] = None
    is_active: bool
    is_development_seed: bool
    registration_enabled: bool = True
    public_registration_token: Optional[str] = None
    registration_url: Optional[str] = None
    site_staff_count: int = 0
    site_admin_count: int = 0
    security_count: int = 0


class CreateLocationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    timezone: str = Field(..., min_length=1, max_length=64)
    registration_enabled: bool = True


class LocationStaffMember(BaseModel):
    user_id: int
    email: str
    display_name: Optional[str] = None
    role: str
    is_active: bool
    assigned_at: Optional[str] = None


class AddLocationStaffRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=50)

    model_config = {"extra": "forbid"}


class LocationRetireSummaryResponse(BaseModel):
    location_id: int
    name: str
    code: str
    is_active: bool
    assigned_staff: int
    onsite_visitors: int
    pending_approvals: int
    future_visits: int
    active_emergency: bool
    can_retire: bool
    blockers: List[str]


class LocationRetireRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)

    model_config = {"extra": "forbid"}


class LocationRetireResponse(BaseModel):
    location_id: int
    status: str
    code: str


class AssignedLocation(BaseModel):
    id: int
    name: str
    code: str
    city: Optional[str] = None


class MeResponse(BaseModel):
    id: int
    email: str
    display_name: Optional[str]
    role: str
    is_owner: bool
    is_active: bool
    permissions: List[str]
    location_ids: List[int]
    assigned_locations: List[AssignedLocation] = []
    auth_provider: Optional[str] = None
    force_password_change: bool = False
    entra_linked: bool = False
    last_login_at: Optional[str] = None
    identity_linked_at: Optional[str] = None


class PublicSiteResponse(BaseModel):
    name: str
    registration_enabled: bool


class PublicHostResponse(BaseModel):
    id: int
    name: str
    department: Optional[str] = None
    email: Optional[str] = None


class RegistrationAttachmentResponse(BaseModel):
    storage_key: str
    file_name: str
    kind: str
    mime_type: Optional[str] = None
    scanned: bool = False
    scan_ms: Optional[int] = None
    ocr_status: str = "unavailable"


class VisitorPhotoStageResponse(BaseModel):
    media_id: int
    status: str
    stored_filename: str
    mime_type: str
    file_size: int
    source: str


class PublicVisitorTypeResponse(BaseModel):
    code: str
    name: str
    requires_vendor_compliance: bool = False
    po_reference_required: bool = False


class PublicRegistrationRequest(BaseModel):
    site_token: str = Field(..., min_length=8, max_length=64)
    visitor_type: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=200)
    mobile: str = Field(..., min_length=7, max_length=30)
    email: str = Field(..., min_length=5, max_length=255)
    company: str = Field(..., min_length=1, max_length=255)
    host_id: int = Field(..., gt=0)
    purpose: str = Field(..., min_length=2, max_length=500)
    expected_duration_minutes: int = Field(..., gt=0)
    policy_accepted: bool


class PublicRegistrationResponse(BaseModel):
    registration_reference: str
    status: str
    visitor_name: str
    site_name: str
    duplicate: bool = False


class SelfRegistrationItem(BaseModel):
    id: int
    registration_reference: Optional[str]
    status: str
    visitor_name: str
    visitor_mobile: Optional[str]
    visitor_email: Optional[str]
    company: Optional[str]
    visitor_type: Optional[str]
    host_name: Optional[str]
    site_name: str
    site_id: int
    purpose: Optional[str]
    expected_duration_minutes: Optional[int]
    policy_accepted: bool
    submitted_at: str


class SelfRegistrationDetail(SelfRegistrationItem):
    policy_version: Optional[str]
    policy_accepted_at: Optional[str]


class SelfRegistrationListResponse(BaseModel):
    items: List[SelfRegistrationItem]
    total: int
    limit: int
    offset: int


class SelfRegistrationQrLocation(BaseModel):
    id: int
    name: str
    code: str
    city: Optional[str] = None
    timezone: Optional[str] = None
    registration_enabled: bool = True
    public_registration_token: Optional[str] = None
    registration_url: Optional[str] = None


class SelfRegistrationQrStats(BaseModel):
    today: int
    pending: int
    approved: int
    rejected: int


class SelfRegistrationQrConfigResponse(BaseModel):
    company_label: str
    app_name: str
    locations: List[SelfRegistrationQrLocation]
    location: SelfRegistrationQrLocation
    registration_url: str
    is_permanent: bool = True
    localhost_warning: bool = False
    stats: SelfRegistrationQrStats


class ApprovalHistoryItem(BaseModel):
    id: int
    decision: str
    actor_type: Optional[str] = "ADMIN_USER"
    actor_email: Optional[str]
    actor_role: Optional[str]
    actor_name: Optional[str] = None
    comment: Optional[str]
    reason_code: Optional[str]
    previous_status: str
    new_status: str
    created_at: Optional[str]


class ApprovalQueueItem(BaseModel):
    id: int
    registration_reference: Optional[str]
    status: str
    visitor_name: str
    visitor_mobile: Optional[str]
    visitor_email: Optional[str]
    company: Optional[str]
    visitor_type: Optional[str]
    host_name: Optional[str]
    site_name: str
    site_id: int
    purpose: Optional[str]
    expected_duration_minutes: Optional[int]
    policy_accepted: bool
    policy_version: Optional[str] = None
    submitted_at: Optional[str]
    approval_history: List[ApprovalHistoryItem] = []


class ApprovalListResponse(BaseModel):
    items: List[ApprovalQueueItem]
    total: int
    limit: int
    offset: int
    pending_count: int


class ApproveRequest(BaseModel):
    comment: Optional[str] = None


class RejectRequest(BaseModel):
    reason_code: str
    comment: Optional[str] = None


class RejectionReasonOption(BaseModel):
    code: str
    label: str


class OperationalVisitItem(BaseModel):
    id: int
    registration_reference: Optional[str]
    status: str
    visitor_name: str
    visitor_mobile: Optional[str]
    visitor_email: Optional[str]
    company: Optional[str]
    visitor_type: Optional[str]
    host_name: Optional[str]
    site_name: str
    site_id: int
    site_city: Optional[str] = None
    purpose: Optional[str]
    expected_duration_minutes: Optional[int]
    policy_accepted: bool
    policy_version: Optional[str] = None
    submitted_at: Optional[str]
    arrived_at: Optional[str] = None
    checked_in_at: Optional[str] = None
    checked_out_at: Optional[str] = None
    check_in_method: Optional[str] = None
    overstay: bool = False
    is_walk_in: bool = True
    approval_history: List[ApprovalHistoryItem] = []


class ExpectedTodayListResponse(BaseModel):
    items: List[OperationalVisitItem]
    total: int
    limit: int
    offset: int


class OnsiteListResponse(BaseModel):
    items: List[OperationalVisitItem]
    total: int
    limit: int
    offset: int
    onsite_count: int


class CreateInvitationRequest(BaseModel):
    location_id: int = Field(..., gt=0)
    visitor_type: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=200)
    mobile: str = Field(..., min_length=10, max_length=10, pattern=r"^[0-9]{10}$")
    email: Optional[str] = Field(None, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    host_id: Optional[int] = Field(None, gt=0)
    visit_date: str = Field(..., min_length=8, max_length=10)
    arrival_time: str = Field(..., min_length=4, max_length=5)
    expected_duration_minutes: int = Field(..., gt=0)
    purpose: str = Field(..., min_length=2, max_length=500)
    notes: Optional[str] = None
    policy_accepted: bool = True
    departure_time: Optional[str] = Field(None, max_length=5)
    designation: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=2000)
    vendor_company_id: Optional[int] = Field(None, gt=0)
    work_purpose: Optional[str] = Field(None, max_length=500)
    po_work_order_reference: Optional[str] = Field(None, max_length=100)
    safety_acknowledged: bool = False
    govt_id_type: Optional[str] = Field(None, max_length=50)
    govt_id_number: Optional[str] = Field(None, max_length=100)
    photo_storage_key: Optional[str] = Field(None, max_length=255)
    photo_media_id: Optional[int] = Field(None, gt=0)
    signature_storage_key: Optional[str] = Field(None, max_length=255)
    id_image_storage_key: Optional[str] = Field(None, max_length=255)
    nda_signed: bool = False
    ppe_required: bool = False
    safety_induction_completed: bool = False
    assets: Optional[List[str]] = None
    assets_other: Optional[str] = Field(None, max_length=200)
    vehicle_number: Optional[str] = Field(None, max_length=30)
    vehicle_type: Optional[str] = Field(None, max_length=30)


class CancelInvitationRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


class InvitationItem(BaseModel):
    id: int
    registration_reference: Optional[str]
    status: str
    source: Optional[str]
    visitor_name: str
    visitor_mobile: Optional[str]
    visitor_email: Optional[str]
    company: Optional[str]
    visitor_type: Optional[str]
    host_name: Optional[str]
    site_name: str
    site_id: int
    site_city: Optional[str] = None
    purpose: Optional[str]
    notes: Optional[str] = None
    expected_duration_minutes: Optional[int]
    scheduled_start: Optional[str]
    scheduled_end: Optional[str]
    submitted_at: Optional[str]
    invitation_status: str
    invitation_valid_from: Optional[str]
    invitation_valid_until: Optional[str]
    has_active_invitation: bool = False
    created_by_email: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancellation_reason: Optional[str] = None
    approval_history: List[ApprovalHistoryItem] = []
    invitation_url: Optional[str] = None


class InvitationListResponse(BaseModel):
    items: List[InvitationItem]
    total: int
    limit: int
    offset: int


class PublicInvitationResponse(BaseModel):
    visitor_name: str
    company: Optional[str]
    site_name: str
    site_city: Optional[str] = None
    host_name: Optional[str]
    purpose: Optional[str]
    scheduled_start: Optional[str]
    status: str
    invitation_token: str


class QrVerifyRequest(BaseModel):
    token: Optional[str] = None
    registration_reference: Optional[str] = None


class QrVerifyResponse(BaseModel):
    valid: bool
    code: str
    message: Optional[str] = None
    visit_id: int
    registration_reference: Optional[str]
    status: str
    source: Optional[str]
    visitor_name: str
    company: Optional[str]
    visitor_type: Optional[str]
    visitor_mobile: Optional[str]
    host_name: Optional[str]
    site_name: str
    site_id: int
    purpose: Optional[str]
    scheduled_start: Optional[str]
    scheduled_end: Optional[str]
    arrived_at: Optional[str] = None
    checked_in_at: Optional[str] = None
    invitation_status: Optional[str] = None
    can_mark_arrived: bool = False
    can_check_in: bool = False
    can_check_out: bool = False
    security_status: Optional[str] = None


class WatchlistItem(BaseModel):
    id: int
    scope_type: str
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    full_name: str
    mobile: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    reason_code: str
    reason_text: Optional[str] = None
    action_level: str
    status: str
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    created_at: Optional[str] = None
    deactivated_at: Optional[str] = None


class WatchlistListResponse(BaseModel):
    items: List[WatchlistItem]
    total: int
    limit: int
    offset: int


class CreateWatchlistRequest(BaseModel):
    scope_type: str = Field(..., min_length=1, max_length=20)
    location_id: Optional[int] = None
    full_name: str = Field(..., min_length=1, max_length=255)
    mobile: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    reason_code: str = Field(..., min_length=1, max_length=50)
    reason_text: Optional[str] = Field(None, max_length=500)
    action_level: str = Field(..., min_length=1, max_length=20)
    valid_from: str
    valid_until: Optional[str] = None


class UpdateWatchlistRequest(BaseModel):
    action_level: Optional[str] = Field(None, max_length=20)
    reason_text: Optional[str] = Field(None, max_length=500)
    valid_until: Optional[str] = None


class SecurityReviewItem(BaseModel):
    visit_id: int
    registration_reference: Optional[str] = None
    status: str
    source: Optional[str] = None
    security_status: str
    visitor_name: str
    visitor_mobile: Optional[str] = None
    visitor_email: Optional[str] = None
    company: Optional[str] = None
    visitor_type: Optional[str] = None
    host_name: Optional[str] = None
    site_name: str
    site_id: int
    purpose: Optional[str] = None
    screening_outcome: Optional[str] = None
    match_confidence: Optional[str] = None
    reason_summary: Optional[str] = None
    signals: List[str] = []
    screening_id: Optional[int] = None
    resolved: bool = False
    resolution: Optional[str] = None
    screened_at: Optional[str] = None


class SecurityReviewListResponse(BaseModel):
    items: List[SecurityReviewItem]
    total: int
    review_count: int
    blocked_count: int
    limit: int
    offset: int


class SecurityResolveRequest(BaseModel):
    comment: Optional[str] = Field(None, max_length=500)


class SecurityBlockRequest(BaseModel):
    comment: str = Field(..., min_length=1, max_length=500)


class BadgeItem(BaseModel):
    id: int
    visit_id: int
    badge_number: str
    status: str
    issued_at: Optional[str]
    printed_at: Optional[str]
    print_count: int
    expires_at: Optional[str]
    visitor_name: str
    company: Optional[str]
    visitor_type: Optional[str]
    host_name: Optional[str]
    site_name: str
    site_code: Optional[str]
    site_city: Optional[str] = None
    registration_reference: Optional[str]
    scheduled_start: Optional[str]
    visit_date: Optional[str]


class HostApprovalPublicResponse(BaseModel):
    state: str
    message: Optional[str] = None
    visit_status: Optional[str] = None
    visitor_name: str = ""
    company: Optional[str] = None
    visitor_type: Optional[str] = None
    site_name: str = ""
    purpose: Optional[str] = None
    is_walk_in: bool = True
    scheduled_display: Optional[str] = None
    expected_duration_minutes: Optional[int] = None
    can_approve: bool = False
    can_reject: bool = False


class HostApprovalActionResponse(BaseModel):
    state: str
    message: Optional[str] = None
    visitor_name: Optional[str] = None


class HostRejectRequest(BaseModel):
    reason_code: str = Field(..., min_length=1, max_length=50)
    comment: Optional[str] = Field(None, max_length=500)


class HostRejectionReasonOption(BaseModel):
    code: str
    label: str


class NotificationItem(BaseModel):
    id: int
    notification_type: str
    channel: str
    recipient: str
    visit_id: Optional[int] = None
    host_id: Optional[int] = None
    location_id: Optional[int] = None
    status: str
    subject: Optional[str] = None
    template_key: str
    attempt_count: int
    sent_at: Optional[str] = None
    failed_at: Optional[str] = None
    error_code: Optional[str] = None
    body_preview: Optional[str] = None
    dev_action_url: Optional[str] = None
    created_at: Optional[str] = None


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
    total: int
    limit: int
    offset: int


class VendorCompanyLocationItem(BaseModel):
    id: int
    name: str
    code: str


class VendorCompanyItem(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_email: Optional[str] = None
    primary_contact_mobile: Optional[str] = None
    is_active: bool = True
    locations: List[VendorCompanyLocationItem] = []
    created_at: Optional[str] = None
    contractors: Optional[List[dict]] = None
    duplicate_warnings: Optional[List[dict]] = None


class VendorCompanyListResponse(BaseModel):
    items: List[VendorCompanyItem]
    total: int
    limit: int
    offset: int


class CreateVendorCompanyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location_ids: List[int]
    code: Optional[str] = Field(None, max_length=50)
    primary_contact_name: Optional[str] = Field(None, max_length=255)
    primary_contact_email: Optional[str] = Field(None, max_length=255)
    primary_contact_mobile: Optional[str] = Field(None, max_length=50)


class VendorCompanyUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    primary_contact_name: Optional[str] = Field(None, max_length=255)
    primary_contact_email: Optional[str] = Field(None, max_length=255)
    primary_contact_mobile: Optional[str] = Field(None, max_length=50)


class CreateVendorVisitRequest(BaseModel):
    location_id: int
    visitor_type: str
    vendor_company_id: int
    full_name: str
    mobile: str
    email: str
    host_id: int
    work_purpose: str
    visit_date: str
    arrival_time: str
    expected_duration_minutes: int
    safety_acknowledged: bool
    po_work_order_reference: Optional[str] = Field(None, max_length=100)
    company: Optional[str] = Field(None, max_length=255)
    work_area: Optional[str] = Field(None, max_length=255)
    vendor_supervisor: Optional[str] = Field(None, max_length=255)
    trade_or_role: Optional[str] = Field(None, max_length=255)


class ComplianceReviewItem(BaseModel):
    visit_id: int
    registration_reference: Optional[str] = None
    visitor_name: str = ""
    vendor_company_name: Optional[str] = None
    site_name: Optional[str] = None
    site_id: Optional[int] = None
    compliance_status: Optional[str] = None
    issue: Optional[str] = None
    status: Optional[str] = None
    scheduled_start: Optional[str] = None


class ComplianceReviewListResponse(BaseModel):
    items: List[ComplianceReviewItem]
    total: int
    attention_count: int
    expiring_count: int = 0
    limit: int
    offset: int


class ContractorVisitListResponse(BaseModel):
    items: List[ComplianceReviewItem]
    total: int
    limit: int
    offset: int


class ComplianceSummaryResponse(BaseModel):
    compliance_status: str
    reason_summary: Optional[str] = None
    signals: List[str] = []
    evaluated_at: Optional[str] = None


class ComplianceVisitItem(BaseModel):
    id: int
    registration_reference: Optional[str] = None
    status: str
    visitor_name: Optional[str] = None
    site_name: Optional[str] = None
    compliance: Optional[ComplianceSummaryResponse] = None
    vendor_company_id: Optional[int] = None


class ComplianceDocumentItem(BaseModel):
    id: int
    requirement_id: int
    requirement_code: str
    requirement_name: str
    visitor_id: Optional[int] = None
    vendor_company_id: Optional[int] = None
    file_name: str
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    status: str
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    uploaded_at: Optional[str] = None
    verified_at: Optional[str] = None
    verified_by_user_id: Optional[int] = None
    verified_by_name: Optional[str] = None
    rejection_comment: Optional[str] = None
    scan_status: Optional[str] = None
    supersedes_id: Optional[int] = None
    is_current: Optional[bool] = False


class ComplianceRequirementItem(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    visitor_type_id: Optional[int] = None
    visitor_type_name: Optional[str] = None
    scope_type: str
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    location_code: Optional[str] = None
    document_owner_type: str
    document_required: bool
    validity_required: bool
    safety_acknowledgement_required: bool
    is_mandatory: bool
    is_active: bool
    expiry_warning_days: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreateComplianceRequirementRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    visitor_type_id: Optional[int] = None
    scope_type: str = "GLOBAL"
    location_id: Optional[int] = None
    document_owner_type: str = "VISITOR"
    document_required: bool = True
    validity_required: bool = True
    safety_acknowledgement_required: bool = False
    is_mandatory: bool = True
    expiry_warning_days: int = Field(30, ge=1, le=365)
    code: Optional[str] = Field(None, max_length=50)


class UpdateComplianceRequirementRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    is_mandatory: Optional[bool] = None
    validity_required: Optional[bool] = None
    expiry_warning_days: Optional[int] = Field(None, ge=1, le=365)
    document_required: Optional[bool] = None


class ComplianceRequirementStatusItem(BaseModel):
    requirement_id: int
    requirement_code: str
    requirement_name: str
    document_owner_type: str
    is_mandatory: bool
    validity_required: bool
    usability: str
    current_document_id: Optional[int] = None
    documents: List[ComplianceDocumentItem] = []


class ComplianceVisitDetailResponse(BaseModel):
    visit_id: int
    registration_reference: Optional[str] = None
    status: str
    visitor_id: Optional[int] = None
    visitor_name: str = ""
    visitor_mobile: Optional[str] = None
    visitor_email: Optional[str] = None
    visitor_type: Optional[str] = None
    vendor_company_id: Optional[int] = None
    vendor_company_name: Optional[str] = None
    site_id: Optional[int] = None
    site_name: Optional[str] = None
    host_name: Optional[str] = None
    work_purpose: Optional[str] = None
    po_work_order_reference: Optional[str] = None
    safety_acknowledged: bool = False
    safety_acknowledged_at: Optional[str] = None
    scheduled_start: Optional[str] = None
    evaluation_date: Optional[str] = None
    compliance: ComplianceSummaryResponse
    requirements: List[ComplianceRequirementStatusItem] = []


class RejectDocumentRequest(BaseModel):
    comment: str = Field(..., min_length=1, max_length=500)


class EmergencyCounts(BaseModel):
    total: int = 0
    unaccounted: int = 0
    safe: int = 0
    not_located: int = 0
    left_premises: int = 0
    pending: int = 0


class EmergencyEventItem(BaseModel):
    id: int
    location_id: int
    location_name: Optional[str] = None
    location_code: Optional[str] = None
    status: str
    started_at: Optional[str] = None
    started_by_user_id: int
    started_by_name: Optional[str] = None
    started_by_email: Optional[str] = None
    reason: str
    notes: Optional[str] = None
    visitor_snapshot_count: int = 0
    closed_at: Optional[str] = None
    closed_by_user_id: Optional[int] = None
    closed_by_name: Optional[str] = None
    closure_comment: Optional[str] = None
    counts: EmergencyCounts = EmergencyCounts()


class EmergencyOverviewItem(BaseModel):
    location_id: int
    location_name: str
    location_code: str
    has_active_emergency: bool
    active_emergency_id: Optional[int] = None
    current_onsite_count: int = 0


class EmergencyRollCallEntryItem(BaseModel):
    id: int
    emergency_event_id: int
    visit_id: int
    visitor_id: int
    visitor_name: str
    company: Optional[str] = None
    visitor_type: Optional[str] = None
    host_name: Optional[str] = None
    mobile: Optional[str] = None
    registration_reference: Optional[str] = None
    badge_number: Optional[str] = None
    checked_in_at: Optional[str] = None
    status: str
    status_label: str
    status_updated_at: Optional[str] = None
    status_updated_by_name: Optional[str] = None
    comment: Optional[str] = None
    version: int = 1
    visit_checked_out_after_start: bool = False
    current_visit_status: Optional[str] = None
    expected_duration_minutes: Optional[int] = None
    action_history: List[Dict[str, Any]] = []


class EmergencyHistoryListResponse(BaseModel):
    items: List[EmergencyEventItem]
    total: int
    limit: int
    offset: int


class StartEmergencyRequest(BaseModel):
    location_id: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class UpdateRollCallStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=30)
    comment: Optional[str] = Field(None, max_length=500)
    expected_version: Optional[int] = None


class CloseEmergencyRequest(BaseModel):
    closure_comment: Optional[str] = Field(None, max_length=500)
    confirm_unresolved: bool = False

