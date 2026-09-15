/** Near-real-time operational refresh intervals (milliseconds). */
export const OPERATIONAL_REFRESH_MS = {
  dashboard: 30000,
  expectedToday: 20000,
  onsiteNow: 15000,
  approvals: 20000,
  securityReview: 20000,
  selfRegistrations: 30000,
  accessOperations: 12000,
  operationsReadiness: 30000,
  visitors: 30000,
} as const;

export type OperationalRefreshKey = keyof typeof OPERATIONAL_REFRESH_MS;
