import PropTypes from 'prop-types';

export default function RiskAcknowledgmentModal({ criticalClauses, onConfirm, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
      <div className="glass-card w-full max-w-3xl p-6">
        <p className="section-label">Risk acknowledgment</p>
        <h2 className="mt-2 text-2xl font-semibold text-slate-900">Review the critical and high-risk clauses before signing</h2>
        <div className="mt-5 max-h-80 overflow-auto space-y-3">
          {criticalClauses.length === 0 ? (
            <p className="text-sm text-slate-500">No critical clauses were detected.</p>
          ) : (
            criticalClauses.map((clause) => (
              <div key={clause.id || clause.position_start} className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-slate-700">
                <p className="font-semibold text-slate-900">{clause.category} - {clause.risk_level}</p>
                <p className="mt-2 leading-6">{clause.clause_text}</p>
              </div>
            ))
          )}
        </div>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button type="button" className="secondary-button" onClick={onClose} aria-label="Cancel signing">
            Cancel
          </button>
          <button type="button" className="primary-button" onClick={onConfirm} aria-label="Confirm risk acknowledgment">
            I understand and want to sign
          </button>
        </div>
      </div>
    </div>
  );
}

RiskAcknowledgmentModal.propTypes = {
  criticalClauses: PropTypes.arrayOf(PropTypes.object).isRequired,
  onConfirm: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
};
