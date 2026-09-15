const CAPABILITY_GROUPS: Array<{ label: string; permissions: string[] }> = [
  {
    label: 'Visitor Operations',
    permissions: [
      'visitor.read',
      'visitor.create',
      'visitor.checkin',
      'visitor.checkout',
      'visitor.verify',
      'checkin.perform',
      'checkout.perform',
      'arrival.read',
      'onsite.read',
    ],
  },
  {
    label: 'Security Operations',
    permissions: [
      'security_screening.read',
      'security_screening.review',
      'watchlist.read',
      'visitor_qr.verify',
    ],
  },
  {
    label: 'Vendor Compliance',
    permissions: ['vendor_company.read', 'compliance.read', 'compliance.verify'],
  },
  {
    label: 'Emergency Management',
    permissions: ['emergency.read', 'emergency.rollcall', 'emergency.start'],
  },
  {
    label: 'Reporting & Analytics',
    permissions: ['reports.view', 'analytics.dashboard.view', 'analytics.weekly.view'],
  },
  {
    label: 'User Administration',
    permissions: ['admins.read', 'admins.manage'],
  },
  {
    label: 'VMS Configuration',
    permissions: [
      'locations.read',
      'locations.manage',
      'access.config.read',
      'privacy.retention.read',
      'operations.readiness.read',
    ],
  },
  {
    label: 'Approvals & Invitations',
    permissions: ['approval.read', 'invitation.read', 'registration.read'],
  },
  {
    label: 'Access & Badges',
    permissions: ['access.read', 'badge.read', 'badge.print'],
  },
];

export function getCapabilityGroups(permissions: string[]): string[] {
  return CAPABILITY_GROUPS
    .filter((group) => group.permissions.some((p) => permissions.includes(p)))
    .map((group) => group.label);
}

export function getRoleDescription(role: string): string {
  const descriptions: Record<string, string> = {
    GLOBAL_ADMIN: 'Full platform administration and all-location operational access.',
    HEAD_ADMIN: 'Cross-location oversight with reporting and administrative read access.',
    SITE_ADMIN: 'Location-scoped visitor and operational management.',
    SECURITY: 'Location-scoped security desk and visitor verification operations.',
  };
  return descriptions[role] ?? 'VMS staff access according to assigned role and permissions.';
}
