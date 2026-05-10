import { useState } from 'react';
import PropTypes from 'prop-types';
import RiskBadge from './RiskBadge';
import NegotiatePanel from './NegotiatePanel';

export default function ClauseCard({ clause, expanded = false, documentId }) {
  const [showNegotiate, setShowNegotiate] = useState(false);
  const isRisky = clause.risk_level === 'critical' || clause.risk_level === 'high';

  return (
    <>
      <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="section-label">{clause.category}</p>
            <h3 className="mt-1 text-sm font-semibold text-slate-900">Clause overview</h3>
          </div>
          <RiskBadge level={clause.risk_level} />
        </div>

        <p className={`mt-4 text-sm leading-6 text-slate-700 ${expanded ? '' : 'line-clamp-3'}`}>
          {clause.clause_text || clause.text}
        </p>

        {(clause.plain_english || clause.explanation) && (
          <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
            <p className="font-semibold text-slate-900">Plain English</p>
            <p className="mt-1.5 leading-6">{clause.plain_english || clause.explanation}</p>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-3 text-xs text-slate-400">
            <span>Score <strong className="text-slate-600">{clause.risk_score}</strong></span>
            <span>·</span>
            <span>Percentile <strong className="text-slate-600">{clause.percentile}</strong></span>
            <span>·</span>
            <span>{clause.is_standard ? '✓ Standard' : '⚠ Unusual'}</span>
          </div>

          {isRisky && documentId && (
            <button
              type="button"
              onClick={() => setShowNegotiate(true)}
              className="flex items-center gap-1.5 rounded-xl border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-700 transition hover:bg-teal-100"
            >
              ⚡ Negotiate this clause
            </button>
          )}
        </div>
      </article>

      {showNegotiate && documentId && (
        <NegotiatePanel
          documentId={documentId}
          clause={clause}
          onClose={() => setShowNegotiate(false)}
        />
      )}
    </>
  );
}

ClauseCard.propTypes = {
  clause: PropTypes.shape({
    id: PropTypes.string,
    category: PropTypes.string,
    risk_level: PropTypes.string,
    clause_text: PropTypes.string,
    text: PropTypes.string,
    plain_english: PropTypes.string,
    explanation: PropTypes.string,
    risk_score: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    percentile: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    is_standard: PropTypes.bool,
  }).isRequired,
  expanded: PropTypes.bool,
  documentId: PropTypes.string,
};
