import PropTypes from 'prop-types';

import RiskBadge from './RiskBadge';

export default function ComparisonDiff({ diff }) {
  const added = diff?.added || [];
  const removed = diff?.removed || [];
  const modified = diff?.modified || [];
  const riskChanged = diff?.risk_changed || [];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="glass-card p-5">
        <p className="section-label">Added</p>
        <div className="mt-4 space-y-3">
          {added.length === 0 ? <p className="text-sm text-slate-500">No added clauses detected.</p> : added.map((item) => <Row key={`${item.index}-added`} item={item} tone="high" />)}
        </div>
      </section>
      <section className="glass-card p-5">
        <p className="section-label">Removed</p>
        <div className="mt-4 space-y-3">
          {removed.length === 0 ? <p className="text-sm text-slate-500">No removed clauses detected.</p> : removed.map((item) => <Row key={`${item.index}-removed`} item={item} tone="low" />)}
        </div>
      </section>
      <section className="glass-card p-5 lg:col-span-2">
        <p className="section-label">Modified</p>
        <div className="mt-4 space-y-4">
          {modified.length === 0 ? <p className="text-sm text-slate-500">No modified clauses detected.</p> : modified.map((item) => <ModifiedRow key={`${item.index}-modified`} item={item} />)}
        </div>
      </section>
      <section className="glass-card p-5 lg:col-span-2">
        <p className="section-label">Risk changes</p>
        <div className="mt-4 flex flex-wrap gap-3">
          {riskChanged.length === 0 ? <p className="text-sm text-slate-500">No risk level changes detected.</p> : riskChanged.map((item) => <RiskChip key={`${item.index}-risk`} item={item} />)}
        </div>
      </section>
    </div>
  );
}

function Row({ item, tone }) {
  return (
    <div className={`rounded-2xl border p-4 ${tone === 'high' ? 'border-orange-200 bg-orange-50' : 'border-emerald-200 bg-emerald-50'}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Clause {item.index + 1}</span>
        {item.category ? <RiskBadge level={item.category.toLowerCase().includes('critical') ? 'critical' : 'medium'} /> : null}
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-700">{item.text}</p>
    </div>
  );
}

function ModifiedRow({ item }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Before</p>
        <p className="mt-2 text-sm leading-6 text-slate-700">{item.from}</p>
      </div>
      <div className="rounded-2xl border border-teal-200 bg-teal-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">After</p>
        <p className="mt-2 text-sm leading-6 text-slate-700">{item.to}</p>
      </div>
    </div>
  );
}

function RiskChip({ item }) {
  return (
    <div className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm">
      Clause {item.index + 1}: {item.from} → {item.to}
    </div>
  );
}

Row.propTypes = {
  item: PropTypes.shape({
    index: PropTypes.number.isRequired,
    text: PropTypes.string,
    category: PropTypes.string,
  }).isRequired,
  tone: PropTypes.oneOf(['high', 'low']).isRequired,
};

ModifiedRow.propTypes = {
  item: PropTypes.shape({
    from: PropTypes.string,
    to: PropTypes.string,
  }).isRequired,
};

RiskChip.propTypes = {
  item: PropTypes.shape({
    index: PropTypes.number.isRequired,
    from: PropTypes.string,
    to: PropTypes.string,
  }).isRequired,
};
