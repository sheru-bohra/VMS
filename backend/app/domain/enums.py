from enum import Enum


class AdminRole(str, Enum):
    GLOBAL_ADMIN = "GLOBAL_ADMIN"
    HEAD_ADMIN = "HEAD_ADMIN"
    SITE_ADMIN = "SITE_ADMIN"
    SECURITY = "SECURITY"


class CheckInMethod(str, Enum):
    ADMIN_MANUAL = "ADMIN_MANUAL"


class VisitSource(str, Enum):
    SELF_REGISTRATION = "self_registration"
    ADVANCE_REGISTRATION = "advance_registration"


class BadgeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    VOID = "VOID"


class EmergencyEventStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class EmergencyReason(str, Enum):
    EMERGENCY = "EMERGENCY"
    EVACUATION_DRILL = "EVACUATION_DRILL"
    OTHER = "OTHER"


class RollCallEntryStatus(str, Enum):
    UNACCOUNTED = "UNACCOUNTED"
    SAFE = "SAFE"
    NOT_LOCATED = "NOT_LOCATED"
    LEFT_PREMISES = "LEFT_PREMISES"


class VisitStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EXPECTED = "EXPECTED"
    ARRIVED = "ARRIVED"
    CHECKED_IN = "CHECKED_IN"
    ONSITE = "ONSITE"
    CHECKED_OUT = "CHECKED_OUT"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"
    OVERSTAYED = "OVERSTAYED"


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalActorType(str, Enum):
    ADMIN_USER = "ADMIN_USER"
    HOST_LINK = "HOST_LINK"


class HostApprovalRequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"


class NotificationType(str, Enum):
    HOST_APPROVAL_REQUEST = "HOST_APPROVAL_REQUEST"
    VISITOR_ARRIVED = "VISITOR_ARRIVED"
    UPCOMING_VISIT_REMINDER = "UPCOMING_VISIT_REMINDER"
    VISIT_CANCELLED_HOST_NOTICE = "VISIT_CANCELLED_HOST_NOTICE"
    VISITOR_INVITATION = "VISITOR_INVITATION"
    VISITOR_INVITATION_CANCELLED = "VISITOR_INVITATION_CANCELLED"


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WatchlistScopeType(str, Enum):
    GLOBAL = "GLOBAL"
    LOCATION = "LOCATION"


class WatchlistActionLevel(str, Enum):
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class WatchlistEntryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"


class WatchlistReasonCode(str, Enum):
    PREVIOUS_SECURITY_INCIDENT = "PREVIOUS_SECURITY_INCIDENT"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    REPEATED_POLICY_VIOLATION = "REPEATED_POLICY_VIOLATION"
    INTERNAL_SECURITY_NOTICE = "INTERNAL_SECURITY_NOTICE"
    OTHER = "OTHER"


WATCHLIST_REASON_LABELS = {
    WatchlistReasonCode.PREVIOUS_SECURITY_INCIDENT: "Previous security incident",
    WatchlistReasonCode.ACCESS_RESTRICTED: "Access restricted",
    WatchlistReasonCode.REPEATED_POLICY_VIOLATION: "Repeated policy violation",
    WatchlistReasonCode.INTERNAL_SECURITY_NOTICE: "Internal security notice",
    WatchlistReasonCode.OTHER: "Other",
}


class SecurityOutcome(str, Enum):
    CLEAR = "CLEAR"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"


class SecurityClearanceStatus(str, Enum):
    CLEAR = "CLEAR"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"


class MatchConfidence(str, Enum):
    EXACT = "EXACT"
    STRONG = "STRONG"
    POSSIBLE = "POSSIBLE"
    NONE = "NONE"


class DuplicateSignalLevel(str, Enum):
    EXACT = "EXACT"
    STRONG = "STRONG"
    POSSIBLE = "POSSIBLE"
    LIKELY_DUPLICATE = "LIKELY_DUPLICATE"
    NONE = "NONE"


class SecurityResolution(str, Enum):
    CLEAR_VISITOR = "CLEAR_VISITOR"
    KEEP_BLOCKED = "KEEP_BLOCKED"


class ComplianceScopeType(str, Enum):
    GLOBAL = "GLOBAL"
    LOCATION = "LOCATION"


class ComplianceDocumentOwnerType(str, Enum):
    COMPANY = "COMPANY"
    VISITOR = "VISITOR"


class ComplianceDocumentStatus(str, Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VALID = "VALID"
    EXPIRING = "EXPIRING"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    EXPIRING = "EXPIRING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NON_COMPLIANT = "NON_COMPLIANT"


class RejectionReason(str, Enum):
    HOST_UNAVAILABLE = "HOST_UNAVAILABLE"
    VISIT_NOT_AUTHORIZED = "VISIT_NOT_AUTHORIZED"
    INCORRECT_DETAILS = "INCORRECT_DETAILS"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    SITE_ACCESS_NOT_PERMITTED = "SITE_ACCESS_NOT_PERMITTED"
    RESCHEDULE_REQUEST = "RESCHEDULE_REQUEST"
    OTHER = "OTHER"


REJECTION_REASON_LABELS = {
    RejectionReason.HOST_UNAVAILABLE: "Host unavailable",
    RejectionReason.VISIT_NOT_AUTHORIZED: "Visit not authorized",
    RejectionReason.INCORRECT_DETAILS: "Incorrect registration details",
    RejectionReason.DUPLICATE_REQUEST: "Duplicate request",
    RejectionReason.SITE_ACCESS_NOT_PERMITTED: "Site access not permitted",
    RejectionReason.RESCHEDULE_REQUEST: "Please reschedule",
    RejectionReason.OTHER: "Other",
}

HOST_REJECTION_REASONS = [
    RejectionReason.HOST_UNAVAILABLE,
    RejectionReason.VISIT_NOT_AUTHORIZED,
    RejectionReason.INCORRECT_DETAILS,
    RejectionReason.RESCHEDULE_REQUEST,
    RejectionReason.OTHER,
]


class Permission(str, Enum):
    VISITOR_READ = "visitor.read"
    VISITOR_VERIFY = "visitor.verify"
    VISITOR_CREATE = "visitor.create"
    VISITOR_UPDATE = "visitor.update"
    VISITOR_CHECKIN = "visitor.checkin"
    VISITOR_CHECKOUT = "visitor.checkout"

    ARRIVAL_READ = "arrival.read"
    ARRIVAL_MANAGE = "arrival.manage"

    CHECKIN_READ = "checkin.read"
    CHECKIN_PERFORM = "checkin.perform"

    CHECKOUT_PERFORM = "checkout.perform"

    REGISTRATION_READ = "registration.read"
    REGISTRATION_MANAGE = "registration.manage"

    APPROVAL_READ = "approval.read"
    APPROVAL_MANAGE = "approval.manage"
    APPROVAL_APPROVE = "approval.approve"
    APPROVAL_REJECT = "approval.reject"

    ONSITE_READ = "onsite.read"

    INVITATION_READ = "invitation.read"
    INVITATION_CREATE = "invitation.create"
    INVITATION_CANCEL = "invitation.cancel"

    VISITOR_QR_VERIFY = "visitor_qr.verify"

    BADGE_READ = "badge.read"
    BADGE_ISSUE = "badge.issue"
    BADGE_PRINT = "badge.print"

    NOTIFICATION_READ = "notification.read"
    NOTIFICATION_MANAGE = "notification.manage"

    WATCHLIST_READ = "watchlist.read"
    WATCHLIST_CREATE = "watchlist.create"
    WATCHLIST_CREATE_LOCATION = "watchlist.create_location"
    WATCHLIST_UPDATE = "watchlist.update"
    WATCHLIST_DEACTIVATE = "watchlist.deactivate"

    SECURITY_SCREENING_READ = "security_screening.read"
    SECURITY_SCREENING_REVIEW = "security_screening.review"
    SECURITY_SCREENING_RESOLVE = "security_screening.resolve"

    ANALYTICS_DASHBOARD_VIEW = "analytics.dashboard.view"
    ANALYTICS_WEEKLY_VIEW = "analytics.weekly.view"
    ANALYTICS_MONTHLY_VIEW = "analytics.monthly.view"
    ANALYTICS_TRENDS_VIEW = "analytics.trends.view"
    ANALYTICS_LOCATIONS_COMPARE = "analytics.locations.compare"

    REPORTS_VIEW = "reports.view"
    REPORTS_EXPORT = "reports.export"
    REPORTS_EXPORT_CSV = "reports.export.csv"
    REPORTS_EXPORT_XLSX = "reports.export.xlsx"

    LOCATIONS_READ = "locations.read"
    LOCATIONS_MANAGE = "locations.manage"

    ADMINS_READ = "admins.read"
    ADMINS_MANAGE = "admins.manage"

    AUDIT_READ = "audit.read"

    COMPLIANCE_READ = "compliance.read"
    COMPLIANCE_REVIEW = "compliance.review"
    COMPLIANCE_VERIFY = "compliance.verify"
    COMPLIANCE_REJECT = "compliance.reject"
    COMPLIANCE_MANAGE_REQUIREMENTS = "compliance.manage_requirements"
    COMPLIANCE_DOCUMENT_DOWNLOAD = "compliance.document.download"

    VENDOR_COMPANY_READ = "vendor_company.read"
    VENDOR_COMPANY_MANAGE = "vendor_company.manage"

    EMERGENCY_READ = "emergency.read"
    EMERGENCY_START = "emergency.start"
    EMERGENCY_ROLLCALL = "emergency.rollcall"
    EMERGENCY_CLOSE = "emergency.close"
    EMERGENCY_HISTORY_READ = "emergency.history.read"

    AI_COPILOT_USE = "ai.copilot.use"
    AI_OPERATIONAL_READ = "ai.operational.read"
    AI_MANAGEMENT_READ = "ai.management.read"
    AI_INSIGHTS_READ = "ai.insights.read"
    AI_INSIGHTS_DISMISS = "ai.insights.dismiss"

    PRIVACY_RETENTION_READ = "privacy.retention.read"
    PRIVACY_RETENTION_MANAGE = "privacy.retention.manage"
    PRIVACY_RETENTION_EXECUTE = "privacy.retention.execute"
    SECURITY_READINESS_READ = "security.readiness.read"
    SECURITY_AUDIT_INTEGRITY_READ = "security.audit_integrity.read"
    SECURITY_AUDIT_INTEGRITY_VERIFY = "security.audit_integrity.verify"

    ACCESS_READ = "access.read"
    ACCESS_OPERATE = "access.operate"
    ACCESS_RETRY = "access.retry"
    ACCESS_REVOKE = "access.revoke"
    ACCESS_CONFIG_READ = "access.config.read"
    ACCESS_CONFIG_MANAGE = "access.config.manage"

    BADGE_PRINTER_READ = "badge.printer.read"
    BADGE_PRINTER_OPERATE = "badge.printer.operate"
    BADGE_PRINTER_CONFIG_MANAGE = "badge.printer.config.manage"

    OPERATIONS_READINESS_READ = "operations.readiness.read"


class PhysicalAccessStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    REVOCATION_PENDING = "REVOCATION_PENDING"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    MANUAL_ACTION_REQUIRED = "MANUAL_ACTION_REQUIRED"


class BadgePrintJobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PRINTED = "PRINTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    MANUAL_ACTION_REQUIRED = "MANUAL_ACTION_REQUIRED"


ALL_PERMISSIONS = frozenset(Permission)

OPERATIONAL_DENIED = frozenset({
    Permission.ANALYTICS_DASHBOARD_VIEW,
    Permission.ANALYTICS_WEEKLY_VIEW,
    Permission.ANALYTICS_MONTHLY_VIEW,
    Permission.ANALYTICS_TRENDS_VIEW,
    Permission.ANALYTICS_LOCATIONS_COMPARE,
    Permission.REPORTS_VIEW,
    Permission.REPORTS_EXPORT,
    Permission.REPORTS_EXPORT_CSV,
    Permission.REPORTS_EXPORT_XLSX,
    Permission.LOCATIONS_MANAGE,
    Permission.ADMINS_READ,
    Permission.ADMINS_MANAGE,
    Permission.AUDIT_READ,
    Permission.AI_MANAGEMENT_READ,
})

SITE_ADMIN_DENIED = OPERATIONAL_DENIED | frozenset({
    Permission.PRIVACY_RETENTION_READ,
    Permission.PRIVACY_RETENTION_MANAGE,
    Permission.PRIVACY_RETENTION_EXECUTE,
    Permission.SECURITY_READINESS_READ,
    Permission.SECURITY_AUDIT_INTEGRITY_READ,
    Permission.SECURITY_AUDIT_INTEGRITY_VERIFY,
    Permission.OPERATIONS_READINESS_READ,
    Permission.ACCESS_CONFIG_MANAGE,
    Permission.BADGE_PRINTER_CONFIG_MANAGE,
})

SECURITY_DENIED = SITE_ADMIN_DENIED

ROLE_PERMISSIONS: dict[AdminRole, frozenset[Permission]] = {
    AdminRole.GLOBAL_ADMIN: ALL_PERMISSIONS,
    AdminRole.HEAD_ADMIN: frozenset({
        Permission.VISITOR_READ,
        Permission.VISITOR_VERIFY,
        Permission.VISITOR_CREATE,
        Permission.VISITOR_UPDATE,
        Permission.VISITOR_CHECKIN,
        Permission.VISITOR_CHECKOUT,
        Permission.ARRIVAL_READ,
        Permission.ARRIVAL_MANAGE,
        Permission.CHECKIN_READ,
        Permission.CHECKIN_PERFORM,
        Permission.CHECKOUT_PERFORM,
        Permission.REGISTRATION_READ,
        Permission.REGISTRATION_MANAGE,
        Permission.APPROVAL_READ,
        Permission.APPROVAL_MANAGE,
        Permission.APPROVAL_APPROVE,
        Permission.APPROVAL_REJECT,
        Permission.ONSITE_READ,
        Permission.INVITATION_READ,
        Permission.INVITATION_CREATE,
        Permission.INVITATION_CANCEL,
        Permission.VISITOR_QR_VERIFY,
        Permission.BADGE_READ,
        Permission.BADGE_ISSUE,
        Permission.BADGE_PRINT,
        Permission.ANALYTICS_DASHBOARD_VIEW,
        Permission.ANALYTICS_WEEKLY_VIEW,
        Permission.ANALYTICS_MONTHLY_VIEW,
        Permission.ANALYTICS_TRENDS_VIEW,
        Permission.ANALYTICS_LOCATIONS_COMPARE,
        Permission.REPORTS_VIEW,
        Permission.REPORTS_EXPORT,
        Permission.REPORTS_EXPORT_CSV,
        Permission.REPORTS_EXPORT_XLSX,
        Permission.LOCATIONS_READ,
        Permission.LOCATIONS_MANAGE,
        Permission.ADMINS_READ,
        Permission.AUDIT_READ,
        Permission.NOTIFICATION_READ,
        Permission.NOTIFICATION_MANAGE,
        Permission.WATCHLIST_READ,
        Permission.WATCHLIST_CREATE_LOCATION,
        Permission.WATCHLIST_UPDATE,
        Permission.WATCHLIST_DEACTIVATE,
        Permission.SECURITY_SCREENING_READ,
        Permission.SECURITY_SCREENING_REVIEW,
        Permission.SECURITY_SCREENING_RESOLVE,
        Permission.COMPLIANCE_READ,
        Permission.COMPLIANCE_REVIEW,
        Permission.COMPLIANCE_VERIFY,
        Permission.COMPLIANCE_REJECT,
        Permission.COMPLIANCE_MANAGE_REQUIREMENTS,
        Permission.COMPLIANCE_DOCUMENT_DOWNLOAD,
        Permission.VENDOR_COMPANY_READ,
        Permission.VENDOR_COMPANY_MANAGE,
        Permission.EMERGENCY_READ,
        Permission.EMERGENCY_START,
        Permission.EMERGENCY_ROLLCALL,
        Permission.EMERGENCY_CLOSE,
        Permission.EMERGENCY_HISTORY_READ,
        Permission.AI_COPILOT_USE,
        Permission.AI_OPERATIONAL_READ,
        Permission.AI_MANAGEMENT_READ,
        Permission.AI_INSIGHTS_READ,
        Permission.AI_INSIGHTS_DISMISS,
        Permission.PRIVACY_RETENTION_READ,
        Permission.SECURITY_READINESS_READ,
        Permission.SECURITY_AUDIT_INTEGRITY_READ,
        Permission.SECURITY_AUDIT_INTEGRITY_VERIFY,
        Permission.OPERATIONS_READINESS_READ,
        Permission.ACCESS_READ,
        Permission.ACCESS_OPERATE,
        Permission.ACCESS_RETRY,
        Permission.ACCESS_REVOKE,
        Permission.ACCESS_CONFIG_READ,
        Permission.ACCESS_CONFIG_MANAGE,
        Permission.BADGE_PRINTER_READ,
        Permission.BADGE_PRINTER_OPERATE,
        Permission.BADGE_PRINTER_CONFIG_MANAGE,
    }),
    AdminRole.SITE_ADMIN: frozenset({
        Permission.VISITOR_READ,
        Permission.VISITOR_VERIFY,
        Permission.VISITOR_CREATE,
        Permission.VISITOR_UPDATE,
        Permission.VISITOR_CHECKIN,
        Permission.VISITOR_CHECKOUT,
        Permission.ARRIVAL_READ,
        Permission.ARRIVAL_MANAGE,
        Permission.CHECKIN_READ,
        Permission.CHECKIN_PERFORM,
        Permission.CHECKOUT_PERFORM,
        Permission.REGISTRATION_READ,
        Permission.REGISTRATION_MANAGE,
        Permission.APPROVAL_READ,
        Permission.APPROVAL_MANAGE,
        Permission.APPROVAL_APPROVE,
        Permission.APPROVAL_REJECT,
        Permission.ONSITE_READ,
        Permission.INVITATION_READ,
        Permission.INVITATION_CREATE,
        Permission.INVITATION_CANCEL,
        Permission.VISITOR_QR_VERIFY,
        Permission.BADGE_READ,
        Permission.BADGE_ISSUE,
        Permission.BADGE_PRINT,
        Permission.LOCATIONS_READ,
        Permission.WATCHLIST_READ,
        Permission.SECURITY_SCREENING_READ,
        Permission.SECURITY_SCREENING_REVIEW,
        Permission.SECURITY_SCREENING_RESOLVE,
        Permission.COMPLIANCE_READ,
        Permission.COMPLIANCE_REVIEW,
        Permission.COMPLIANCE_VERIFY,
        Permission.COMPLIANCE_REJECT,
        Permission.COMPLIANCE_DOCUMENT_DOWNLOAD,
        Permission.VENDOR_COMPANY_READ,
        Permission.VENDOR_COMPANY_MANAGE,
        Permission.EMERGENCY_READ,
        Permission.EMERGENCY_START,
        Permission.EMERGENCY_ROLLCALL,
        Permission.EMERGENCY_CLOSE,
        Permission.EMERGENCY_HISTORY_READ,
        Permission.AI_COPILOT_USE,
        Permission.AI_OPERATIONAL_READ,
        Permission.AI_INSIGHTS_READ,
        Permission.AI_INSIGHTS_DISMISS,
        Permission.ACCESS_READ,
        Permission.ACCESS_OPERATE,
        Permission.ACCESS_RETRY,
        Permission.ACCESS_REVOKE,
        Permission.ACCESS_CONFIG_READ,
        Permission.BADGE_PRINTER_READ,
        Permission.BADGE_PRINTER_OPERATE,
    }),
    AdminRole.SECURITY: frozenset({
        Permission.VISITOR_READ,
        Permission.VISITOR_VERIFY,
        Permission.VISITOR_CHECKIN,
        Permission.VISITOR_CHECKOUT,
        Permission.ARRIVAL_READ,
        Permission.ARRIVAL_MANAGE,
        Permission.CHECKIN_READ,
        Permission.CHECKIN_PERFORM,
        Permission.CHECKOUT_PERFORM,
        Permission.REGISTRATION_READ,
        Permission.INVITATION_READ,
        Permission.VISITOR_QR_VERIFY,
        Permission.BADGE_READ,
        Permission.BADGE_ISSUE,
        Permission.BADGE_PRINT,
        Permission.APPROVAL_READ,
        Permission.APPROVAL_APPROVE,
        Permission.APPROVAL_REJECT,
        Permission.ONSITE_READ,
        Permission.WATCHLIST_READ,
        Permission.SECURITY_SCREENING_READ,
        Permission.SECURITY_SCREENING_REVIEW,
        Permission.SECURITY_SCREENING_RESOLVE,
        Permission.COMPLIANCE_READ,
        Permission.COMPLIANCE_REVIEW,
        Permission.EMERGENCY_READ,
        Permission.EMERGENCY_START,
        Permission.EMERGENCY_ROLLCALL,
        Permission.EMERGENCY_CLOSE,
        Permission.EMERGENCY_HISTORY_READ,
        Permission.AI_COPILOT_USE,
        Permission.AI_OPERATIONAL_READ,
        Permission.AI_INSIGHTS_READ,
        Permission.ACCESS_READ,
        Permission.ACCESS_OPERATE,
        Permission.ACCESS_RETRY,
        Permission.ACCESS_REVOKE,
        Permission.BADGE_PRINTER_READ,
        Permission.BADGE_PRINTER_OPERATE,
    }),
}


def get_permissions_for_role(role: AdminRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has_permission(role: AdminRole, permission: Permission) -> bool:
    return permission in get_permissions_for_role(role)
