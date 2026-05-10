import { useEffect, useState } from 'react';

import ComparisonDiff from '../components/ComparisonDiff';
import RiskBadge from '../components/RiskBadge';
import { compareApi, documentsApi } from '../api/documents';

export default function ComparisonPage() {
  const [formState, setFormState] = useState({ document_v1_id: '', document_v2_id: '' });
  const [documents, setDocuments] = useState([]);
  const [diff, setDiff] = useState(null);
  const [loading, setLoading] = useState(false);
  const [docsLoading, setDocsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    documentsApi
      .list()
      .then((response) => {
        if (active) {
          const completed = response.data.filter((doc) => doc.status === 'complete');
          setDocuments(completed);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (active) setDocsLoading(false);
      });
    return () => { active = false; };
  }, []);

  async function handleCompare(event) {
    event.preventDefault();
    if (!formState.document_v1_id || !formState.document_v2_id) {
      setError('Select two documents to compare.');
      return;
    }
    if (formState.document_v1_id === formState.document_v2_id) {
      setError('Select two different documents.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await compareApi.create(formState);
      setDiff(response.data.diff_result);
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Comparison failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-shell py-8">
      <div className="glass-card p-8">
        <p className="section-label">Comparison</p>
        <h2 className="mt-2 text-3xl font-semibold text-slate-900">Clause-level diff</h2>
        <p className="mt-2 text-sm text-slate-600">Select two analyzed documents to see what changed between versions.</p>
        <form className="mt-6 grid gap-4 md:grid-cols-2" onSubmit={handleCompare}>
          <div>
            <label className="mb-2 block text-sm font-semibold text-slate-700" htmlFor="compare-v1">Document V1</label>
            <select
              id="compare-v1"
              className="input-field"
              value={formState.document_v1_id}
              onChange={(event) => setFormState((current) => ({ ...current, document_v1_id: event.target.value }))}
              aria-label="Document version one"
              disabled={docsLoading}
            >
              <option value="">{docsLoading ? 'Loading documents...' : 'Select first document'}</option>
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename} — {doc.overall_risk_level || 'unknown'}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold text-slate-700" htmlFor="compare-v2">Document V2</label>
            <select
              id="compare-v2"
              className="input-field"
              value={formState.document_v2_id}
              onChange={(event) => setFormState((current) => ({ ...current, document_v2_id: event.target.value }))}
              aria-label="Document version two"
              disabled={docsLoading}
            >
              <option value="">{docsLoading ? 'Loading documents...' : 'Select second document'}</option>
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename} — {doc.overall_risk_level || 'unknown'}
                </option>
              ))}
            </select>
          </div>
          <button className="primary-button md:col-span-2" type="submit" disabled={loading || docsLoading} aria-label="Compare documents">
            {loading ? 'Comparing...' : 'Compare versions'}
          </button>
        </form>
        {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
        {documents.length === 0 && !docsLoading ? (
          <p className="mt-4 text-sm text-slate-500">You need at least two analyzed documents to compare. Upload documents first.</p>
        ) : null}
      </div>
      {diff ? <div className="mt-8"><ComparisonDiff diff={diff} /></div> : null}
    </div>
  );
}
