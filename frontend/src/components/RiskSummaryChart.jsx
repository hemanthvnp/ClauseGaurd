import PropTypes from 'prop-types';
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

const COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#f59e0b',
  low: '#10b981',
};

export default function RiskSummaryChart({ clauses, selectedLevel, onSelectLevel }) {
  const data = [
    { name: 'Critical', key: 'critical', value: clauses.filter((c) => c.risk_level === 'critical').length, fill: COLORS.critical },
    { name: 'High',     key: 'high',     value: clauses.filter((c) => c.risk_level === 'high').length,     fill: COLORS.high },
    { name: 'Medium',   key: 'medium',   value: clauses.filter((c) => c.risk_level === 'medium').length,   fill: COLORS.medium },
    { name: 'Low',      key: 'low',      value: clauses.filter((c) => c.risk_level === 'low').length,      fill: COLORS.low },
  ].filter((entry) => entry.value > 0);

  function handleClick(entry) {
    if (!onSelectLevel) return;
    onSelectLevel(selectedLevel === entry.key ? null : entry.key);
  }

  return (
    <div className="glass-card p-5">
      <div className="mb-2">
        <p className="section-label">Risk distribution</p>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">Clause risk summary</h3>
        <p className="mt-1 text-xs text-slate-400">Click a slice to filter clauses</p>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={65}
              outerRadius={92}
              paddingAngle={3}
              onClick={handleClick}
              style={{ cursor: 'pointer' }}
            >
              {data.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={entry.fill}
                  opacity={selectedLevel && selectedLevel !== entry.key ? 0.3 : 1}
                  stroke={selectedLevel === entry.key ? '#1e293b' : 'none'}
                  strokeWidth={selectedLevel === entry.key ? 2 : 0}
                />
              ))}
            </Pie>
            <Tooltip formatter={(value, name) => [`${value} clauses`, name]} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
      {selectedLevel && (
        <button
          type="button"
          onClick={() => onSelectLevel(null)}
          className="mt-2 w-full rounded-full border border-slate-200 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-50 transition"
        >
          Clear filter — show critical &amp; high
        </button>
      )}
    </div>
  );
}

RiskSummaryChart.propTypes = {
  clauses: PropTypes.arrayOf(PropTypes.shape({ risk_level: PropTypes.string })).isRequired,
  selectedLevel: PropTypes.string,
  onSelectLevel: PropTypes.func,
};
