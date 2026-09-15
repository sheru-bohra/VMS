import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AdminLayout } from '../layouts/AdminLayout';
import { VisitorLayout } from '../layouts/VisitorLayout';
import { DashboardPage } from '../pages/dashboard/DashboardPage';
import { VisitorsPage } from '../pages/visitors/VisitorsPage';
import { VisitorWelcomePage } from '../pages/visit/VisitorWelcomePage';
import { VisitorRegistrationPage } from '../pages/visit/VisitorRegistrationPage';
import { RegistrationSuccessPage } from '../pages/visit/RegistrationSuccessPage';
import { SelfRegistrationsPage } from '../pages/self-registrations/SelfRegistrationsPage';
import { SelfRegistrationQrPage } from '../pages/self-registrations/SelfRegistrationQrPage';
import { LocationsPage } from '../pages/locations/LocationsPage';
import { ApprovalsPage } from '../pages/approvals/ApprovalsPage';
import { ExpectedTodayPage } from '../pages/expected-today/ExpectedTodayPage';
import { OnsiteNowPage } from '../pages/onsite/OnsiteNowPage';
import { InvitationsPage } from '../pages/invitations/InvitationsPage';
import { RegisterVisitorPage } from '../pages/register-visitor/RegisterVisitorPage';
import { BadgePrintPage } from '../pages/badges/BadgePrintPage';
import { VisitorInvitationPage } from '../pages/visit/VisitorInvitationPage';
import { HostApprovalPage } from '../pages/host/HostApprovalPage';
import { DevNotificationsPage } from '../pages/dev/DevNotificationsPage';
import { WatchlistPage } from '../pages/watchlist/WatchlistPage';
import { SecurityReviewPage } from '../pages/security-review/SecurityReviewPage';
import { VendorsContractorsPage } from '../pages/vendors/VendorsContractorsPage';
import { CreateVendorVisitPage } from '../pages/vendors/CreateVendorVisitPage';
import { ReportsPage } from '../pages/reports/ReportsPage';
import { VmsCopilotPage } from '../pages/vms-copilot/VmsCopilotPage';
import { DevLoginPage } from '../pages/login/LoginPage';
import { VmsLoginPage } from '../pages/login/VmsLoginPage';
import { AuthCallbackPage } from '../pages/auth/AuthCallbackPage';
import { SetPasswordPage } from '../pages/auth/SetPasswordPage';
import { AdministrationPage } from '../pages/administration/AdministrationPage';
import { AdministrationUsersPage } from '../pages/administration/AdministrationUsersPage';
import { PrivacySecurityPage } from '../pages/administration/PrivacySecurityPage';
import { AccessBadgesAdminPage } from '../pages/administration/AccessBadgesAdminPage';
import { OperationsReadinessPage } from '../pages/administration/OperationsReadinessPage';
import { AccessOperationsPage } from '../pages/access-operations/AccessOperationsPage';
import { ProfilePage } from '../pages/profile/ProfilePage';
import { PreferencesPage } from '../pages/profile/PreferencesPage';
import { useAuth } from '../hooks/useAuth';
import { isDevAuthMode } from '../config/auth';
import { getUnauthenticatedLoginRedirect } from '../auth/authRedirect';
import {
  LoadingState,
  ErrorState,
  NotFoundState,
} from '../components/StatePanels';
import { hasPermission } from '../utils/permissions';
import { getDefaultLandingPath } from '../utils/userPreferences';
import type { PermissionKey, UserProfile } from '../types';
import '../styles/states.css';

const ADMIN_HUB_PERMISSIONS: PermissionKey[] = [
  'admins.read',
  'privacy.retention.read',
  'access.config.read',
  'operations.readiness.read',
  'locations.read',
];

function canAccessAdministration(permissions: string[]) {
  return ADMIN_HUB_PERMISSIONS.some((p) => hasPermission(permissions, p));
}

function DefaultHome({ user }: { user: UserProfile }) {
  const target = getDefaultLandingPath(user.id, user.permissions, user.role);
  return <Navigate to={target} replace />;
}

function ProtectedRoute({
  children,
  permission,
  permissions,
}: {
  children: React.ReactNode;
  permission?: PermissionKey;
  permissions: string[];
}) {
  if (permission && !hasPermission(permissions, permission)) {
    return <ErrorState title="Access denied" message="You do not have permission to view this page." />;
  }
  return <>{children}</>;
}

export function AdminRoutes() {
  const { user, loading, error, reload } = useAuth();
  const location = useLocation();

  if (loading) return <LoadingState message="Loading admin session…" />;
  if (user?.force_password_change) {
    return <Navigate to="/auth/set-password" replace />;
  }
  if (error) {
    return <ErrorState title="Unable to load session" message={error} action={{ label: 'Retry', onClick: reload }} />;
  }
  if (!user) {
    const loginPath = getUnauthenticatedLoginRedirect(location.pathname, location.search);
    return <Navigate to={loginPath} replace />;
  }

  return (
    <Routes>
      <Route element={<AdminLayout user={user} />}>
        <Route index element={<DefaultHome user={user} />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="preferences" element={<PreferencesPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route
          path="visitors"
          element={
            <ProtectedRoute permission="visitor.read" permissions={user.permissions}>
              <VisitorsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="expected-today"
          element={
            <ProtectedRoute permission="arrival.read" permissions={user.permissions}>
              <ExpectedTodayPage />
            </ProtectedRoute>
          }
        />
        <Route path="emergency-roll-call" element={<Navigate to="/dashboard" replace />} />
        <Route
          path="onsite-now"
          element={
            <ProtectedRoute permission="onsite.read" permissions={user.permissions}>
              <OnsiteNowPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="invitations"
          element={
            <ProtectedRoute permission="invitation.read" permissions={user.permissions}>
              <InvitationsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="register-visitor"
          element={
            <ProtectedRoute permission="invitation.create" permissions={user.permissions}>
              <RegisterVisitorPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="invitations/new"
          element={<Navigate to="/register-visitor" replace />}
        />
        <Route path="scan" element={<Navigate to="/dashboard" replace />} />
        <Route
          path="self-registrations/qr"
          element={
            <ProtectedRoute permission="registration.read" permissions={user.permissions}>
              <SelfRegistrationQrPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="self-registrations"
          element={
            <ProtectedRoute permission="registration.read" permissions={user.permissions}>
              <SelfRegistrationsPage />
            </ProtectedRoute>
          }
        />
        <Route path="vendors" element={<Navigate to="/vendors-contractors" replace />} />
        <Route
          path="vendors-contractors"
          element={
            <ProtectedRoute permission="vendor_company.read" permissions={user.permissions}>
              <VendorsContractorsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="vendors-contractors/new-visit"
          element={
            <ProtectedRoute permission="vendor_company.manage" permissions={user.permissions}>
              <CreateVendorVisitPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="approvals"
          element={
            <ProtectedRoute permission="approval.read" permissions={user.permissions}>
              <ApprovalsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="watchlist"
          element={
            <ProtectedRoute permission="watchlist.read" permissions={user.permissions}>
              <WatchlistPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="security-review"
          element={
            <ProtectedRoute permission="security_screening.read" permissions={user.permissions}>
              <SecurityReviewPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="locations"
          element={
            <ProtectedRoute permission="locations.read" permissions={user.permissions}>
              <LocationsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="vms-copilot"
          element={
            <ProtectedRoute permission="ai.copilot.use" permissions={user.permissions}>
              <VmsCopilotPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="reports"
          element={
            <ProtectedRoute permission="reports.view" permissions={user.permissions}>
              <ReportsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="access-operations"
          element={
            <ProtectedRoute permission="access.read" permissions={user.permissions}>
              <AccessOperationsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="administration"
          element={
            canAccessAdministration(user.permissions)
              ? <AdministrationPage />
              : <ErrorState title="Access denied" message="You do not have permission to view administration." />
          }
        />
        <Route
          path="administration/privacy-security"
          element={
            <ProtectedRoute permission="privacy.retention.read" permissions={user.permissions}>
              <PrivacySecurityPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="administration/access-badges"
          element={
            <ProtectedRoute permission="access.config.read" permissions={user.permissions}>
              <AccessBadgesAdminPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="administration/operations-readiness"
          element={
            <ProtectedRoute permission="operations.readiness.read" permissions={user.permissions}>
              <OperationsReadinessPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="administration/users"
          element={
            <ProtectedRoute permission="admins.read" permissions={user.permissions}>
              <AdministrationUsersPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFoundState />} />
      </Route>
    </Routes>
  );
}

export function App() {
  const loginElement = isDevAuthMode ? <DevLoginPage /> : <VmsLoginPage />;

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={loginElement} />
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route path="/auth/set-password" element={<SetPasswordPage />} />
        <Route path="/visit/*" element={<VisitorLayout />}>
          <Route index element={<VisitorWelcomePage />} />
          <Route path="register/:siteToken" element={<VisitorRegistrationPage />} />
          <Route path="register/:siteToken/success" element={<RegistrationSuccessPage />} />
          <Route path="invitation/:token" element={<VisitorInvitationPage />} />
        </Route>
        <Route path="/badges/:visitId/print" element={<BadgePrintPage />} />
        <Route path="/host/approval/:token" element={<HostApprovalPage />} />
        <Route path="/dev/notifications" element={<DevNotificationsPage />} />
        <Route path="/*" element={<AdminRoutes />} />
      </Routes>
    </BrowserRouter>
  );
}
