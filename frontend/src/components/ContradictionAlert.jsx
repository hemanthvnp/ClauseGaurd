/**
 * ContradictionAlert
 * Displays a list of detected clause contradictions inside a document.
 * Severity badges: high (red), medium (amber), low (blue).
 */
import { useState } from 'react';

const SEVERITY_STYLES = {
  high:   'bg-red-50 border-red-400 text-red-800',
  medium: 'bg-amber-50 border-amber-400 text-amber-800',
  low:    'bg-blue-50 border-blue-400 text-blue-800',
};
const BADGE_STYLES = {
  high:   'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low:    'bg-blue-100 text-blue-700',
};
const TYPE_LABELS = {
  risk_signal:    'Risk Signal',
  keyword_antonym:'Keyword',
  semantic:       'Semantic',
  llm_confirmed:  'LLM Confirmed',
};

export function ContradictionAlert({ contradictions = [] }) {
  const [expanded, setExpanded] = useState(null);

  if (!contradictions.length) return null;

  const highCount   = contradictions.filter(c => c.severity === 'high').length;
  const mediumCount = contradictions.filter(c => c.severity === 'medium').length;

  return (
    <section className="rounded-xl border border-red-300 bg-red-50 p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-2xl">⚠️</span>
        <div>
          <h3 className="font-semibold text-red-900 text-base">
            Clause Contradictions Detected
          </h3>
          <p className="text-sm text-red-700">
            {highCount > 0 && `${highCount} high-severity`}
            {highCount > 0 && mediumCount > 0 && ', '}
            {mediumCount > 0 && `${mediumCount} medium-severity`}
            {' '}conflict{contradictions.length !== 1 ? 's' : ''} found in this document.
          </p>
        </div>
      </div>

      {/* Contradiction cards */}
      <div className="space-y-3">
        {contradictions.map((pair, idx) => {
          const isOpen = expanded === idx;
          const sev    = pair.severity || 'medium';
          return (
            <div
              key={idx}
              className={`rounded-lg border-l-4 p-3 ${SEVERITY_STYLES[sev]}`}
            >
              {/* Summary row */}
              <button
                className="w-full text-left"
                onClick={() => setExpanded(isOpen ? null : idx)}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`text-xs font-medium rounded px-2 py-0.5 ${BADGE_STYLES[sev]}`}>
                      {sev.toUpperCase()}
                    </span>
                    <span className="text-xs rounded bg-white/60 px-2 py-0.5 font-mono">
                      {TYPE_LABELS[pair.contradiction_type] || pair.contradiction_type}
                    </span>
                    <span className="text-xs font-medium">
                      {pair.clause_a_category} vs {pair.clause_b_category}
                    </span>
                  </div>
                  <span className="text-xs shrink-0 mt-0.5 text-gray-500">
                    {isOpen ? '▲ Hide' : '▼ Show'}
                  </span>
                </div>
                <p className="mt-1 text-sm">{pair.explanation}</p>
              </button>

              {/* Expanded details */}
              {isOpen && (
                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                  <ClauseSnippet
                    label={pair.clause_a_category}
                    text={pair.clause_a_text}
                  />
                  <ClauseSnippet
                    label={pair.clause_b_category}
                    text={pair.clause_b_text}
                  />
                </div>
              )}

              {/* Confidence */}
              <div className="mt-2 text-xs text-gray-500">
                Confidence: {(pair.confidence * 100).toFixed(0)}%
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ClauseSnippet({ label, text }) {
  return (
    <div className="rounded bg-white/70 p-3">
      <p className="text-xs font-semibold text-gray-600 mb-1">{label}</p>
      <p className="text-xs text-gray-700 line-clamp-4">{text}</p>
    </div>
  );
}
