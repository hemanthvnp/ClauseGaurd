import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Link, useParams } from 'react-router-dom';

import { documentsApi } from '../api/documents';
import ChatPanel from '../components/ChatPanel';
import ClauseCard from '../components/ClauseCard';
import DocumentViewer from '../components/DocumentViewer';
import ObligationsTimeline from '../components/ObligationsTimeline';
import RiskSummaryChart from '../components/RiskSummaryChart';

const POLL_INTERVAL_MS = 2500;

export default function AnalysisPage() {
  const { id } = useParams();
  const [documentState, setDocumentState] = useState(null);
  const [clauses, setClauses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [blobUrl, setBlobUrl] = useState(null);
  const blobUrlRef = useRef(null);
  const timerRef = useRef(null);
  const activeRef = useRef(true);

  const loadClauses = useCallback(async () => {
    try {
      const res = await documentsApi.clauses(id);
      if (activeRef.current) setClauses(res.data);
    } catch (_) {}
  }, [id]);

  const loadBlob = useCallback(async () => {
    try {
      const res = await documentsApi.downloadBlob(id);
      if (!activeRef.current) return;
      if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
      const url = URL.createObjectURL(res.data);
      blobUrlRef.current = url;
      setBlobUrl(url);
    } catch (_) {}
  }, [id]);

  const loadDocument = useCallback(async (silent = false) => {
    try {
      const res = await documentsApi.get(id);
      if (!activeRef.current) return;
      const doc = res.data;
      setDocumentState(doc);

      if (doc.status === 'complete') {
        await Promise.all([loadClauses(), loadBlob()]);
      }
      return doc.status;
    } catch (requestError) {
      if (activeRef.current && !silent) {
        setError(requestError?.response?.data?.detail || 'Unable to load analysis.');
      }
      return 'failed';
    }
  }, [id, loadClauses, loadBlob]);

  useEffect(() => {
    if (id) {
      window.localStorage.setItem('clauseguard_signature_document_id', id);
    }
  }, [id]);

  useEffect(() => {
    activeRef.current = true;

    async function tick() {
      const status = await loadDocument(timerRef.current !== null);
      if (!activeRef.current) return;
      if (status === 'processing') {
        timerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
      } else {
        timerRef.current = null;
        setLoading(false);
      }
    }

    void tick();

    return () => {
      activeRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [id, loadDocument]);

  const [selectedLevel, setSelectedLevel] = useState(null);

  const fileType = useMemo(() => documentState?.file_type || 'pdf', [documentState]);
  const isProcessing = documentState?.status === 'processing';

  // Default: show only critical + high. When a pie slice is selected, show that level only.
  const visibleClauses = useMemo(() => {
    if (selectedLevel) return clauses.filter((c) => c.risk_level === selectedLevel);
    return clauses.filter((c) => c.risk_level === 'critical' || c.risk_level === 'high');
  }, [clauses, selectedLevel]);

  const filterLabel = selectedLevel
    ? `Showing: ${selectedLevel}`
    : 'Showing: critical & high';

  return (
    <div className="page-shell py-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="section-label">Analysis</p>
          <h2 className="mt-2 text-3xl font-semibold text-slate-900">Clause review</h2>
          <p className="mt-2 text-sm text-slate-600">{documentState?.filename || 'Document analysis'}</p>
        </div>
        <Link className="secondary-button" to="/signature">
          Proceed to signature
        </Link>
      </div>

      {loading && isProcessing ? (
        <div className="mt-10 flex flex-col items-center gap-3 text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-600 border-t-transparent" />
          <p className="text-sm font-medium text-slate-600">Processing document — checking every 2.5 s…</p>
        </div>
      ) : null}

      {loading && !isProcessing ? <p className="mt-6 text-sm text-slate-600">Loading analysis...</p> : null}
      {error ? <p className="mt-6 text-sm text-red-600">{error}</p> : null}
      {!loading && documentState?.status === 'failed' ? (
        <p className="mt-6 text-sm text-red-600">Processing failed. Please delete and re-upload the document.</p>
      ) : null}

      {!loading && !error && documentState?.status === 'complete' ? (
        <div className="mt-8 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <DocumentViewer fileUrl={blobUrl} fileType={fileType} text={documentState?.raw_text || ''} />
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">{filterLabel} · {visibleClauses.length} clause{visibleClauses.length !== 1 ? 's' : ''}</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {visibleClauses.length === 0
                ? <p className="col-span-2 text-sm text-slate-500">No clauses at this risk level.</p>
                : visibleClauses.map((clause) => <ClauseCard key={clause.id} clause={clause} expanded documentId={id} />)}
            </div>
          </div>
          <div className="space-y-6">
            <RiskSummaryChart clauses={clauses} selectedLevel={selectedLevel} onSelectLevel={setSelectedLevel} />
            <ObligationsTimeline documentId={id} />
            <ChatPanel documentId={id} />
            <div className="glass-card p-5">
              <p className="section-label">Document status</p>
              <div className="mt-4 space-y-2 text-sm text-slate-600">
                <p>Status: {documentState?.status}</p>
                <p>Risk score: {documentState?.overall_risk_score ?? 'Pending'}</p>
                <p>Risk level: {documentState?.overall_risk_level ?? 'Pending'}</p>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
