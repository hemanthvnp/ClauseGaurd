import PropTypes from 'prop-types';

const levelStyles = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  medium: 'bg-amber-100 text-amber-800 border-amber-200',
  low: 'bg-emerald-100 text-emerald-800 border-emerald-200',
};

export default function RiskBadge({ level }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${levelStyles[level] || levelStyles.low}`}>
      {level}
    </span>
  );
}

RiskBadge.propTypes = {
  level: PropTypes.oneOf(['critical', 'high', 'medium', 'low']).isRequired,
};
