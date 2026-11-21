import React, { useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { PROFILE_GATE_ALLOWED, useAuth } from '../../contexts/useAuth';
import { Sidebar } from './Sidebar';
import { Navbar } from './Navbar';

export const DashboardLayout: React.FC = () => {
  // Below the lg breakpoint the sidebar is an off-canvas drawer opened from the navbar.
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { needsProfile } = useAuth();
  const location = useLocation();

  // The onboarding checklist is generated from the profile, so nothing else works until it exists.
  if (needsProfile && !PROFILE_GATE_ALLOWED.includes(location.pathname)) {
    return <Navigate to="/app/profile" replace />;
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-(--bg-primary)">
      <Sidebar mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Navbar onMenuClick={() => setMobileNavOpen(true)} />
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
