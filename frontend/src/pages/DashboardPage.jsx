import { useState } from 'react';
import { Link } from 'react-router-dom';
import { documentsApi } from '../api/documents';
import { useDocuments } from '../hooks/useDocuments';

const RISK_BORDER = { critical: 'border-l-red-500', high: 'border-l-orange-400', medium: 'border-l-amber-400', low: 'border-l-emerald-400' };
const RISK_BG    = { critical: 'bg-red-50',       high: 'bg-orange-50',       medium: 'bg-amber-50',       low: 'bg-emerald-50'       };
const RISK_TEXT  = { critical: 'text-red-700',    high: 'text-orange-700',    medium: 'text-amber-700',    low: 'text-emerald-700'    };
const RISK_DOT   = { critical: 'bg-red-500',      high: 'bg-orange-400',      medium: 'bg-amber-400',      low: 'bg-emerald-400'      };

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function StatCard({ label, value, sub, color = 'text-slate-900' }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className={`mt-1 text-3xl font-bold ${color}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const { documents, loading, error, refetch } = useDocuments(true);
  const [deleting, setDeleting] = useState(null);

  const complete  = documents.filter((d) => d.status === 'complete');
  const critical  = complete.filter((d) => d.overall_risk_level === 'critical').length;
  const high      = complete.filter((d) => d.overall_risk_level === 'high').length;

  async function handleDelete(e, id) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm('Delete this document and all its clauses? This cannot be undone.')) return;
    setDeleting(id);
    try { await documentsApi.remove(id); await refetch(true); } catch (_) {}
    setDeleting(null);
  }

  return (
    <div className="page-shell py-8">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="section-label">Overview</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Your Documents</h1>
          <p className="mt-1 text-sm text-slate-500">Upload and analyze legal contracts to understand the risk before you sign.</p>
        </div>
        <Link to="/upload"
          className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 active:scale-[0.98]">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          Upload contract
        </Link>
      </div>

      {/* Stats */}
      {!loading && documents.length > 0 && (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Total"     value={documents.length} sub="documents uploaded" />
          <StatCard label="Analysed"  value={complete.length}  sub="fully processed" color="text-teal-700" />
          <StatCard label="Critical"  value={critical}         sub="high-risk docs" color="text-red-600" />
          <StatCard label="High risk" value={high}             sub="need review" color="text-orange-600" />
        </div>
      )}

      {/* Error / loading */}
      {loading && (
        <div className="mt-10 flex items-center gap-3 text-sm text-slate-500">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
          Loading documents…
        </div>
      )}
      {error && <p className="mt-6 text-sm text-red-600">{error}</p>}

      {/* Empty state */}
      {!loading && !error && documents.length === 0 && (
        <div className="mt-12 flex flex-col items-center rounded-3xl border-2 border-dashed border-slate-200 py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-3xl">📄</div>
          <h3 className="mt-4 text-lg font-semibold text-slate-900">No documents yet</h3>
          <p className="mt-2 max-w-xs text-sm text-slate-500">Upload your first contract to get an instant AI-powered risk analysis.</p>
          <Link to="/upload"
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
            Upload your first contract
          </Link>
        </div>
      )}

      {/* Document list */}
      {!loading && documents.length > 0 && (
        <div className="mt-6 space-y-3">
          {documents.map((doc) => {
            const level = (doc.overall_risk_level || 'low').toLowerCase();
            const isProcessing = doc.status === 'processing';
            return (
              <div key={doc.id} className="group relative">
                <Link
                  to={`/analysis/${doc.id}`}
                  className={`flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-l-4 border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${RISK_BORDER[level] || 'border-l-slate-300'}`}
                >
                  {/* Left */}
                  <div className="flex min-w-0 items-center gap-4">
                    <div className={`hidden h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-lg sm:flex ${RISK_BG[level] || 'bg-slate-50'}`}>
                      {doc.file_type === 'pdf' ? '📄' : '📝'}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-slate-900">{doc.filename}</p>
                      <p className="mt-0.5 text-xs text-slate-400">
                        {doc.file_type.toUpperCase()} · {formatDate(doc.created_at)}
                        {isProcessing && (
                          <span className="ml-2 inline-flex items-center gap-1 font-medium text-amber-600">
                            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
                            Analysing…
                          </span>
                        )}
                        {doc.status === 'failed' && <span className="ml-2 font-medium text-red-500">Failed</span>}
                      </p>
                    </div>
                  </div>

                  {/* Right */}
                  {doc.status === 'complete' && (
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="text-xs text-slate-400">Risk score</p>
                        <p className="text-lg font-bold text-slate-900">{doc.overall_risk_score ?? '—'}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ${RISK_BG[level]} ${RISK_TEXT[level]}`}>
                        <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full ${RISK_DOT[level]}`} />
                        {level}
                      </span>
                    </div>
                  )}
                </Link>

                {/* Delete button */}
                <button
                  type="button"
                  onClick={(e) => handleDelete(e, doc.id)}
                  disabled={deleting === doc.id}
                  aria-label={`Delete ${doc.filename}`}
                  className="absolute right-4 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-slate-300 opacity-0 transition group-hover:opacity-100 hover:bg-red-50 hover:text-red-500"
                >
                  {deleting === doc.id
                    ? <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
                    : <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
