export const Permission = {
  VISITOR_READ: 'visitor.read',
  VISITOR_CREATE: 'visitor.create',
  VISITOR_UPDATE: 'visitor.update',
  VISITOR_CHECKIN: 'visitor.checkin',
  VISITOR_CHECKOUT: 'visitor.checkout',
  REGISTRATION_READ: 'registration.read',
  REGISTRATION_MANAGE: 'registration.manage',
  APPROVAL_READ: 'approval.read',
  APPROVAL_MANAGE: 'approval.manage',
  INVITATION_READ: 'invitation.read',
  INVITATION_CREATE: 'invitation.create',
  INVITATION_CANCEL: 'invitation.cancel',
  VISITOR_QR_VERIFY: 'visitor_qr.verify',
  BADGE_READ: 'badge.read',
  BADGE_ISSUE: 'badge.issue',
  BADGE_PRINT: 'badge.print',
  ONSITE_READ: 'onsite.read',
  ANALYTICS_DASHBOARD_VIEW: 'analytics.dashboard.view',
  ANALYTICS_WEEKLY_VIEW: 'analytics.weekly.view',
  ANALYTICS_MONTHLY_VIEW: 'analytics.monthly.view',
  REPORTS_VIEW: 'reports.view',
  REPORTS_EXPORT: 'reports.export',
  LOCATIONS_READ: 'locations.read',
  LOCATIONS_MANAGE: 'locations.manage',
  ADMINS_READ: 'admins.read',
  ADMINS_MANAGE: 'admins.manage',
  AUDIT_READ: 'audit.read',
  WATCHLIST_READ: 'watchlist.read',
  WATCHLIST_CREATE: 'watchlist.create',
  WATCHLIST_CREATE_LOCATION: 'watchlist.create_location',
  WATCHLIST_UPDATE: 'watchlist.update',
  WATCHLIST_DEACTIVATE: 'watchlist.deactivate',
  SECURITY_SCREENING_READ: 'security_screening.read',
  SECURITY_SCREENING_REVIEW: 'security_screening.review',
  SECURITY_SCREENING_RESOLVE: 'security_screening.resolve',
  COMPLIANCE_READ: 'compliance.read',
  COMPLIANCE_VERIFY: 'compliance.verify',
  VENDOR_COMPANY_READ: 'vendor_company.read',
  VENDOR_COMPANY_MANAGE: 'vendor_company.manage',
  EMERGENCY_READ: 'emergency.read',
  EMERGENCY_START: 'emergency.start',
  EMERGENCY_ROLLCALL: 'emergency.rollcall',
  EMERGENCY_CLOSE: 'emergency.close',
  AI_INSIGHTS_DISMISS: 'ai.insights.dismiss',
  AI_COPILOT_USE: 'ai.copilot.use',
  AI_OPERATIONAL_READ: 'ai.operational.read',
  AI_MANAGEMENT_READ: 'ai.management.read',
  AI_INSIGHTS_READ: 'ai.insights.read',
  PRIVACY_RETENTION_READ: 'privacy.retention.read',
  PRIVACY_RETENTION_MANAGE: 'privacy.retention.manage',
  PRIVACY_RETENTION_EXECUTE: 'privacy.retention.execute',
  SECURITY_READINESS_READ: 'security.readiness.read',
  SECURITY_AUDIT_INTEGRITY_READ: 'security.audit_integrity.read',
  ACCESS_READ: 'access.read',
  ACCESS_OPERATE: 'access.operate',
  ACCESS_RETRY: 'access.retry',
  ACCESS_REVOKE: 'access.revoke',
  ACCESS_CONFIG_READ: 'access.config.read',
  ACCESS_CONFIG_MANAGE: 'access.config.manage',
  BADGE_PRINTER_READ: 'badge.printer.read',
  BADGE_PRINTER_OPERATE: 'badge.printer.operate',
  BADGE_PRINTER_CONFIG_MANAGE: 'badge.printer.config.manage',
  OPERATIONS_READINESS_READ: 'operations.readiness.read',
} as const;

export type PermissionKey = typeof Permission[keyof typeof Permission];

export type AdminRole = 'GLOBAL_ADMIN' | 'HEAD_ADMIN' | 'SITE_ADMIN' | 'SECURITY';

export interface AssignedLocation {
  id: number;
  name: string;
  code: string;
  city?: string | null;
}

export interface UserProfile {
  id: number;
  email: string;
  display_name: string | null;
  role: AdminRole;
  is_owner: boolean;
  is_active: boolean;
  permissions: string[];
  location_ids: number[];
  assigned_locations: AssignedLocation[];
  auth_provider?: string | null;
  force_password_change?: boolean;
  entra_linked?: boolean;
  last_login_at?: string | null;
  identity_linked_at?: string | null;
}

export interface Location {
  id: number;
  name: string;
  code: string;
  city?: string | null;
  timezone?: string | null;
  is_active: boolean;
  is_development_seed: boolean;
  registration_enabled?: boolean;
  public_registration_token?: string | null;
  registration_url?: string | null;
  site_staff_count?: number;
  site_admin_count?: number;
  security_count?: number;
}

export interface LocationStaffMember {
  user_id: number;
  email: string;
  display_name?: string | null;
  role: 'SITE_ADMIN' | 'SECURITY';
  is_active: boolean;
  assigned_at?: string | null;
}

export interface LocationRetireSummary {
  location_id: number;
  name: string;
  code: string;
  is_active: boolean;
  assigned_staff: number;
  onsite_visitors: number;
  pending_approvals: number;
  future_visits: number;
  active_emergency: boolean;
  can_retire: boolean;
  blockers: string[];
}

export interface LocationRetireResponse {
  location_id: number;
  status: string;
  code: string;
}

export interface PublicSite {
  name: string;
  registration_enabled: boolean;
}

export interface PublicHost {
  id: number;
  name: string;
  department?: string | null;
  email?: string | null;
}

export interface PublicVisitorType {
  code: string;
  name: string;
  requires_vendor_compliance?: boolean;
  po_reference_required?: boolean;
}

export interface PublicRegistrationPayload {
  site_token: string;
  visitor_type: string;
  full_name: string;
  mobile: string;
  email: string;
  company: string;
  host_id: number;
  purpose: string;
  expected_duration_minutes: number;
  policy_accepted: boolean;
}

export interface PublicRegistrationResult {
  registration_reference: string;
  status: string;
  visitor_name: string;
  site_name: string;
  duplicate?: boolean;
}

export interface SelfRegistration {
  id: number;
  registration_reference: string | null;
  status: string;
  visitor_name: string;
  visitor_mobile: string | null;
  visitor_email: string | null;
  company: string | null;
  visitor_type: string | null;
  host_name: string | null;
  site_name: string;
  site_id: number;
  purpose: string | null;
  expected_duration_minutes: number | null;
  policy_accepted: boolean;
  submitted_at: string;
  policy_version?: string | null;
  policy_accepted_at?: string | null;
}

export interface SelfRegistrationList {
  items: SelfRegistration[];
  total: number;
  limit: number;
  offset: number;
}

export interface SelfRegistrationQrStats {
  today: number;
  pending: number;
  approved: number;
  rejected: number;
}

export interface SelfRegistrationQrConfig {
  company_label: string;
  app_name: string;
  locations: Location[];
  location: Location;
  registration_url: string;
  is_permanent: boolean;
  localhost_warning: boolean;
  stats: SelfRegistrationQrStats;
}

export interface ApprovalHistoryItem {
  id: number;
  decision: string;
  actor_email: string | null;
  actor_role: string | null;
  comment: string | null;
  reason_code: string | null;
  previous_status: string;
  new_status: string;
  created_at: string | null;
}

export interface ApprovalItem {
  id: number;
  registration_reference: string | null;
  status: string;
  visitor_name: string;
  visitor_mobile: string | null;
  visitor_email: string | null;
  company: string | null;
  visitor_type: string | null;
  host_name: string | null;
  site_name: string;
  site_id: number;
  purpose: string | null;
  expected_duration_minutes: number | null;
  policy_accepted: boolean;
  policy_version?: string | null;
  submitted_at: string | null;
  approval_history: ApprovalHistoryItem[];
  compliance_status?: string | null;
  compliance_reason_summary?: string | null;
  compliance_signals?: string[];
}

export interface ApprovalList {
  items: ApprovalItem[];
  total: number;
  limit: number;
  offset: number;
  pending_count: number;
}

export interface OperationalVisit {
  id: number;
  registration_reference: string | null;
  status: string;
  visitor_name: string;
  visitor_mobile: string | null;
  visitor_email: string | null;
  company: string | null;
  visitor_type: string | null;
  host_name: string | null;
  site_name: string;
  site_id: number;
  site_city?: string | null;
  purpose: string | null;
  expected_duration_minutes: number | null;
  policy_accepted: boolean;
  policy_version?: string | null;
  submitted_at: string | null;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  arrived_at?: string | null;
  checked_in_at?: string | null;
  checked_out_at?: string | null;
  check_in_method?: string | null;
  overstay?: boolean;
  is_walk_in?: boolean;
  approval_history: ApprovalHistoryItem[];
}

export interface OperationalVisitList {
  items: OperationalVisit[];
  total: number;
  limit: number;
  offset: number;
  onsite_count?: number;
}

export interface RejectionReasonOption {
  code: string;
  label: string;
}

export interface InvitationItem {
  id: number;
  registration_reference: string | null;
  status: string;
  source?: string | null;
  visitor_name: string;
  visitor_mobile: string | null;
  visitor_email: string | null;
  company: string | null;
  visitor_type: string | null;
  host_name: string | null;
  site_name: string;
  site_id: number;
  site_city?: string | null;
  purpose: string | null;
  notes?: string | null;
  expected_duration_minutes: number | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  submitted_at: string | null;
  invitation_status: string;
  invitation_valid_from?: string | null;
  invitation_valid_until?: string | null;
  has_active_invitation: boolean;
  created_by_email?: string | null;
  cancelled_at?: string | null;
  cancellation_reason?: string | null;
  approval_history: ApprovalHistoryItem[];
  invitation_url?: string | null;
}

export interface InvitationList {
  items: InvitationItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PublicInvitation {
  visitor_name: string;
  company: string | null;
  site_name: string;
  site_city?: string | null;
  host_name: string | null;
  purpose: string | null;
  scheduled_start: string | null;
  status: string;
  invitation_token: string;
}

export interface QrVerifyResult {
  valid: boolean;
  code: string;
  message?: string | null;
  visit_id: number;
  registration_reference: string | null;
  status: string;
  source?: string | null;
  visitor_name: string;
  company: string | null;
  visitor_type: string | null;
  visitor_mobile: string | null;
  host_name: string | null;
  site_name: string;
  site_id: number;
  purpose: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  arrived_at?: string | null;
  checked_in_at?: string | null;
  invitation_status?: string | null;
  can_mark_arrived: boolean;
  can_check_in: boolean;
  can_check_out: boolean;
  security_status?: string | null;
}

export interface WatchlistItem {
  id: number;
  scope_type: string;
  location_id: number | null;
  location_name: string | null;
  full_name: string;
  mobile: string | null;
  email: string | null;
  company: string | null;
  reason_code: string;
  reason_text: string | null;
  action_level: string;
  status: string;
  valid_from: string | null;
  valid_until: string | null;
  created_at: string | null;
  deactivated_at: string | null;
}

export interface WatchlistList {
  items: WatchlistItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SecurityReviewItem {
  visit_id: number;
  registration_reference: string | null;
  status: string;
  source: string | null;
  security_status: string;
  visitor_name: string;
  visitor_mobile: string | null;
  visitor_email: string | null;
  company: string | null;
  visitor_type: string | null;
  host_name: string | null;
  site_name: string;
  site_id: number;
  purpose: string | null;
  screening_outcome: string | null;
  match_confidence: string | null;
  reason_summary: string | null;
  signals: string[];
  screening_id: number | null;
  resolved: boolean;
  resolution: string | null;
  screened_at: string | null;
}

export interface SecurityReviewList {
  items: SecurityReviewItem[];
  total: number;
  review_count: number;
  blocked_count: number;
  limit: number;
  offset: number;
}

export interface VendorCompanyLocationItem {
  id: number;
  name: string;
  code: string;
}

export interface VendorCompanyItem {
  id: number;
  name: string;
  code?: string | null;
  primary_contact_name?: string | null;
  primary_contact_email?: string | null;
  primary_contact_mobile?: string | null;
  is_active: boolean;
  locations?: VendorCompanyLocationItem[];
  created_at?: string | null;
}

export interface VendorCompanyList {
  items: VendorCompanyItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ComplianceReviewItem {
  visit_id: number;
  registration_reference?: string | null;
  visitor_name: string;
  vendor_company_name?: string | null;
  site_name?: string | null;
  site_id?: number | null;
  compliance_status?: string | null;
  issue?: string | null;
  status?: string | null;
  scheduled_start?: string | null;
}

export interface ComplianceReviewList {
  items: ComplianceReviewItem[];
  total: number;
  attention_count: number;
  expiring_count: number;
  limit: number;
  offset: number;
}

export interface ComplianceSummary {
  compliance_status: string;
  reason_summary?: string | null;
  signals?: string[];
  evaluated_at?: string | null;
}

export interface ComplianceDocumentItem {
  id: number;
  requirement_id: number;
  requirement_code: string;
  requirement_name: string;
  visitor_id?: number | null;
  vendor_company_id?: number | null;
  file_name: string;
  mime_type?: string | null;
  file_size_bytes?: number | null;
  status: string;
  valid_from?: string | null;
  valid_until?: string | null;
  uploaded_at?: string | null;
  verified_at?: string | null;
  verified_by_user_id?: number | null;
  verified_by_name?: string | null;
  rejection_comment?: string | null;
  scan_status?: string | null;
  supersedes_id?: number | null;
  is_current?: boolean;
}

export interface ComplianceRequirementStatusItem {
  requirement_id: number;
  requirement_code: string;
  requirement_name: string;
  document_owner_type: string;
  is_mandatory: boolean;
  validity_required: boolean;
  usability: string;
  current_document_id?: number | null;
  documents: ComplianceDocumentItem[];
}

export interface ComplianceVisitDetail {
  visit_id: number;
  registration_reference?: string | null;
  status: string;
  visitor_id?: number | null;
  visitor_name: string;
  visitor_mobile?: string | null;
  visitor_email?: string | null;
  visitor_type?: string | null;
  vendor_company_id?: number | null;
  vendor_company_name?: string | null;
  site_id?: number | null;
  site_name?: string | null;
  host_name?: string | null;
  work_purpose?: string | null;
  po_work_order_reference?: string | null;
  safety_acknowledged: boolean;
  safety_acknowledged_at?: string | null;
  scheduled_start?: string | null;
  evaluation_date?: string | null;
  compliance: ComplianceSummary;
  requirements: ComplianceRequirementStatusItem[];
}

export interface ComplianceRequirementItem {
  id: number;
  name: string;
  code: string;
  description?: string | null;
  visitor_type_id?: number | null;
  visitor_type_name?: string | null;
  scope_type: string;
  location_id?: number | null;
  location_name?: string | null;
  location_code?: string | null;
  document_owner_type: string;
  document_required: boolean;
  validity_required: boolean;
  safety_acknowledgement_required: boolean;
  is_mandatory: boolean;
  is_active: boolean;
  expiry_warning_days: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface VendorCompanyDocumentGroup {
  requirement_id: number;
  requirement_name: string;
  requirement_code: string;
  current_document_id?: number | null;
  current_status?: string | null;
  valid_until?: string | null;
  documents: ComplianceDocumentItem[];
}

export interface VendorCompanyDetail extends VendorCompanyItem {
  duplicate_warnings?: Array<{ id: number; name: string }>;
  contractors?: Array<{
    visitor_id: number;
    full_name: string;
    email?: string | null;
    phone?: string | null;
    trade_or_role?: string | null;
  }>;
  compliance_documents?: VendorCompanyDocumentGroup[];
}

export interface ContractorVisitList {
  items: ComplianceReviewItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface BadgeItem {
  id: number;
  visit_id: number;
  badge_number: string;
  status: string;
  issued_at: string | null;
  printed_at: string | null;
  print_count: number;
  expires_at: string | null;
  visitor_name: string;
  company: string | null;
  visitor_type: string | null;
  host_name: string | null;
  site_name: string;
  site_code: string | null;
  site_city?: string | null;
  registration_reference: string | null;
  scheduled_start: string | null;
  visit_date: string | null;
}

export interface HostApprovalPublic {
  state: string;
  message?: string | null;
  visit_status?: string | null;
  visitor_name: string;
  company?: string | null;
  visitor_type?: string | null;
  site_name: string;
  purpose?: string | null;
  is_walk_in: boolean;
  scheduled_display?: string | null;
  expected_duration_minutes?: number | null;
  can_approve: boolean;
  can_reject: boolean;
}

export interface HostApprovalAction {
  state: string;
  message?: string | null;
  visitor_name?: string | null;
}

export interface HostRejectionReason {
  code: string;
  label: string;
}

export interface NotificationItem {
  id: number;
  notification_type: string;
  channel: string;
  recipient: string;
  visit_id?: number | null;
  status: string;
  subject?: string | null;
  body_preview?: string | null;
  dev_action_url?: string | null;
  created_at?: string | null;
}

export interface NotificationList {
  items: NotificationItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface VisitorPolicy {
  version: string;
  title: string;
  content: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
    request_id?: string | null;
  };
}

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: string;
  requiredPermission?: PermissionKey;
}

export const DURATION_OPTIONS = [
  { label: '30 minutes', minutes: 30 },
  { label: '1 hour', minutes: 60 },
  { label: '2 hours', minutes: 120 },
  { label: '4 hours', minutes: 240 },
  { label: 'Full day', minutes: 480 },
] as const;

export function formatDuration(minutes: number | null | undefined): string {
  if (!minutes) return '—';
  const opt = DURATION_OPTIONS.find((d) => d.minutes === minutes);
  return opt?.label ?? `${minutes} min`;
}

export function formatStatus(status: string): string {
  return status.replace(/_/g, ' ');
}

export interface EmergencyCounts {
  total: number;
  unaccounted: number;
  safe: number;
  not_located: number;
  left_premises: number;
  pending: number;
}

export interface EmergencyEventItem {
  id: number;
  location_id: number;
  location_name?: string | null;
  location_code?: string | null;
  status: string;
  started_at?: string | null;
  started_by_user_id: number;
  started_by_name?: string | null;
  started_by_email?: string | null;
  reason: string;
  notes?: string | null;
  visitor_snapshot_count: number;
  closed_at?: string | null;
  closed_by_user_id?: number | null;
  closed_by_name?: string | null;
  closure_comment?: string | null;
  counts: EmergencyCounts;
}

export interface EmergencyOverviewItem {
  location_id: number;
  location_name: string;
  location_code: string;
  has_active_emergency: boolean;
  active_emergency_id?: number | null;
  current_onsite_count: number;
}

export interface EmergencyRollCallActionItem {
  id: number;
  old_status: string;
  new_status: string;
  actor_email?: string | null;
  comment?: string | null;
  created_at?: string | null;
}

export interface EmergencyRollCallEntryItem {
  id: number;
  emergency_event_id: number;
  visit_id: number;
  visitor_id: number;
  visitor_name: string;
  company?: string | null;
  visitor_type?: string | null;
  host_name?: string | null;
  mobile?: string | null;
  registration_reference?: string | null;
  badge_number?: string | null;
  checked_in_at?: string | null;
  status: string;
  status_label: string;
  status_updated_at?: string | null;
  status_updated_by_name?: string | null;
  comment?: string | null;
  version: number;
  visit_checked_out_after_start: boolean;
  current_visit_status?: string | null;
  expected_duration_minutes?: number | null;
  action_history?: EmergencyRollCallActionItem[];
}

export interface EmergencyHistoryList {
  items: EmergencyEventItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardKpis {
  expected_today: number;
  awaiting_approval: number;
  checked_in_today: number;
  onsite_now: number;
  checked_out_today: number;
  overstayed: number;
  vendor_contractor_onsite: number;
}

export interface DashboardTrendPoint {
  date: string;
  label?: string;
  granularity?: 'hour' | 'day';
  expected: number;
  checked_in: number;
  checked_out: number;
}

export interface DashboardLocationRow {
  location_id: number;
  location_name: string;
  visitors: number;
  check_ins: number;
  onsite: number;
  rejected: number;
}

export interface DashboardData {
  range: {
    period: string;
    from: string;
    to: string;
    location_id?: number | null;
    location_label?: string;
  };
  kpis: DashboardKpis;
  visitor_trend: DashboardTrendPoint[];
  visitor_types: Array<{ name: string; count: number }>;
  locations: DashboardLocationRow[];
  peak_arrivals: Array<{ hour: number; label: string; count: number }>;
  approval_metrics: { average_minutes: number; median_minutes: number; sample_size: number };
  visit_duration: { average_minutes: number; sample_size: number };
  security_summary: { review: number; blocked: number };
  compliance_summary: { review_required: number; non_compliant: number; expiring: number };
  active_emergencies: Array<{ id: number; location_id: number; location_name?: string | null }>;
}

export interface ReportVisitRow {
  registration_reference?: string | null;
  visitor_name?: string;
  visitor_mobile?: string | null;
  visitor_email?: string | null;
  company?: string | null;
  visitor_type?: string | null;
  host_name?: string | null;
  location_name?: string | null;
  source?: string | null;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  created_at?: string | null;
  approval_status?: string | null;
  approval_time?: string | null;
  security_status?: string | null;
  compliance_status?: string | null;
  checked_in_at?: string | null;
  checked_out_at?: string | null;
  visit_duration_minutes?: number | null;
  status?: string | null;
}

export interface ReportVisitList {
  items: ReportVisitRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface CopilotResponsePayload {
  answer: string;
  summary: string;
  insights?: Array<{ type: string; title: string; explanation: string; priority?: string; evidence?: string[] }>;
  recommended_actions?: Array<{ label: string; path: string; action_type?: string }>;
  source_references?: Array<{ label: string; path?: string; reference?: string }>;
  limitations?: string[];
  denied?: boolean;
  unavailable?: boolean;
}

export interface CopilotResponse {
  intent: string;
  response: CopilotResponsePayload;
  provider: string;
  context_scope?: string[];
}

export interface AIInsightItem {
  id: number;
  insight_type: string;
  location_id?: number | null;
  location_name?: string | null;
  visit_id?: number | null;
  visitor_id?: number | null;
  status: string;
  priority: string;
  title: string;
  summary: string;
  evidence?: { bullets?: string[]; confidence?: string; suggested_action?: string };
  generated_at?: string | null;
  deep_link?: string | null;
}
