import type {
  ApiErrorBody,
  Location,
  LocationRetireResponse,
  LocationRetireSummary,
  LocationStaffMember,
  PublicHost,
  PublicRegistrationPayload,
  PublicRegistrationResult,
  PublicSite,
  PublicVisitorType,
  SelfRegistration,
  SelfRegistrationList,
  SelfRegistrationQrConfig,
  ApprovalList,
  ApprovalItem,
  BadgeItem,
  HostApprovalAction,
  HostApprovalPublic,
  HostRejectionReason,
  InvitationItem,
  InvitationList,
  NotificationList,
  PublicInvitation,
  QrVerifyResult,
  SecurityReviewItem,
  SecurityReviewList,
  UserProfile,
  VisitorPolicy,
  WatchlistItem,
  WatchlistList,
  VendorCompanyItem,
  VendorCompanyList,
  ComplianceReviewList,
  ContractorVisitList,
  ComplianceVisitDetail,
  ComplianceDocumentItem,
  ComplianceRequirementItem,
  VendorCompanyDetail,
  EmergencyEventItem,
  EmergencyOverviewItem,
  EmergencyRollCallEntryItem,
  EmergencyHistoryList,
  DashboardData,
  ReportVisitList,
  OperationalVisit,
  OperationalVisitList,
  CopilotResponse,
  AIInsightItem,
} from '../types';
import { triggerOperationalRefresh } from '../utils/operationalRefreshEvents';
import { handleApiUnauthorized, shouldHandleApiUnauthorized } from '../auth/authRedirect';
import { getVmsNativeAccessToken } from '../auth/vmsNativeAuth';

let accessTokenProvider: (() => Promise<string | null>) | null = null;

export function setAccessTokenProvider(provider: () => Promise<string | null>) {
  accessTokenProvider = provider;
}

const AUTH_MODE = (import.meta.env.VITE_AUTH_MODE as string | undefined) ?? 'dev';

async function buildAuthHeaders(extra?: Record<string, string>): Promise<Record<string, string>> {
  const headers: Record<string, string> = { ...extra };
  if (AUTH_MODE === 'entra' || AUTH_MODE === 'vms_native') {
    const nativeToken = getVmsNativeAccessToken();
    if (nativeToken) {
      headers.Authorization = `Bearer ${nativeToken}`;
    } else if (accessTokenProvider) {
      const token = await accessTokenProvider();
      if (token) headers.Authorization = `Bearer ${token}`;
    }
  } else if (AUTH_MODE === 'dev') {
    const devUser = typeof localStorage !== 'undefined' ? localStorage.getItem('vms_dev_user') : null;
    if (devUser) headers['X-Dev-User-Email'] = devUser;
  }
  return headers;
}

class ApiClientError extends Error {
  status: number;
  code: string;
  requestId?: string;

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.name = 'ApiClientError';
  }
}

async function parseError(response: Response): Promise<{ code: string; message: string; requestId?: string }> {
  try {
    const body = await response.json() as ApiErrorBody & { detail?: unknown };
    if (body.error) {
      return {
        code: body.error.code,
        message: body.error.message,
        requestId: body.error.request_id ?? undefined,
      };
    }
    if (Array.isArray(body.detail)) {
      return { code: 'validation_error', message: 'Please check your input and try again.' };
    }
    if (typeof body.detail === 'string') {
      return { code: 'error', message: body.detail };
    }
  } catch {
    // ignore
  }
  return { code: 'unknown_error', message: `Request failed with status ${response.status}` };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const authHeaders = await buildAuthHeaders();
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const { code, message, requestId } = await parseError(response);
    if (response.status === 401 && shouldHandleApiUnauthorized(path)) {
      handleApiUnauthorized();
    }
    throw new ApiClientError(response.status, code, message, requestId);
  }

  return response.json() as Promise<T>;
}

async function uploadForm<T>(path: string, formData: FormData): Promise<T> {
  const authHeaders = await buildAuthHeaders();
  const response = await fetch(path, {
    method: 'POST',
    headers: authHeaders,
    body: formData,
  });
  if (!response.ok) {
    const { code, message, requestId } = await parseError(response);
    if (response.status === 401 && shouldHandleApiUnauthorized(path)) {
      handleApiUnauthorized();
    }
    throw new ApiClientError(response.status, code, message, requestId);
  }
  return response.json() as Promise<T>;
}

async function downloadBlob(path: string): Promise<Blob> {
  const authHeaders = await buildAuthHeaders();
  const response = await fetch(path, {
    headers: authHeaders,
  });
  if (!response.ok) {
    const { code, message, requestId } = await parseError(response);
    if (response.status === 401 && shouldHandleApiUnauthorized(path)) {
      handleApiUnauthorized();
    }
    throw new ApiClientError(response.status, code, message, requestId);
  }
  return response.blob();
}

export const api = {
  health: () => request<{ status: string; service: string }>('/api/health'),
  me: () => request<UserProfile>('/api/me'),
  locations: () => request<Location[]>('/api/locations'),
  createLocation: (payload: {
    name: string;
    code: string;
    timezone: string;
    registration_enabled: boolean;
  }) =>
    request<Location>('/api/locations', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  locationStaff: (locationId: number) =>
    request<LocationStaffMember[]>(`/api/locations/${locationId}/staff`),
  addLocationStaff: (
    locationId: number,
    payload: { email: string; display_name: string; role: 'SITE_ADMIN' | 'SECURITY' },
  ) =>
    request<LocationStaffMember>(`/api/locations/${locationId}/staff`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  removeLocationStaff: (locationId: number, userId: number) =>
    request<void>(`/api/locations/${locationId}/staff/${userId}`, { method: 'DELETE' }),
  locationRetireSummary: (locationId: number) =>
    request<LocationRetireSummary>(`/api/locations/${locationId}/retire-summary`),
  retireLocation: (locationId: number, reason?: string) => {
    const q = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    return request<LocationRetireResponse>(`/api/locations/${locationId}${q}`, { method: 'DELETE' });
  },

  publicSite: (token: string) => request<PublicSite>(`/api/public/sites/${encodeURIComponent(token)}`),
  publicHosts: (token: string, search: string) =>
    request<PublicHost[]>(
      `/api/public/sites/${encodeURIComponent(token)}/hosts?search=${encodeURIComponent(search)}`,
    ),
  publicVisitorTypes: (token: string) =>
    request<PublicVisitorType[]>(`/api/public/sites/${encodeURIComponent(token)}/visitor-types`),
  publicPolicy: () => request<VisitorPolicy>('/api/public/policy'),
  submitRegistration: (payload: PublicRegistrationPayload) =>
    request<PublicRegistrationResult>('/api/public/registrations', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  selfRegistrations: (params: {
    status?: string;
    search?: string;
    site?: number;
    visitor_type?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.status) q.set('status', params.status);
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.visitor_type) q.set('visitor_type', params.visitor_type);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<SelfRegistrationList>(`/api/self-registrations${qs ? `?${qs}` : ''}`);
  },
  selfRegistrationQrConfig: (site?: number) => {
    const q = site ? `?site=${site}` : '';
    return request<SelfRegistrationQrConfig>(`/api/self-registrations/qr-config${q}`);
  },
  selfRegistrationDetail: (id: number) =>
    request<SelfRegistration>(`/api/self-registrations/${id}`),

  approvals: (params: {
    status?: string;
    search?: string;
    site?: number;
    visitor_type?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.status) q.set('status', params.status);
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.visitor_type) q.set('visitor_type', params.visitor_type);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<ApprovalList>(`/api/approvals${qs ? `?${qs}` : ''}`);
  },
  approvalDetail: (id: number) => request<ApprovalItem>(`/api/approvals/${id}`),
  approveVisit: (id: number, comment?: string) =>
    request<ApprovalItem>(`/api/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }),
  rejectVisit: (id: number, reason_code: string, comment?: string) =>
    request<ApprovalItem>(`/api/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason_code, comment }),
    }),
  rejectionReasons: () => request<RejectionReasonOption[]>('/api/approvals/rejection-reasons'),

  expectedToday: (params: {
    status?: string;
    search?: string;
    site?: number;
    visitor_type?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.status) q.set('status', params.status);
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.visitor_type) q.set('visitor_type', params.visitor_type);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<OperationalVisitList>(`/api/expected-today${qs ? `?${qs}` : ''}`);
  },
  onsiteVisitors: (params: {
    search?: string;
    site?: number;
    visitor_type?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.visitor_type) q.set('visitor_type', params.visitor_type);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<OperationalVisitList>(`/api/onsite${qs ? `?${qs}` : ''}`);
  },
  visitorVisits: (params: {
    status?: string;
    search?: string;
    site?: number;
    visitor_type?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.status) q.set('status', params.status);
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.visitor_type) q.set('visitor_type', params.visitor_type);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<OperationalVisitList>(`/api/visitors${qs ? `?${qs}` : ''}`);
  },
  visitDetail: (id: number) => request<OperationalVisit>(`/api/visits/${id}`),
  arriveVisit: (id: number) =>
    request<OperationalVisit>(`/api/visits/${id}/arrive`, { method: 'POST', body: '{}' }),
  checkInVisit: async (id: number) => {
    const result = await request<OperationalVisit>(`/api/visits/${id}/check-in`, { method: 'POST', body: '{}' });
    triggerOperationalRefresh();
    return result;
  },
  checkOutVisit: async (id: number) => {
    const result = await request<OperationalVisit>(`/api/visits/${id}/check-out`, { method: 'POST', body: '{}' });
    triggerOperationalRefresh();
    return result;
  },

  locationHosts: (locationId: number, search?: string) => {
    const q = search ? `?search=${encodeURIComponent(search)}` : '';
    return request<PublicHost[]>(`/api/locations/${locationId}/hosts${q}`);
  },
  visitorTypes: () => request<PublicVisitorType[]>('/api/visitor-types'),

  invitations: (params: { tab?: string; search?: string; site?: number; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.tab) q.set('tab', params.tab);
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<InvitationList>(`/api/invitations${qs ? `?${qs}` : ''}`);
  },
  createInvitation: (payload: Record<string, unknown>) =>
    request<InvitationItem>('/api/invitations', { method: 'POST', body: JSON.stringify(payload) }),
  stageVisitorPhoto: async (
    file: File,
    opts: { fullName?: string; source?: string; locationId?: number },
  ) => {
    const form = new FormData();
    form.append('file', file);
    if (opts.fullName) form.append('full_name', opts.fullName);
    if (opts.source) form.append('source', opts.source);
    if (opts.locationId) form.append('location_id', String(opts.locationId));
    const headers = await buildAuthHeaders();
    const response = await fetch('/api/invitations/visitor-photo', {
      method: 'POST',
      headers,
      body: form,
    });
    if (!response.ok) {
      const err = await parseError(response);
      throw new ApiClientError(response.status, err.code, err.message, err.requestId);
    }
    return response.json() as Promise<{
      media_id: number;
      status: string;
      stored_filename: string;
      mime_type: string;
      file_size: number;
      source: string;
    }>;
  },
  deleteVisitorPhoto: async (mediaId: number) => {
    const headers = await buildAuthHeaders();
    const response = await fetch(`/api/invitations/visitor-photo/${mediaId}`, {
      method: 'DELETE',
      headers,
    });
    if (!response.ok) {
      const err = await parseError(response);
      throw new ApiClientError(response.status, err.code, err.message, err.requestId);
    }
  },
  uploadRegistrationAttachment: async (kind: string, file: File) => {
    const form = new FormData();
    form.append('kind', kind);
    form.append('file', file);
    const headers = await buildAuthHeaders();
    const response = await fetch('/api/invitations/registration-attachments', {
      method: 'POST',
      headers,
      body: form,
    });
    if (!response.ok) {
      const err = await parseError(response);
      throw new ApiClientError(response.status, err.code, err.message, err.requestId);
    }
    return response.json() as Promise<{
      storage_key: string;
      file_name: string;
      kind: string;
      ocr_status: string;
    }>;
  },
  invitationDetail: (id: number) => request<InvitationItem>(`/api/invitations/${id}`),
  invitationQr: (id: number) => request<InvitationItem>(`/api/invitations/${id}/qr`),
  cancelInvitation: (id: number, reason: string) =>
    request<InvitationItem>(`/api/invitations/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  publicInvitation: (token: string) =>
    request<PublicInvitation>(`/api/public/invitations/${encodeURIComponent(token)}`),
  verifyVisitorQr: (body: { token?: string; registration_reference?: string }) =>
    request<QrVerifyResult>('/api/visitor-qr/verify', { method: 'POST', body: JSON.stringify(body) }),
  issueBadge: (visitId: number) =>
    request<BadgeItem>(`/api/badges/visits/${visitId}/issue`, { method: 'POST', body: '{}' }),
  printBadge: (visitId: number) =>
    request<BadgeItem>(`/api/badges/visits/${visitId}/print`, { method: 'POST', body: '{}' }),
  getBadge: (visitId: number) => request<BadgeItem>(`/api/badges/visits/${visitId}`),

  hostApprovalSummary: (token: string) =>
    request<HostApprovalPublic>(`/api/public/host-approvals/${encodeURIComponent(token)}`),
  hostRejectionReasons: () =>
    request<HostRejectionReason[]>('/api/public/host-approvals/rejection-reasons'),
  hostApprove: (token: string) =>
    request<HostApprovalAction>('/api/public/host-approvals/approve', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  hostReject: (token: string, reasonCode: string, comment?: string) =>
    request<HostApprovalAction>('/api/public/host-approvals/reject', {
      method: 'POST',
      body: JSON.stringify({ token, reason_code: reasonCode, comment }),
    }),
  devNotifications: () => request<NotificationList>('/api/dev/notifications'),
  resendHostApproval: (visitId: number) =>
    request<{ success: boolean }>(`/api/approvals/${visitId}/resend-host-approval`, { method: 'POST', body: '{}' }),

  watchlist: (params: {
    search?: string;
    scope?: string;
    location_id?: number;
    status?: string;
    action_level?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.scope) q.set('scope', params.scope);
    if (params.location_id) q.set('location_id', String(params.location_id));
    if (params.status) q.set('status', params.status);
    if (params.action_level) q.set('action_level', params.action_level);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<WatchlistList>(`/api/watchlist${qs ? `?${qs}` : ''}`);
  },
  watchlistDetail: (id: number) => request<WatchlistItem>(`/api/watchlist/${id}`),
  createWatchlistEntry: (payload: Record<string, unknown>) =>
    request<WatchlistItem>('/api/watchlist', { method: 'POST', body: JSON.stringify(payload) }),
  deactivateWatchlistEntry: (id: number) =>
    request<WatchlistItem>(`/api/watchlist/${id}/deactivate`, { method: 'POST', body: '{}' }),

  securityReviews: (params: { tab?: string; search?: string; site?: number; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.tab) q.set('tab', params.tab);
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<SecurityReviewList>(`/api/security-reviews${qs ? `?${qs}` : ''}`);
  },
  securityReviewDetail: (visitId: number) => request<SecurityReviewItem>(`/api/security-reviews/${visitId}`),
  clearSecurityReview: (visitId: number, comment?: string) =>
    request<SecurityReviewItem>(`/api/security-reviews/${visitId}/clear`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }),
  blockSecurityReview: (visitId: number, comment: string) =>
    request<SecurityReviewItem>(`/api/security-reviews/${visitId}/block`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }),

  vendorCompanies: (params: { search?: string; location_id?: number; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.location_id) q.set('location_id', String(params.location_id));
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<VendorCompanyList>(`/api/vendor-companies${qs ? `?${qs}` : ''}`);
  },
  createVendorCompany: (payload: Record<string, unknown>) =>
    request<VendorCompanyItem>('/api/vendor-companies', { method: 'POST', body: JSON.stringify(payload) }),
  vendorCompanyDetail: (id: number) => request<VendorCompanyDetail>(`/api/vendor-companies/${id}`),
  createVendorVisit: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/vendor-visits', { method: 'POST', body: JSON.stringify(payload) }),
  complianceReviews: (params: { search?: string; site?: number; tab?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.tab) q.set('tab', params.tab);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<ComplianceReviewList>(`/api/compliance/reviews${qs ? `?${qs}` : ''}`);
  },
  contractorVisits: (params: { search?: string; site?: number; compliance_status?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.site) q.set('site', String(params.site));
    if (params.compliance_status) q.set('compliance_status', params.compliance_status);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<ContractorVisitList>(`/api/compliance/contractor-visits${qs ? `?${qs}` : ''}`);
  },
  complianceRequirements: () =>
    request<Array<{ id: number; code: string; name: string; document_owner_type: string; is_mandatory: boolean; validity_required: boolean }>>('/api/compliance/requirements'),
  complianceRequirementsAdmin: (includeInactive = true) =>
    request<ComplianceRequirementItem[]>(`/api/compliance/requirements/admin?include_inactive=${includeInactive}`),
  createComplianceRequirement: (payload: Record<string, unknown>) =>
    request<ComplianceRequirementItem>('/api/compliance/requirements', { method: 'POST', body: JSON.stringify(payload) }),
  updateComplianceRequirement: (id: number, payload: Record<string, unknown>) =>
    request<ComplianceRequirementItem>(`/api/compliance/requirements/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateComplianceRequirement: (id: number) =>
    request<ComplianceRequirementItem>(`/api/compliance/requirements/${id}/deactivate`, { method: 'POST', body: '{}' }),
  complianceVisitDetail: (visitId: number) =>
    request<ComplianceVisitDetail>(`/api/compliance/visits/${visitId}/detail`),
  evaluateCompliance: (visitId: number) =>
    request<ComplianceVisitDetail['compliance']>(`/api/compliance/visits/${visitId}/evaluate`, { method: 'POST', body: '{}' }),
  uploadComplianceDocument: (formData: FormData) =>
    uploadForm<ComplianceDocumentItem>('/api/compliance-documents', formData),
  verifyComplianceDocument: (documentId: number, visitId?: number) => {
    const q = visitId ? `?visit_id=${visitId}` : '';
    return request<ComplianceDocumentItem>(`/api/compliance-documents/${documentId}/verify${q}`, { method: 'POST', body: '{}' });
  },
  rejectComplianceDocument: (documentId: number, comment: string, visitId?: number) => {
    const q = visitId ? `?visit_id=${visitId}` : '';
    return request<ComplianceDocumentItem>(`/api/compliance-documents/${documentId}/reject${q}`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    });
  },
  downloadComplianceDocument: (documentId: number) =>
    downloadBlob(`/api/compliance-documents/${documentId}/download`),

  emergencyActive: (locationId?: number) => {
    const q = locationId ? `?location_id=${locationId}` : '';
    return request<EmergencyEventItem[]>(`/api/emergencies/active${q}`);
  },
  emergencyOverview: () => request<EmergencyOverviewItem[]>('/api/emergencies/overview'),
  emergencyHistory: (params: { location_id?: number; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.location_id) q.set('location_id', String(params.location_id));
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<EmergencyHistoryList>(`/api/emergencies/history${qs ? `?${qs}` : ''}`);
  },
  emergencyOnsiteCount: (locationId: number) =>
    request<{ location_id: number; onsite_count: number }>(`/api/emergencies/onsite-count?location_id=${locationId}`),
  startEmergency: (payload: { location_id: number; reason: string; notes?: string }) =>
    request<EmergencyEventItem>('/api/emergencies', { method: 'POST', body: JSON.stringify(payload) }),
  emergencyDetail: (id: number) => request<EmergencyEventItem>(`/api/emergencies/${id}`),
  emergencyRollCall: (emergencyId: number, search?: string) => {
    const q = search ? `?search=${encodeURIComponent(search)}` : '';
    return request<EmergencyRollCallEntryItem[]>(`/api/emergencies/${emergencyId}/roll-call${q}`);
  },
  emergencyRollCallEntry: (emergencyId: number, entryId: number) =>
    request<EmergencyRollCallEntryItem>(`/api/emergencies/${emergencyId}/entries/${entryId}`),
  updateRollCallStatus: (emergencyId: number, entryId: number, payload: { status: string; comment?: string; expected_version?: number }) =>
    request<EmergencyRollCallEntryItem>(`/api/emergencies/${emergencyId}/entries/${entryId}/status`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  closeEmergency: (emergencyId: number, payload: { closure_comment?: string; confirm_unresolved?: boolean }) =>
    request<EmergencyEventItem>(`/api/emergencies/${emergencyId}/close`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  analyticsDashboard: (params: {
    period?: string;
    from?: string;
    to?: string;
    location_id?: number;
    visitor_type_id?: number;
    source?: string;
  }) => {
    const q = new URLSearchParams();
    if (params.period) q.set('period', params.period);
    if (params.from) q.set('from', params.from);
    if (params.to) q.set('to', params.to);
    if (params.location_id) q.set('location_id', String(params.location_id));
    if (params.visitor_type_id) q.set('visitor_type_id', String(params.visitor_type_id));
    if (params.source) q.set('source', params.source);
    const qs = q.toString();
    return request<DashboardData>(`/api/analytics/dashboard${qs ? `?${qs}` : ''}`);
  },

  dashboardKpiDrillDown: (
    kpiKey: string,
    params: { location_id?: number; limit?: number; offset?: number } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.location_id) q.set('location_id', String(params.location_id));
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return request<OperationalVisitList>(
      `/api/analytics/dashboard/kpi/${encodeURIComponent(kpiKey)}${qs ? `?${qs}` : ''}`,
    );
  },

  reportVisits: (params: Record<string, string | number | undefined>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== '') q.set(key, String(val));
    });
    const qs = q.toString();
    return request<ReportVisitList>(`/api/reports/visits?${qs}`);
  },

  exportReportVisits: (
    format: 'csv' | 'xlsx',
    params: Record<string, string | number | undefined>,
  ) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== '') q.set(key, String(val));
    });
    const path = format === 'csv' ? '/api/reports/visits/export.csv' : '/api/reports/visits/export.xlsx';
    return downloadBlob(`${path}?${q.toString()}`);
  },

  copilotSuggestions: () =>
    request<{ suggestions: string[] }>('/api/ai/copilot/suggestions'),

  copilotQuery: (payload: { question: string; location_id?: number; session_id?: number }) =>
    request<CopilotResponse>('/api/ai/copilot/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  aiInsights: (params: { location_id?: number; priority?: string; insight_type?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params.location_id) q.set('location_id', String(params.location_id));
    if (params.priority) q.set('priority', params.priority);
    if (params.insight_type) q.set('insight_type', params.insight_type);
    if (params.status) q.set('status', params.status);
    const qs = q.toString();
    return request<{ items: AIInsightItem[] }>(`/api/ai/insights${qs ? `?${qs}` : ''}`);
  },

  aiInsightsRefresh: (locationId?: number) => {
    const q = locationId ? `?location_id=${locationId}` : '';
    return request<{ generated: number }>(`/api/ai/insights/refresh${q}`, { method: 'POST', body: '{}' });
  },

  aiInsightDismiss: (id: number) =>
    request<{ id: number; status: string }>(`/api/ai/insights/${id}/dismiss`, { method: 'POST', body: '{}' }),

  adminUsers: () => request<AdminUserItem[]>('/api/administration/users'),
  createAdminUser: (payload: {
    email: string;
    display_name: string;
    role: string;
    location_ids: number[];
    is_active?: boolean;
    temporary_password?: string;
    generate_password?: boolean;
    force_password_change?: boolean;
  }) =>
    request<AdminUserItem>('/api/administration/users', { method: 'POST', body: JSON.stringify(payload) }),
  resetAdminUserPassword: (
    id: number,
    payload: { temporary_password: string; confirm_password: string; force_password_change?: boolean },
  ) =>
    request<AdminUserItem>(`/api/administration/users/${id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateAdminUser: (id: number, payload: Record<string, unknown>) =>
    request<AdminUserItem>(`/api/administration/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateAdminUser: (id: number) =>
    request<AdminUserItem>(`/api/administration/users/${id}/deactivate`, { method: 'POST', body: '{}' }),
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string; expires_in: number; force_password_change: boolean }>(
      '/api/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) },
    ),
  ownerLogin: (email: string, password: string) =>
    request<{ access_token: string; token_type: string; expires_in: number; force_password_change: boolean }>(
      '/api/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) },
    ),
  setPassword: (newPassword: string, confirmPassword: string) =>
    request<{ status: string }>('/api/auth/set-password', {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword, confirm_password: confirmPassword }),
    }),
  changePassword: (currentPassword: string, newPassword: string, confirmPassword: string) =>
    request<{ status: string }>('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    }),
  authLogout: () => request<{ status: string }>('/api/auth/logout', { method: 'POST', body: '{}' }),

  retentionPolicies: () => request<RetentionPolicyItem[]>('/api/administration/privacy-security/retention/policies'),
  retentionPreview: (policyId: number) =>
    request<Record<string, unknown>>(`/api/administration/privacy-security/retention/policies/${policyId}/preview`),
  retentionExecute: (policyId: number) =>
    request<Record<string, unknown>>(
      `/api/administration/privacy-security/retention/policies/${policyId}/execute`,
      { method: 'POST', body: '{}' },
    ),
  securityReadiness: () => request<Record<string, unknown>>('/api/administration/privacy-security/readiness'),
  auditIntegrity: () => request<Record<string, unknown>>('/api/administration/privacy-security/audit-integrity'),
  fileSecurityStatus: () => request<Record<string, unknown>>('/api/administration/privacy-security/file-security'),

  operationsReadiness: () => request<Record<string, unknown>>('/api/administration/operations/readiness'),

  accessCredentials: (attention = false) =>
    request<Record<string, unknown>[]>(`/api/access/credentials${attention ? '?attention=true' : ''}`),
  retryAccessCredential: (id: number) =>
    request<Record<string, unknown>>(`/api/access/credentials/${id}/retry`, { method: 'POST', body: '{}' }),
  revokeAccessCredential: (id: number) =>
    request<Record<string, unknown>>(`/api/access/credentials/${id}/revoke`, { method: 'POST', body: '{}' }),
  badgePrintJobs: (attention = false) =>
    request<Record<string, unknown>[]>(`/api/badge-print-jobs${attention ? '?attention=true' : ''}`),
  retryBadgePrintJob: (id: number) =>
    request<Record<string, unknown>>(`/api/badge-print-jobs/${id}/retry`, { method: 'POST', body: '{}' }),
  physicalPrintBadge: (visitId: number, payload?: { printer_id?: number; idempotency_key?: string }) =>
    request<Record<string, unknown>>(`/api/badges/visits/${visitId}/physical-print`, {
      method: 'POST',
      body: JSON.stringify(payload ?? {}),
    }),
  physicalIntegrationStatus: () => request<Record<string, unknown>>('/api/physical-integrations/status'),
  accessLocationConfigs: () => request<Record<string, unknown>[]>('/api/access/config/locations'),
  accessProfiles: (locationId?: number) =>
    request<Record<string, unknown>[]>(
      `/api/access/profiles${locationId ? `?location_id=${locationId}` : ''}`,
    ),
  accessProfileMappings: (locationId?: number) =>
    request<Record<string, unknown>[]>(
      `/api/access/profile-mappings${locationId ? `?location_id=${locationId}` : ''}`,
    ),
  badgePrinters: (locationId?: number) =>
    request<Record<string, unknown>[]>(
      `/api/badge-printers${locationId ? `?location_id=${locationId}` : ''}`,
    ),
  createAccessProfile: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/access/profiles', { method: 'POST', body: JSON.stringify(payload) }),
  updateAccessProfile: (id: number, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/access/profiles/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateAccessProfile: (id: number) =>
    request<Record<string, unknown>>(`/api/access/profiles/${id}/deactivate`, { method: 'POST', body: '{}' }),
  createAccessProfileMapping: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/access/profile-mappings', { method: 'POST', body: JSON.stringify(payload) }),
  updateAccessProfileMapping: (id: number, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/access/profile-mappings/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateAccessProfileMapping: (id: number) =>
    request<Record<string, unknown>>(`/api/access/profile-mappings/${id}/deactivate`, { method: 'POST', body: '{}' }),
  updateAccessLocationConfig: (locationId: number, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/access/config/locations/${locationId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  createBadgePrinter: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/badge-printers', { method: 'POST', body: JSON.stringify(payload) }),
  updateBadgePrinter: (id: number, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/badge-printers/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  setDefaultBadgePrinter: (id: number) =>
    request<Record<string, unknown>>(`/api/badge-printers/${id}/set-default`, { method: 'POST', body: '{}' }),
  deactivateBadgePrinter: (id: number) =>
    request<Record<string, unknown>>(`/api/badge-printers/${id}/deactivate`, { method: 'POST', body: '{}' }),
  accessAttentionItems: () => request<Record<string, unknown>[]>('/api/access/attention'),
};

interface RetentionPolicyItem {
  id: number;
  data_category: string;
  scope_type: string;
  location_id: number | null;
  location_name: string | null;
  retention_days: number;
  action: string;
  is_active: boolean;
}

interface AdminUserItem {
  id: number;
  email: string;
  display_name: string | null;
  role: string;
  is_owner: boolean;
  is_active: boolean;
  location_ids: number[];
  assigned_locations: Array<{ id: number; name: string; code: string; city?: string | null }>;
  entra_linked: boolean;
  auth_provider?: string | null;
  last_login_at: string | null;
  identity_linked_at: string | null;
}

export { ApiClientError };
