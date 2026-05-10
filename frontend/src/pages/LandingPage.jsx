import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { demoApi } from '../api/documents';

const SAMPLE_CLAUSES = [
  { title: 'Arbitration',    level: 'critical', color: 'text-red-700 bg-red-50 border-red-200',      desc: 'Mandatory arbitration removes your right to sue in court.' },
  { title: 'Auto-Renewal',   level: 'high',     color: 'text-orange-700 bg-orange-50 border-orange-200', desc: 'The term renews automatically unless you cancel 30 days before.' },
  { title: 'Confidentiality',level: 'low',      color: 'text-emerald-700 bg-emerald-50 border-emerald-200', desc: 'A standard mutual promise to keep information private.' },
];

const FEATURES = [
  { icon: '📄', title: 'Upload & parse',        desc: 'PDF and DOCX intake with clause-preserving NLP extraction.' },
  { icon: '⚖️', title: 'Classify & score',      desc: 'CUAD-style clause labels backed by a weighted risk engine.' },
  { icon: '💬', title: 'AI Q&A',                desc: 'Ask anything — Groq Llama 3.3 70B answers using HyDE retrieval.' },
  { icon: '✍️', title: 'Compare & sign',        desc: 'Semantic diffing, risk acknowledgment, and signed PDF export.' },
];

export default function LandingPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function startDemo() {
    setLoading(true); setError('');
    try {
      const res = await demoApi.bootstrap();
      window.localStorage.setItem('clauseguard_access_token', res.data.access_token);
      window.localStorage.setItem('clauseguard_refresh_token', res.data.refresh_token);
      if (res.data.documents?.[0]?.id)
        window.localStorage.setItem('clauseguard_signature_document_id', res.data.documents[0].id);
      navigate('/dashboard');
    } catch {
      setError('Could not start demo. Please try again.');
    } finally { setLoading(false); }
  }

  return (
    <div className="min-h-screen">

      {/* ── Hero (dark) ─────────────────────────────────────────── */}
      <div className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-900 to-teal-950">
        {/* Background blobs */}
        <div className="pointer-events-none absolute top-0 left-0 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/3 rounded-full bg-teal-500/10 blur-3xl" />
        <div className="pointer-events-none absolute top-0 right-0 h-[500px] w-[500px] translate-x-1/3 -translate-y-1/3 rounded-full bg-amber-500/8 blur-3xl" />

        {/* Nav */}
        <nav className="relative mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500 text-xs font-black text-white">CG</div>
            <span className="text-base font-bold text-white">ClauseGuard</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login"
              className="rounded-lg px-4 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/10 hover:text-white">
              Sign in
            </Link>
            <Link to="/register"
              className="rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-400">
              Get started free
            </Link>
          </div>
        </nav>

        {/* Hero content */}
        <div className="relative mx-auto max-w-7xl px-4 pb-24 pt-16 sm:px-6 lg:grid lg:grid-cols-[1fr_420px] lg:items-center lg:gap-16 lg:px-8 xl:grid-cols-[1fr_480px] xl:pt-20">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55 }}>
            <span className="inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-3 py-1 text-xs font-semibold text-teal-400">
              AI Legal Risk Analyzer
            </span>
            <h1 className="mt-5 text-5xl font-bold leading-tight tracking-tight text-white sm:text-6xl xl:text-7xl">
              Read every<br />clause before<br />you sign.
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-slate-400">
              ClauseGuard extracts and classifies every clause in your contract, scores the risk, explains it in plain English, and answers your questions in real time.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button" onClick={() => void startDemo()} disabled={loading}
                className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-bold text-slate-900 shadow-lg transition hover:bg-slate-100 active:scale-[0.97] disabled:opacity-70">
                {loading ? (
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
                ) : '🎯'} {loading ? 'Loading demo…' : 'Try the demo — no sign-up'}
              </button>
              <Link to="/register"
                className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/8 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/15">
                Get started free →
              </Link>
            </div>
            {error && <p className="mt-4 text-sm text-red-300">{error}</p>}

            {/* Social proof */}
            <div className="mt-10 flex flex-wrap items-center gap-6 text-xs text-slate-500">
              {['PostgreSQL', 'FastAPI', 'React', 'Groq Llama 3.3 70B', 'Celery'].map((t) => (
                <span key={t} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-slate-400">{t}</span>
              ))}
            </div>
          </motion.div>

          {/* Sample report card */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.65, delay: 0.15 }}
            className="mt-12 lg:mt-0">
            <div className="rounded-3xl border border-white/10 bg-white/5 p-1 shadow-2xl backdrop-blur">
              <div className="rounded-[20px] bg-white p-5">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-teal-700">ClauseGuard</p>
                    <p className="text-sm font-bold text-slate-900">Risk Analysis Report</p>
                  </div>
                  <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">CRITICAL</span>
                </div>
                <div className="mt-4 space-y-3">
                  {SAMPLE_CLAUSES.map((c) => (
                    <div key={c.title} className={`rounded-2xl border p-3.5 ${c.color}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold">{c.title}</p>
                        <span className="rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide">{c.level}</span>
                      </div>
                      <p className="mt-1.5 text-xs leading-relaxed opacity-80">{c.desc}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-4 rounded-2xl bg-slate-900 p-3.5 text-xs text-slate-300">
                  <span className="text-teal-400 font-semibold">AI: </span>
                  Review the arbitration clause carefully — it removes your right to a jury trial for any disputes.
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* ── Features (light) ─────────────────────────────────────── */}
      <div id="features" className="bg-slate-50 py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-widest text-teal-700">What it does</p>
            <h2 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">Everything you need to review a contract</h2>
          </div>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
            {FEATURES.map(({ icon, title, desc }) => (
              <div key={title} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md">
                <span className="text-3xl">{icon}</span>
                <p className="mt-4 text-base font-bold text-slate-900">{title}</p>
                <p className="mt-2 text-sm leading-relaxed text-slate-500">{desc}</p>
              </div>
            ))}
          </div>

          {/* CTA strip */}
          <div className="mt-16 rounded-3xl bg-slate-900 px-8 py-10 text-center">
            <h3 className="text-2xl font-bold text-white">Ready to review your contract?</h3>
            <p className="mt-2 text-sm text-slate-400">Upload any PDF or DOCX and get a full risk analysis in under 30 seconds.</p>
            <div className="mt-6 flex justify-center gap-4">
              <button type="button" onClick={() => void startDemo()} disabled={loading}
                className="rounded-xl bg-teal-500 px-6 py-3 text-sm font-bold text-white transition hover:bg-teal-400 active:scale-[0.97]">
                Try the demo
              </button>
              <Link to="/register" className="rounded-xl border border-white/20 bg-white/10 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/20">
                Create account
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
