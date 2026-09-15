export type DashboardKpiId =
  | 'expected_today'
  | 'awaiting_approval'
  | 'checked_in_today'
  | 'onsite_now'
  | 'checked_out_today'
  | 'overstayed'
  | 'vendor_contractor_onsite';

export interface DashboardKpiDefinition {
  id: DashboardKpiId;
  label: string;
  navigatePath?: string;
  useModal: boolean;
  ariaLabel: string;
}

export const DASHBOARD_KPIS: DashboardKpiDefinition[] = [
  {
    id: 'expected_today',
    label: 'Expected Today',
    navigatePath: '/expected-today',
    useModal: false,
    ariaLabel: 'View today\'s expected visitors',
  },
  {
    id: 'awaiting_approval',
    label: 'Awaiting Approval',
    navigatePath: '/approvals',
    useModal: false,
    ariaLabel: 'View registrations awaiting approval',
  },
  {
    id: 'checked_in_today',
    label: 'Checked In Today',
    useModal: true,
    ariaLabel: 'View visitors checked in today',
  },
  {
    id: 'onsite_now',
    label: 'Onsite Now',
    navigatePath: '/onsite-now',
    useModal: false,
    ariaLabel: 'View visitors currently onsite',
  },
  {
    id: 'checked_out_today',
    label: 'Checked Out Today',
    useModal: true,
    ariaLabel: 'View visitors checked out today',
  },
  {
    id: 'overstayed',
    label: 'Overstayed',
    useModal: true,
    ariaLabel: 'View overstayed visitors',
  },
  {
    id: 'vendor_contractor_onsite',
    label: 'Vendor/Contractor Onsite',
    useModal: true,
    ariaLabel: 'View vendor and contractor visitors onsite',
  },
];

export function buildKpiNavigationPath(
  kpi: DashboardKpiDefinition,
  siteId?: number,
): string | undefined {
  if (!kpi.navigatePath) return undefined;
  const params = new URLSearchParams();
  if (siteId) params.set('site', String(siteId));
  if (kpi.id === 'awaiting_approval') params.set('status', 'PENDING_APPROVAL');
  const qs = params.toString();
  return qs ? `${kpi.navigatePath}?${qs}` : kpi.navigatePath;
}

export function shouldUseKpiModal(
  kpi: DashboardKpiDefinition,
  siteId?: number,
): boolean {
  if (kpi.useModal) return true;
  if (kpi.id === 'awaiting_approval' && siteId !== undefined) return true;
  return false;
}
