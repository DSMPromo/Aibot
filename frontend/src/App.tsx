import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { Toaster } from '@/components/ui/toaster'

// Layouts
import AuthLayout from '@/features/auth/AuthLayout'
import DashboardLayout from '@/features/dashboard/DashboardLayout'

// Auth pages
import LoginPage from '@/features/auth/LoginPage'
import RegisterPage from '@/features/auth/RegisterPage'
import ForgotPasswordPage from '@/features/auth/ForgotPasswordPage'

// Dashboard pages
import DashboardPage from '@/features/dashboard/DashboardPage'

// Settings pages
import {
  SettingsLayout,
  ProfilePage,
  ConnectionsPage,
  AlertsPage,
  SecurityPage,
  BillingPage,
  OAuthCallbackPage,
} from '@/features/settings'

// Campaign pages
import { CampaignWizard, CampaignsListPage, CampaignDetailPage } from '@/features/campaigns'

// Automation pages
import { AutomationPage } from '@/features/automation'

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Public route wrapper (redirects if already authenticated)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <>
      <Routes>
        {/* Public auth routes */}
        <Route
          element={
            <PublicRoute>
              <AuthLayout />
            </PublicRoute>
          }
        >
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        </Route>

        {/* Protected dashboard routes */}
        <Route
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />

          {/* Settings routes */}
          <Route path="/settings" element={<SettingsLayout />}>
            <Route index element={<Navigate to="/settings/profile" replace />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="connections" element={<ConnectionsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="security" element={<SecurityPage />} />
            <Route path="billing" element={<BillingPage />} />
          </Route>

          {/* Campaign routes */}
          <Route path="/campaigns" element={<CampaignsListPage />} />
          <Route path="/campaigns/new" element={<CampaignWizard />} />
          <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
          <Route path="/analytics" element={<div className="text-muted-foreground">Analytics coming in Phase 4</div>} />
          <Route path="/ai-studio" element={<div className="text-muted-foreground">AI Studio coming in Phase 3</div>} />
          <Route path="/automation" element={<AutomationPage />} />
        </Route>

        {/* OAuth callback (standalone page for popup) */}
        <Route
          path="/oauth/callback/:platform"
          element={
            <ProtectedRoute>
              <OAuthCallbackPage />
            </ProtectedRoute>
          }
        />

        {/* Redirects */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>

      <Toaster />
    </>
  )
}

export default App
