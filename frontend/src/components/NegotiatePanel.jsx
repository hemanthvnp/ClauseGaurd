import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { negotiateApi } from '../api/documents';

const LIKELIHOOD_STYLE = {
  'Very Likely': 'bg-emerald-100 text-emerald-800 border-emerald-200',
  'Likely':      'bg-teal-100 text-teal-800 border-teal-200',
  'Possible':    'bg-amber-100 text-amber-800 border-amber-200',
  'Unlikely':    'bg-red-100 text-red-800 border-red-200',
};

export default function NegotiatePanel({ documentId, clause, onClose }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [copied, setCopied]   = useState(false);

  async function load() {
    setLoading(true); setError('');
    try {
      const res = await negotiateApi.suggest(documentId, clause.id);
      setData(res.data);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not generate advice. Please try again.');
    } finally { setLoading(false); }
  }

  async function copyAlt() {
    if (!data?.alternative_text) return;
    await navigator.clipboard.writeText(data.alternative_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const likelihood = data?.likelihood_of_acceptance || '';

  // Close on Escape key
  useEffect(() => {
    function handleKey(e) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/60 overflow-y-auto p-4 pt-8 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-full max-w-2xl rounded-3xl bg-white shadow-2xl mb-8">
        {/* Sticky close button — always visible in top-right */}
        <button
          type="button" onClick={onClose}
          className="absolute right-4 top-4 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition hover:bg-slate-200 hover:text-slate-800"
          aria-label="Close"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 p-6 pr-14">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-teal-700">Negotiation Advisor</p>
            <h3 className="mt-1 text-lg font-bold text-slate-900">{clause.category} Clause</h3>
            <p className="mt-0.5 text-xs text-slate-500 line-clamp-2">{clause.clause_text}</p>
          </div>
          {/* spacer — actual close is the absolute button */}
          <div className="w-8 flex-shrink-0" />
        </div>

        <div className="p-6">
          {!data && !loading && (
            <div className="text-center">
              <p className="text-sm text-slate-600">
                Get AI-generated negotiation advice for this clause — including a specific alternative text you can propose.
              </p>
              {error && (
                <p className="mt-3 text-sm text-red-600">{error}</p>
              )}
              <button type="button" onClick={load}
                className="mt-5 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
                ⚡ Generate negotiation advice
              </button>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-600 border-t-transparent" />
              <p className="text-sm text-slate-500">Analysing clause and generating alternatives…</p>
            </div>
          )}

          {data && (
            <div className="space-y-5">
              {/* Why risky */}
              <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
                <p className="mb-2 text-xs font-bold uppercase tracking-wider text-red-600">⚠ Why this is risky</p>
                <p className="text-sm leading-relaxed text-slate-700">{data.why_risky}</p>
              </div>

              {/* Alternative text */}
              <div className="rounded-2xl border border-teal-200 bg-teal-50 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-bold uppercase tracking-wider text-teal-700">✏ Suggested alternative language</p>
                  <button type="button" onClick={copyAlt}
                    className="flex items-center gap-1 rounded-lg border border-teal-200 bg-white px-3 py-1 text-xs font-semibold text-teal-700 transition hover:bg-teal-100">
                    {copied ? '✓ Copied' : 'Copy text'}
                  </button>
                </div>
                <p className="font-mono text-xs leading-relaxed text-slate-800 italic">"{data.alternative_text}"</p>
              </div>

              {/* Negotiation tips */}
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">💡 How to negotiate this</p>
                <p className="text-sm leading-relaxed text-slate-700">{data.negotiation_tips}</p>
              </div>

              {/* Likelihood */}
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3">
                <p className="text-sm font-medium text-slate-600">Likelihood the other party accepts:</p>
                <span className={`rounded-full border px-3 py-1 text-xs font-bold ${LIKELIHOOD_STYLE[likelihood] || 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                  {likelihood || 'Unknown'}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

NegotiatePanel.propTypes = {
  documentId: PropTypes.string.isRequired,
  clause: PropTypes.shape({
    id: PropTypes.string.isRequired,
    category: PropTypes.string,
    clause_text: PropTypes.string.isRequired,
    risk_level: PropTypes.string,
  }).isRequired,
  onClose: PropTypes.func.isRequired,
};
