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

function StrengthBar({ password }) {
  const score = [/.{8,}/, /[A-Z]/, /[a-z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(password)).length;
  const labels = ['', 'Weak', 'Fair', 'Good', 'Strong', 'Very strong'];
  const colors  = ['', 'bg-red-400', 'bg-orange-400', 'bg-amber-400', 'bg-emerald-400', 'bg-teal-500'];
  const texts   = ['', 'text-red-500', 'text-orange-500', 'text-amber-600', 'text-emerald-600', 'text-teal-600'];
  if (!password) return null;
  return (
    <div className="mt-2">
      <div className="flex gap-1">
        {[1,2,3,4,5].map((i) => (
          <div key={i} className={`h-1 flex-1 rounded-full transition-all duration-300 ${i <= score ? colors[score] : 'bg-slate-200'}`} />
        ))}
      </div>
      <p className={`mt-1 text-xs font-medium ${texts[score]}`}>{labels[score]}</p>
    </div>
  );
}

const STATS = [
  { n: '41', label: 'Clause categories' },
  { n: '100', label: 'Risk score range' },
  { n: 'RAG', label: 'AI retrieval engine' },
  { n: 'Free', label: 'Powered by Groq' },
];

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '', confirm: '' });
  const [show, setShow] = useState({ password: false, confirm: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  const toggleShow = (field) => setShow((s) => ({ ...s, [field]: !s[field] }));

  function validate() {
    if (!form.email || !form.password || !form.confirm) return 'Please fill in all fields.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) return 'Enter a valid email address.';
    if (form.password.length < 8) return 'Password must be at least 8 characters.';
    if (form.password !== form.confirm) return 'Passwords do not match.';
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }
    setLoading(true); setError('');
    try {
      await authApi.register({ email: form.email, password: form.password });
      setSuccess(true);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Registration failed. Please try again.');
    } finally { setLoading(false); }
  }

  return (
    <div className="flex min-h-screen items-stretch bg-slate-900">
      <div className="mx-auto flex w-full max-w-[1400px] shadow-2xl">

        {/* ── Left: Branding ──────────────────────────────────────── */}
        <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-teal-900 p-10 lg:flex lg:w-[46%] xl:p-14">
          <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-teal-500/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-32 -right-20 h-96 w-96 rounded-full bg-teal-400/8 blur-3xl" />

          <div className="relative flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-500 text-sm font-black text-white shadow-lg">CG</div>
            <span className="text-lg font-bold tracking-tight text-white">ClauseGuard</span>
          </div>

          <div className="relative">
            <p className="text-xs font-semibold uppercase tracking-widest text-teal-400">Start for free</p>
            <h1 className="mt-3 text-3xl font-bold leading-snug text-white xl:text-4xl">
              Your AI legal<br />analyst, always<br />available.
            </h1>
            <p className="mt-4 text-sm leading-relaxed text-slate-400">
              Upload any contract and get instant risk analysis, plain-English explanations, and AI-powered Q&A.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-3">
              {STATS.map((s) => (
                <div key={s.label} className="rounded-2xl border border-white/8 bg-white/5 p-3.5">
                  <p className="text-xl font-bold text-teal-400">{s.n}</p>
                  <p className="mt-0.5 text-xs text-slate-400">{s.label}</p>
                </div>
              ))}
            </div>
          </div>

          <p className="relative text-xs text-slate-600">© {new Date().getFullYear()} ClauseGuard</p>
        </div>

        {/* ── Right: Form ─────────────────────────────────────────── */}
        <div className="flex flex-1 items-center justify-center bg-white px-6 py-12 sm:px-10 xl:px-16">
          <div className="w-full max-w-[380px]">
            <div className="mb-8 flex items-center gap-2 lg:hidden">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-xs font-black text-white">CG</div>
              <span className="text-base font-bold text-slate-900">ClauseGuard</span>
            </div>

            {success ? (
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl">✓</div>
                <h2 className="text-xl font-bold text-slate-900">Account created!</h2>
                <p className="mt-2 text-sm text-slate-500">Redirecting you to sign in…</p>
              </div>
            ) : (
              <>
                <h2 className="text-2xl font-bold text-slate-900">Create your account</h2>
                <p className="mt-1 text-sm text-slate-500">Start analysing contracts in seconds. Free forever.</p>

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
                      <input id="password" type={show.password ? 'text' : 'password'} autoComplete="new-password" required placeholder="At least 8 characters"
                        value={form.password} onChange={set('password')}
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-4 pr-11 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:bg-white focus:ring-4 focus:ring-teal-100" />
                      <button type="button" onClick={() => toggleShow('password')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition" aria-label="Toggle password">
                        <EyeIcon open={show.password} />
                      </button>
                    </div>
                    <StrengthBar password={form.password} />
                  </div>

                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-slate-700" htmlFor="confirm">Confirm password</label>
                    <div className="relative">
                      <input id="confirm" type={show.confirm ? 'text' : 'password'} autoComplete="new-password" required placeholder="Repeat your password"
                        value={form.confirm} onChange={set('confirm')}
                        className={`w-full rounded-xl border bg-slate-50 py-3 pl-4 pr-11 text-sm text-slate-900 outline-none transition focus:ring-4 ${
                          form.confirm && form.confirm !== form.password
                            ? 'border-red-300 focus:border-red-400 focus:ring-red-100'
                            : 'border-slate-200 focus:border-teal-500 focus:bg-white focus:ring-teal-100'
                        }`} />
                      <button type="button" onClick={() => toggleShow('confirm')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition" aria-label="Toggle confirm">
                        <EyeIcon open={show.confirm} />
                      </button>
                    </div>
                    {form.confirm && form.confirm !== form.password && (
                      <p className="mt-1 text-xs text-red-500">Passwords don&apos;t match</p>
                    )}
                  </div>

                  {error && (
                    <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-700">
                      <span className="mt-0.5 flex-shrink-0">⚠</span><span>{error}</span>
                    </div>
                  )}

                  <button type="submit" disabled={loading}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 active:scale-[0.98] disabled:opacity-60">
                    {loading ? (<><svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>Creating account…</>) : 'Create free account'}
                  </button>
                </form>

                <p className="mt-6 text-center text-sm text-slate-500">
                  Already have an account?{' '}
                  <Link to="/login" className="font-semibold text-teal-700 hover:text-teal-800 transition">Sign in</Link>
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
