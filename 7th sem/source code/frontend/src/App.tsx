import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { ThemeProvider } from './contexts/ThemeContext';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './contexts/useAuth';

// Page Loading Fallback Spinner
const PageLoader = () => (
  <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3">
    <div className="w-10 h-10 border-4 border-primary-500/30 border-t-primary-500 rounded-full animate-spin"></div>
    <span className="text-sm text-(--text-muted) animate-pulse font-medium">Loading view...</span>
  </div>
);

// Protected Route Wrapper
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="min-h-screen flex items-center justify-center"><div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div></div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

// Admin Route Wrapper (Only HR Admin can access)
const AdminRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="min-h-screen flex items-center justify-center"><div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div></div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.role !== 'hr_admin') {
    return <Navigate to="/app/dashboard" replace />;
  }
  return <>{children}</>;
};

// Employee Route Wrapper (Redirects HR Admin to HR Dashboard)
const EmployeeRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="min-h-screen flex items-center justify-center"><div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div></div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.role === 'hr_admin') {
    return <Navigate to="/app/admin" replace />;
  }
  return <>{children}</>;
};

// Role-Aware Default Home
const AppIndexRedirect = () => {
  const { user } = useAuth();
  if (user?.role === 'hr_admin') {
    return <Navigate to="admin" replace />;
  }
  return <Navigate to="dashboard" replace />;
};

// Auth Pages (Lazy Loaded)
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })));
const SignupPage = lazy(() => import('./pages/SignupPage').then(m => ({ default: m.SignupPage })));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then(m => ({ default: m.ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then(m => ({ default: m.ResetPasswordPage })));

// App Pages (Lazy Loaded)
const AppDashboardPage = lazy(() => import('./pages/AppDashboardPage').then(m => ({ default: m.AppDashboardPage })));
const ChatPage = lazy(() => import('./pages/ChatPage').then(m => ({ default: m.ChatPage })));
const ChecklistPage = lazy(() => import('./pages/ChecklistPage').then(m => ({ default: m.ChecklistPage })));
const ProfileSetupPage = lazy(() => import('./pages/ProfileSetupPage').then(m => ({ default: m.ProfileSetupPage })));
const KnowledgeBasePage = lazy(() => import('./pages/KnowledgeBasePage').then(m => ({ default: m.KnowledgeBasePage })));
const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage').then(m => ({ default: m.AdminDashboardPage })));
const EmployeeDetailPage = lazy(() => import('./pages/EmployeeDetailPage').then(m => ({ default: m.EmployeeDetailPage })));
const TimelinePage = lazy(() => import('./pages/TimelinePage').then(m => ({ default: m.TimelinePage })));
const IntegrationsPage = lazy(() => import('./pages/IntegrationsPage').then(m => ({ default: m.IntegrationsPage })));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })));
const RoadmapPage = lazy(() => import('./pages/RoadmapPage').then(m => ({ default: m.RoadmapPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));
const GitHubCallbackPage = lazy(() => import('./pages/GitHubCallbackPage').then(m => ({ default: m.GitHubCallbackPage })));

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ErrorBoundary>
        <Toaster
          position="top-right"
          toastOptions={{
            className: '!bg-(--bg-card) !text-(--text-primary) !border !border-(--border-default) !shadow-lg',
            duration: 3000,
          }}
        />
        <BrowserRouter>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              {/* Auth Routes */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

              {/* Dashboard App Routes - Protected */}
              <Route path="/app" element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }>
                <Route index element={<AppIndexRedirect />} />
                
                {/* Employee-Only Pages */}
                <Route path="dashboard" element={<EmployeeRoute><AppDashboardPage /></EmployeeRoute>} />
                <Route path="checklist" element={<EmployeeRoute><ChecklistPage /></EmployeeRoute>} />
                <Route path="profile" element={<EmployeeRoute><ProfileSetupPage /></EmployeeRoute>} />
                <Route path="roadmap" element={<EmployeeRoute><RoadmapPage /></EmployeeRoute>} />
                <Route path="timeline" element={<EmployeeRoute><TimelinePage /></EmployeeRoute>} />
                <Route path="chat" element={<EmployeeRoute><ChatPage /></EmployeeRoute>} />

                {/* Shared Platform Pages */}
                <Route path="knowledge" element={<KnowledgeBasePage />} />
                <Route path="integrations" element={<IntegrationsPage />} />
                <Route path="settings" element={<SettingsPage />} />

                {/* HR Admin-Only Pages */}
                <Route path="admin" element={<AdminRoute><AdminDashboardPage /></AdminRoute>} />
                <Route path="admin/employees/:sessionId" element={<AdminRoute><EmployeeDetailPage /></AdminRoute>} />
                <Route path="analytics" element={<AdminRoute><AnalyticsPage /></AdminRoute>} />
              </Route>

              {/* Root Route redirects to App Login */}
              <Route path="/" element={<Navigate to="/login" replace />} />

              {/* GitHub OAuth callback – must be outside /app so it works before full auth */}
              <Route path="/integrations/github/callback" element={<Suspense fallback={<PageLoader />}><GitHubCallbackPage /></Suspense>} />

              {/* Catch-all */}
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ErrorBoundary>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;

