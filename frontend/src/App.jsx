import { useEffect, useState } from 'react';
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';

import LandingPage    from './pages/LandingPage';
import LoginPage      from './pages/LoginPage';
import RegisterPage   from './pages/RegisterPage';
import DashboardPage  from './pages/DashboardPage';
import UploadPage     from './pages/UploadPage';
import AnalysisPage   from './pages/AnalysisPage';
import ComparisonPage from './pages/ComparisonPage';
import SignaturePage  from './pages/SignaturePage';
import { authApi }    from './api/documents';

const NAV_LINKS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/upload',    label: 'Upload'    },
  { to: '/comparison',label: 'Compare'   },
  { to: '/signature', label: 'Sign'      },
];

function AppShell({ children }) {
  const location  = useLocation();
  const navigate  = useNavigate();
  const [userEmail, setUserEmail] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);

  const isPublic = ['/', '/login', '/register'].includes(location.pathname);

  useEffect(() => {
    if (!isPublic) {
      authApi.me().then((r) => setUserEmail(r.data.email)).catch(() => {});
    }
  }, [isPublic]);

  function handleLogout() {
    window.localStorage.removeItem('clauseguard_access_token');
    window.localStorage.removeItem('clauseguard_refresh_token');
    window.localStorage.removeItem('clauseguard_signature_document_id');
    navigate('/login');
  }

  if (isPublic) return children;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 antialiased">
      {/* Top nav */}
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center gap-2.5 flex-shrink-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-xs font-black text-white">CG</div>
            <div className="hidden sm:block">
              <p className="text-sm font-bold tracking-tight text-slate-900 leading-none">ClauseGuard</p>
              <p className="text-[10px] text-slate-400 leading-none mt-0.5">Legal risk analyzer</p>
            </div>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map(({ to, label }) => (
              <NavLink
                key={to} to={to}
                className={({ isActive }) =>
                  `rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                    isActive
                      ? 'bg-slate-900 text-white'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-3">
            {userEmail && (
              <div className="hidden items-center gap-2 sm:flex">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-100 text-xs font-bold text-teal-700">
                  {userEmail[0].toUpperCase()}
                </div>
                <span className="hidden text-xs text-slate-500 lg:block max-w-[140px] truncate">{userEmail}</span>
              </div>
            )}
            <button
              type="button" onClick={handleLogout}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
            >
              Sign out
            </button>

            {/* Mobile hamburger */}
            <button
              type="button" onClick={() => setMobileOpen((v) => !v)}
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 md:hidden"
              aria-label="Toggle menu"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                {mobileOpen
                  ? <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  : <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="border-t border-slate-100 bg-white px-4 pb-4 md:hidden">
            {NAV_LINKS.map(({ to, label }) => (
              <NavLink
                key={to} to={to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `block rounded-lg px-3 py-2.5 text-sm font-medium mt-1 ${
                    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </div>
        )}
      </header>

      {children}
    </div>
  );
}

function RequireAuth({ children }) {
  const token = window.localStorage.getItem('clauseguard_access_token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/"           element={<LandingPage />} />
        <Route path="/login"      element={<LoginPage />} />
        <Route path="/register"   element={<RegisterPage />} />
        <Route path="/dashboard"  element={<RequireAuth><DashboardPage /></RequireAuth>} />
        <Route path="/upload"     element={<RequireAuth><UploadPage /></RequireAuth>} />
        <Route path="/analysis/:id" element={<RequireAuth><AnalysisPage /></RequireAuth>} />
        <Route path="/comparison" element={<RequireAuth><ComparisonPage /></RequireAuth>} />
        <Route path="/signature"  element={<RequireAuth><SignaturePage /></RequireAuth>} />
        <Route path="*"           element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
