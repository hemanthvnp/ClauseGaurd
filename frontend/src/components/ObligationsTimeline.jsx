import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { obligationsApi } from '../api/documents';

const URGENCY_STYLE = {
  critical: { dot: 'bg-red-500',     badge: 'bg-red-100 text-red-800 border-red-200',     label: 'Critical' },
  high:     { dot: 'bg-orange-400',  badge: 'bg-orange-100 text-orange-800 border-orange-200', label: 'High' },
  medium:   { dot: 'bg-amber-400',   badge: 'bg-amber-100 text-amber-800 border-amber-200',    label: 'Medium' },
  low:      { dot: 'bg-emerald-400', badge: 'bg-emerald-100 text-emerald-800 border-emerald-200', label: 'Low' },
};

const CATEGORY_ICON = {
  'Payment':        '💰',
  'Renewal':        '🔄',
  'Notice':         '📬',
  'Non-Compete':    '🚫',
  'Confidentiality':'🔒',
  'Termination':    '⛔',
  'Delivery':       '📦',
  'Reporting':      '📊',
  'Other':          '📋',
};

const TYPE_BADGE = {
  'NDA':                  'bg-purple-100 text-purple-800',
  'Employment Agreement': 'bg-blue-100 text-blue-800',
  'SaaS Agreement':       'bg-teal-100 text-teal-800',
  'Freelance Contract':   'bg-amber-100 text-amber-800',
  'Service Agreement':    'bg-indigo-100 text-indigo-800',
  'Rental Agreement':     'bg-rose-100 text-rose-800',
};

export default function ObligationsTimeline({ documentId }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    let active = true;
    obligationsApi.get(documentId)
      .then((r) => { if (active) setData(r.data); })
      .catch(() => { if (active) setError('Could not extract obligations.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [documentId]);

  if (loading) {
    return (
      <div className="glass-card p-6">
        <p className="section-label">Obligations & Deadlines</p>
        <div className="mt-6 flex items-center gap-3 text-sm text-slate-500">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
          Extracting obligations…
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-card p-6">
        <p className="section-label">Obligations & Deadlines</p>
        <p className="mt-4 text-sm text-slate-500">{error || 'No obligations data available.'}</p>
      </div>
    );
  }

  const { contract_meta, obligations, summary } = data;
  const typeBadge = TYPE_BADGE[contract_meta.contract_type] || 'bg-slate-100 text-slate-700';

  // Sort: critical first
  const sorted = [...obligations].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return (order[a.urgency] ?? 4) - (order[b.urgency] ?? 4);
  });

  return (
    <div className="glass-card p-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="section-label">Obligations & Deadlines</p>
          <h3 className="mt-1 text-lg font-bold text-slate-900">What you&apos;re committing to</h3>
        </div>
        <span className={`flex-shrink-0 rounded-full px-3 py-1 text-xs font-bold ${typeBadge}`}>
          {contract_meta.contract_type}
        </span>
      </div>

      {/* Meta */}
      {(contract_meta.parties.length > 0 || contract_meta.effective_date || contract_meta.expiration_date) && (
        <div className="mt-4 flex flex-wrap gap-3 text-xs">
          {contract_meta.parties.map((p) => (
            <span key={p} className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 font-medium text-slate-600">👤 {p}</span>
          ))}
          {contract_meta.effective_date && (
            <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 font-medium text-slate-600">📅 Effective: {contract_meta.effective_date}</span>
          )}
          {contract_meta.expiration_date && (
            <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 font-medium text-slate-600">⏰ Expires: {contract_meta.expiration_date}</span>
          )}
        </div>
      )}

      {/* AI Summary */}
      {summary && (
        <div className="mt-4 rounded-2xl border border-teal-100 bg-teal-50 px-4 py-3 text-sm text-slate-700">
          <span className="font-semibold text-teal-700">AI Summary: </span>{summary}
        </div>
      )}

      {/* Timeline */}
      <div className="mt-5 space-y-3">
        {sorted.map((ob, i) => {
          const s = URGENCY_STYLE[ob.urgency] || URGENCY_STYLE.medium;
          const icon = CATEGORY_ICON[ob.category] || '📋';
          return (
            <div key={i} className="flex gap-4">
              {/* Timeline dot */}
              <div className="flex flex-col items-center">
                <div className={`mt-1.5 h-3 w-3 flex-shrink-0 rounded-full ${s.dot}`} />
                {i < sorted.length - 1 && <div className="mt-1 w-0.5 flex-1 bg-slate-200" />}
              </div>
              {/* Content */}
              <div className="pb-4 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-base">{icon}</span>
                  <span className="text-sm font-semibold text-slate-900">{ob.category}</span>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${s.badge}`}>{s.label}</span>
                  {ob.party && ob.party !== 'Unknown' && (
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-500">{ob.party}</span>
                  )}
                </div>
                <p className="mt-1 text-sm text-slate-600">{ob.description}</p>
                {ob.deadline && (
                  <p className="mt-1 text-xs font-medium text-slate-500">
                    ⏱ {ob.deadline}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {obligations.length === 0 && (
        <p className="mt-4 text-sm text-slate-500">No specific obligations were extracted. Review the full document carefully.</p>
      )}
    </div>
  );
}

ObligationsTimeline.propTypes = {
  documentId: PropTypes.string.isRequired,
};
