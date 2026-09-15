import { DashboardPage } from '../pages/dashboard/DashboardPage';
import { VisitorsPage } from '../pages/visitors/VisitorsPage';
import { ExpectedTodayPage } from '../pages/expected-today/ExpectedTodayPage';
import { OnsiteNowPage } from '../pages/onsite/OnsiteNowPage';
import { InvitationsPage } from '../pages/invitations/InvitationsPage';
import { CreateInvitationPage } from '../pages/invitations/CreateInvitationPage';
import { SelfRegistrationsPage } from '../pages/self-registrations/SelfRegistrationsPage';
import { SelfRegistrationQrPage } from '../pages/self-registrations/SelfRegistrationQrPage';
import { VendorsContractorsPage } from '../pages/vendors/VendorsContractorsPage';
import { CreateVendorVisitPage } from '../pages/vendors/CreateVendorVisitPage';
import { ApprovalsPage } from '../pages/approvals/ApprovalsPage';
import { WatchlistPage } from '../pages/watchlist/WatchlistPage';
import { SecurityReviewPage } from '../pages/security-review/SecurityReviewPage';
import { LocationsPage } from '../pages/locations/LocationsPage';
import { ReportsPage } from '../pages/reports/ReportsPage';
import { VmsCopilotPage } from '../pages/vms-copilot/VmsCopilotPage';
import { AccessOperationsPage } from '../pages/access-operations/AccessOperationsPage';
import { AdministrationPage } from '../pages/administration/AdministrationPage';
import { AdministrationUsersPage } from '../pages/administration/AdministrationUsersPage';
import { PrivacySecurityPage } from '../pages/administration/PrivacySecurityPage';
import { AccessBadgesAdminPage } from '../pages/administration/AccessBadgesAdminPage';
import { OperationsReadinessPage } from '../pages/administration/OperationsReadinessPage';
import { VisitorWelcomePage } from '../pages/visit/VisitorWelcomePage';
import { VisitorRegistrationPage } from '../pages/visit/VisitorRegistrationPage';
import { RegistrationSuccessPage } from '../pages/visit/RegistrationSuccessPage';
import { VisitorInvitationPage } from '../pages/visit/VisitorInvitationPage';
import { BadgePrintPage } from '../pages/badges/BadgePrintPage';
import { HostApprovalPage } from '../pages/host/HostApprovalPage';
import { DevNotificationsPage } from '../pages/dev/DevNotificationsPage';
import { ProfilePage } from '../pages/profile/ProfilePage';
import { PreferencesPage } from '../pages/profile/PreferencesPage';
import { DevLoginPage } from '../pages/login/LoginPage';
import { EntraLoginPage } from '../pages/login/EntraLoginPage';
import { AuthCallbackPage } from '../pages/auth/AuthCallbackPage';

/** Completed staff routes — must not render foundation placeholder shells. */
export const COMPLETED_STAFF_ROUTES = [
  { path: '/dashboard', Component: DashboardPage, marker: 'Visitor Management Dashboard' },
  { path: '/visitors', Component: VisitorsPage, marker: 'Visitor records and visit history' },
  { path: '/expected-today', Component: ExpectedTodayPage, marker: 'Expected Today' },
  { path: '/onsite-now', Component: OnsiteNowPage, marker: 'Onsite Now' },
  { path: '/invitations', Component: InvitationsPage, marker: 'Invitations' },
  { path: '/self-registrations', Component: SelfRegistrationsPage, marker: 'Self Registrations' },
  { path: '/self-registrations/qr', Component: SelfRegistrationQrPage, marker: 'Reception QR' },
  { path: '/vendors-contractors', Component: VendorsContractorsPage, marker: 'Vendors & Contractors' },
  { path: '/approvals', Component: ApprovalsPage, marker: 'Approvals' },
  { path: '/watchlist', Component: WatchlistPage, marker: 'Watchlist' },
  { path: '/security-review', Component: SecurityReviewPage, marker: 'Security Review' },
  { path: '/locations', Component: LocationsPage, marker: 'Locations' },
  { path: '/reports', Component: ReportsPage, marker: 'Reports' },
  { path: '/vms-copilot', Component: VmsCopilotPage, marker: 'VMS Copilot' },
  { path: '/access-operations', Component: AccessOperationsPage, marker: 'Access Operations' },
  { path: '/administration', Component: AdministrationPage, marker: 'Configure users, security' },
  { path: '/administration/users', Component: AdministrationUsersPage, marker: 'Users & Access' },
  { path: '/administration/privacy-security', Component: PrivacySecurityPage, marker: 'Privacy & Security' },
  { path: '/administration/access-badges', Component: AccessBadgesAdminPage, marker: 'Access & Badge' },
  { path: '/administration/operations-readiness', Component: OperationsReadinessPage, marker: 'Operations' },
  { path: '/profile', Component: ProfilePage, marker: 'My Profile' },
  { path: '/preferences', Component: PreferencesPage, marker: 'Preferences' },
] as const;

export const PLACEHOLDER_BANNED_TEXT = [
  'Next Phase',
  'Coming in the next implementation phase',
  'foundation shell',
  'ready for future development',
];

export const PUBLIC_ROUTE_COMPONENTS = [
  { path: '/visit', Component: VisitorWelcomePage, marker: 'Welcome to Visitor Check-In' },
  { path: '/visit/register', Component: VisitorRegistrationPage, marker: 'Registration' },
  { path: '/visit/register/success', Component: RegistrationSuccessPage, marker: 'Registration' },
  { path: '/visit/invitation', Component: VisitorInvitationPage, marker: 'Invitation' },
  { path: '/badges/print', Component: BadgePrintPage, marker: 'Badge' },
  { path: '/host/approval', Component: HostApprovalPage, marker: 'Host Approval' },
  { path: '/dev/notifications', Component: DevNotificationsPage, marker: 'Notifications' },
  { path: '/login', Component: DevLoginPage, marker: 'Sign in' },
  { path: '/auth/callback', Component: AuthCallbackPage, marker: 'Signing in' },
  { path: '/login-entra', Component: EntraLoginPage, marker: 'Sign in' },
];
