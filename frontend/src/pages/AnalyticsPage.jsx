/**
 * Analytics Dashboard
 * Displays portfolio-level risk intelligence across all of a user's documents.
 *
 * Sections:
 *  - KPI cards (total docs, avg risk, critical clause count)
 *  - Risk distribution donut chart
 *  - Category heatmap (bar chart — top 10 categories)
 *  - Risk trend line chart (last 30 days)
 */
import { useEffect, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, Legend,
  Line, LineChart, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import { apiClient } from '../api/client';

const RISK_COLORS = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#22c55e',
};

const RISK_ORDER = ['critical', 'high', 'medium', 'low'];

// ── API helpers ──────────────────────────────────────────────────────────────

async function fetchSummary()      { return apiClient.get('/analytics/summary').then(r => r.data); }
async function fetchDistribution() { return apiClient.get('/analytics/risk-distribution').then(r => r.data); }
async function fetchHeatmap()      { return apiClient.get('/analytics/category-heatmap').then(r => r.data); }
async function fetchTrends()       { return apiClient.get('/analytics/trends?days=30').then(r => r.data); }

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [summary,      setSummary]      = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [heatmap,      setHeatmap]      = useState([]);
  const [trends,       setTrends]       = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchSummary(), fetchDistribution(), fetchHeatmap(), fetchTrends()])
      .then(([s, d, h, t]) => {
        setSummary(s);
        setDistribution(d);
        setHeatmap(h.slice(0, 10));
        setTrends(t);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingScreen />;
  if (error)   return <ErrorScreen message={error} />;
  if (!summary || summary.total_documents === 0) return <EmptyState />;

  const pieData = distribution?.distribution?.map(d => ({
    name:  d.level,
    value: d.count,
    pct:   d.percentage,
  })) ?? [];

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">Portfolio Analytics</h1>
        <p className="text-sm text-gray-500 mt-1">
          Risk intelligence across {summary.total_documents} analyzed document
          {summary.total_documents !== 1 ? 's' : ''}
        </p>
      </header>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Documents" value={summary.total_documents} color="blue" />
        <KpiCard label="Total Clauses" value={summary.total_clauses} color="indigo" />
        <KpiCard
          label="Avg Risk Score"
          value={`${summary.avg_risk_score}/100`}
          color={summary.avg_risk_score >= 65 ? 'red' : summary.avg_risk_score >= 35 ? 'amber' : 'green'}
        />
        <KpiCard
          label="Critical Clauses"
          value={summary.risk_breakdown?.critical ?? 0}
          color="red"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Donut chart */}
        <ChartCard title="Risk Distribution" subtitle="Clauses by risk level">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={70}
                outerRadius={110}
                paddingAngle={3}
                dataKey="value"
                label={({ name, pct }) => `${name} ${pct}%`}
                labelLine={false}
              >
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={RISK_COLORS[entry.name] ?? '#94a3b8'} />
                ))}
              </Pie>
              <Tooltip formatter={(v, n) => [`${v} clauses`, n]} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Category heatmap */}
        <ChartCard title="Top Clause Categories" subtitle="By occurrence count">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={heatmap} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="category"
                tick={{ fontSize: 10 }}
                width={130}
              />
              <Tooltip
                formatter={(v, n) => [v, n === 'count' ? 'Occurrences' : n]}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {heatmap.map((entry, i) => (
                  <Cell key={i} fill={RISK_COLORS[entry.max_risk_level] ?? '#6366f1'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Trend chart */}
      {trends.length > 0 && (
        <ChartCard
          title="Risk Score Trend"
          subtitle="Average document risk score over the last 30 days"
        >
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="avg_risk_score"
                name="Avg Risk Score"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {/* Highest risk document */}
      {summary.highest_risk_document && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-semibold text-red-800 mb-1">Highest Risk Document</p>
          <p className="text-sm text-red-700">
            <span className="font-medium">{summary.highest_risk_document.filename}</span>
            {' — '}
            <RiskBadge level={summary.highest_risk_document.risk_level} />
            {' '}{summary.highest_risk_document.risk_score}/100
          </p>
        </div>
      )}

      {/* Top categories table */}
      {summary.top_categories?.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-gray-800 mb-3">Most Frequent Clause Types</h2>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
                <tr>
                  <th className="px-4 py-3 text-left">Category</th>
                  <th className="px-4 py-3 text-right">Occurrences</th>
                  <th className="px-4 py-3 text-right">Avg Risk</th>
                  <th className="px-4 py-3 text-center">Max Level</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {heatmap.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-800">{row.category}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.count}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.avg_score}</td>
                    <td className="px-4 py-3 text-center">
                      <RiskBadge level={row.max_risk_level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiCard({ label, value, color }) {
  const bg = {
    blue:   'bg-blue-50 border-blue-200 text-blue-700',
    indigo: 'bg-indigo-50 border-indigo-200 text-indigo-700',
    red:    'bg-red-50 border-red-200 text-red-700',
    amber:  'bg-amber-50 border-amber-200 text-amber-700',
    green:  'bg-green-50 border-green-200 text-green-700',
  }[color] ?? 'bg-gray-50 border-gray-200 text-gray-700';

  return (
    <div className={`rounded-xl border p-4 ${bg}`}>
      <p className="text-xs font-medium opacity-70 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}

function ChartCard({ title, subtitle, children }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="font-semibold text-gray-800">{title}</p>
      {subtitle && <p className="text-xs text-gray-500 mb-3">{subtitle}</p>}
      {children}
    </div>
  );
}

function RiskBadge({ level }) {
  const styles = {
    critical: 'bg-red-100 text-red-700',
    high:     'bg-orange-100 text-orange-700',
    medium:   'bg-yellow-100 text-yellow-700',
    low:      'bg-green-100 text-green-700',
  };
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${styles[level] ?? 'bg-gray-100 text-gray-700'}`}>
      {level}
    </span>
  );
}

function LoadingScreen() {
  return (
    <div className="flex flex-col items-center justify-center min-h-64 gap-3 text-gray-500">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      <p className="text-sm">Loading analytics...</p>
    </div>
  );
}

function ErrorScreen({ message }) {
  return (
    <div className="flex items-center justify-center min-h-64">
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center max-w-sm">
        <p className="text-red-700 font-medium">Failed to load analytics</p>
        <p className="text-sm text-red-600 mt-1">{message}</p>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-64 gap-3 text-gray-500">
      <span className="text-4xl">📄</span>
      <p className="font-medium">No documents analyzed yet</p>
      <p className="text-sm">Upload a contract to see your risk portfolio.</p>
    </div>
  );
}
