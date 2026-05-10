import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../api/documents';

function EyeIcon({ open }) {
  return open ? (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

const FEATURES = [
  { icon: '⚖️', text: 'AI-powered clause risk detection' },
  { icon: '💬', text: 'Ask any question about your contract' },
  { icon: '✍️', text: 'Sign with a tamper-proof audit trail' },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.email || !form.password) { setError('Please fill in all fields.'); return; }
    setLoading(true); setError('');
    try {
      const res = await authApi.login(form);
      window.localStorage.setItem('clauseguard_access_token', res.data.access_token);
      window.localStorage.setItem('clauseguard_refresh_token', res.data.refresh_token);
      navigate('/dashboard');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Invalid email or password.');
    } finally { setLoading(false); }
  }

  async function handleDemoLogin() {
    setLoading(true); setError('');
    try {
      const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
      const res = await fetch(`${base}/api/v1/demo/bootstrap`);
      const data = await res.json();
      window.localStorage.setItem('clauseguard_access_token', data.access_token);
      window.localStorage.setItem('clauseguard_refresh_token', data.refresh_token);
      navigate('/dashboard');
    } catch { setError('Demo unavailable.'); }
    finally { setLoading(false); }
  }

  return (
    /* Full-screen split — capped at 1400px so it doesn't stretch on 4K */
    <div className="flex min-h-screen items-stretch bg-slate-900">
      <div className="mx-auto flex w-full max-w-[1400px] shadow-2xl">

        {/* ── Left: Branding panel ────────────────────────────────── */}
        <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-teal-900 p-10 lg:flex lg:w-[46%] xl:p-14">
          {/* Decorative circles */}
          <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-teal-500/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-32 -right-20 h-96 w-96 rounded-full bg-teal-400/8 blur-3xl" />

          <div className="relative flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-500 text-sm font-black text-white shadow-lg">CG</div>
            <span className="text-lg font-bold tracking-tight text-white">ClauseGuard</span>
          </div>

          <div className="relative">
            <p className="text-xs font-semibold uppercase tracking-widest text-teal-400">AI Legal Analysis</p>
            <h1 className="mt-3 text-3xl font-bold leading-snug text-white xl:text-4xl">
              Understand every<br />contract before<br />you sign.
            </h1>
            <p className="mt-4 text-sm leading-relaxed text-slate-400">
              AI-powered risk analysis that turns dense legal language into clear, actionable insights.
            </p>
            <div className="mt-8 space-y-3.5">
              {FEATURES.map((f) => (
                <div key={f.text} className="flex items-center gap-3">
                  <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/8 text-base">{f.icon}</span>
                  <span className="text-sm text-slate-300">{f.text}</span>
                </div>
              ))}
            </div>
          </div>

          <p className="relative text-xs text-slate-600">© {new Date().getFullYear()} ClauseGuard</p>
        </div>

        {/* ── Right: Form panel ───────────────────────────────────── */}
        <div className="flex flex-1 items-center justify-center bg-white px-6 py-12 sm:px-10 xl:px-16">
          <div className="w-full max-w-[380px]">
            {/* Mobile logo */}
            <div className="mb-8 flex items-center gap-2 lg:hidden">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-xs font-black text-white">CG</div>
              <span className="text-base font-bold text-slate-900">ClauseGuard</span>
            </div>

            <h2 className="text-2xl font-bold text-slate-900">Welcome back</h2>
            <p className="mt-1 text-sm text-slate-500">Sign in to your account to continue.</p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700" htmlFor="email">Email address</label>
                <input id="email" type="email" autoComplete="email" required placeholder="you@example.com"
                  value={form.email} onChange={set('email')}
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:bg-white focus:ring-4 focus:ring-teal-100" />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700" htmlFor="password">Password</label>
                <div className="relative">
                  <input id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required placeholder="••••••••"
                    value={form.password} onChange={set('password')}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-4 pr-11 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:bg-white focus:ring-4 focus:ring-teal-100" />
                  <button type="button" onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition" aria-label="Toggle password">
                    <EyeIcon open={showPassword} />
                  </button>
                </div>
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-700">
                  <span className="mt-0.5 flex-shrink-0">⚠</span><span>{error}</span>
                </div>
              )}

              <button type="submit" disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 active:scale-[0.98] disabled:opacity-60">
                {loading ? (<><svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>Signing in…</>) : 'Sign in'}
              </button>
            </form>

            <div className="my-5 flex items-center gap-3">
              <div className="h-px flex-1 bg-slate-200" />
              <span className="text-xs text-slate-400">or</span>
              <div className="h-px flex-1 bg-slate-200" />
            </div>

            <button type="button" onClick={handleDemoLogin} disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 active:scale-[0.98] disabled:opacity-60">
              🎯 Try the demo (no sign-up)
            </button>

            <p className="mt-6 text-center text-sm text-slate-500">
              Don&apos;t have an account?{' '}
              <Link to="/register" className="font-semibold text-teal-700 hover:text-teal-800 transition">Create one free</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
