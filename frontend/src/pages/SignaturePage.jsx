import { useEffect, useMemo, useRef, useState } from 'react';

import SignaturePad from '../components/SignaturePad';
import RiskAcknowledgmentModal from '../components/RiskAcknowledgmentModal';
import RiskBadge from '../components/RiskBadge';
import { signApi, documentsApi } from '../api/documents';

export default function SignaturePage() {
  const signatureRef = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [documentId, setDocumentId] = useState(window.localStorage.getItem('clauseguard_signature_document_id') || '');
  const [clauses, setClauses] = useState([]);
  const [clausesLoading, setClausesLoading] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [signedBlobUrl, setSignedBlobUrl] = useState(null);
  const signedBlobRef = useRef(null);

  useEffect(() => {
    let active = true;
    documentsApi
      .list()
      .then((response) => {
        if (active) {
          setDocuments(response.data.filter((doc) => doc.status === 'complete'));
        }
      })
      .catch(() => {})
      .finally(() => { if (active) setDocsLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!documentId) { setClauses([]); return; }
    let active = true;
    setClausesLoading(true);
    setAcknowledged(false);
    setResult(null);
    if (signedBlobRef.current) {
      URL.revokeObjectURL(signedBlobRef.current);
      signedBlobRef.current = null;
      setSignedBlobUrl(null);
    }
    documentsApi.clauses(documentId)
      .then((res) => { if (active) setClauses(res.data); })
      .catch(() => { if (active) setClauses([]); })
      .finally(() => { if (active) setClausesLoading(false); });
    return () => { active = false; };
  }, [documentId]);

  useEffect(() => {
    return () => {
      if (signedBlobRef.current) URL.revokeObjectURL(signedBlobRef.current);
    };
  }, []);

  const criticalClauses = useMemo(
    () => clauses.filter((c) => c.risk_level === 'critical' || c.risk_level === 'high'),
    [clauses],
  );

  function handleDocumentChange(event) {
    const newId = event.target.value;
    setDocumentId(newId);
    if (newId) window.localStorage.setItem('clauseguard_signature_document_id', newId);
  }

  async function handleSign() {
    if (!documentId) { setResult({ error: 'Select a document before signing.' }); return; }
    setLoading(true);
    try {
      const signatureImage = signatureRef.current?.isEmpty() ? null : signatureRef.current?.toDataURL('image/png');
      const response = await signApi.sign(documentId, { signature_image: signatureImage });
      setResult(response.data);

      // Fetch the signed PDF as a blob immediately after signing
      const blobRes = await signApi.downloadBlob(documentId);
      const url = URL.createObjectURL(blobRes.data);
      signedBlobRef.current = url;
      setSignedBlobUrl(url);
    } catch (requestError) {
      setResult({ error: requestError?.response?.data?.detail || 'Signing failed.' });
    } finally {
      setLoading(false);
      setShowModal(false);
    }
  }

  const selectedDoc = documents.find((d) => d.id === documentId);

  return (
    <div className="page-shell py-8">
      <div className="glass-card p-8">
        <p className="section-label">Signature</p>
        <h2 className="mt-2 text-3xl font-semibold text-slate-900">Sign after acknowledging the risk report</h2>
        <p className="mt-3 text-sm text-slate-600">This page collects a signature and prepares a tamper-evident document package.</p>
        <div className="mt-6">
          <label className="text-sm font-semibold text-slate-700" htmlFor="document-id">Select document to sign</label>
          <select id="document-id" className="input-field mt-2" value={documentId} onChange={handleDocumentChange} disabled={docsLoading} aria-label="Document to sign">
            <option value="">{docsLoading ? 'Loading documents...' : 'Select a document'}</option>
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename} — {doc.overall_risk_level || 'unknown'} ({doc.overall_risk_score ?? '—'})
              </option>
            ))}
          </select>
          {selectedDoc ? (
            <div className="mt-3 flex items-center gap-3 text-sm text-slate-600">
              <span>{selectedDoc.filename}</span>
              <RiskBadge level={(selectedDoc.overall_risk_level || 'low').toLowerCase()} />
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <SignaturePad ref={signatureRef} onClear={() => signatureRef.current?.clear()} />
        <div className="glass-card p-6">
          <p className="section-label">Review</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-900">Critical & high-risk clauses</h3>
          {clausesLoading ? <p className="mt-4 text-sm text-slate-500">Loading clauses...</p> : null}
          <div className="mt-4 max-h-80 space-y-3 overflow-auto">
            {!clausesLoading && criticalClauses.length === 0 && documentId
              ? <p className="text-sm text-slate-500">No critical or high-risk clauses detected.</p>
              : null}
            {!clausesLoading && !documentId
              ? <p className="text-sm text-slate-500">Select a document above to see its risk clauses.</p>
              : null}
            {criticalClauses.map((clause) => (
              <div key={clause.id} className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-slate-700">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-slate-900">{clause.category}</p>
                  <RiskBadge level={clause.risk_level} />
                </div>
                <p className="mt-2 leading-6">{clause.clause_text}</p>
                {clause.plain_english
                  ? <p className="mt-2 text-xs text-slate-500 italic">{clause.plain_english}</p>
                  : null}
              </div>
            ))}
          </div>
          <label className="mt-5 flex items-start gap-3 text-sm text-slate-700">
            <input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} disabled={!documentId || (criticalClauses.length === 0 && clauses.length === 0)} aria-label="Acknowledge critical clauses" />
            <span>I have reviewed the critical and high-risk clauses before signing.</span>
          </label>
          <button className="primary-button mt-6 w-full" type="button" disabled={!acknowledged || loading || !documentId} onClick={() => setShowModal(true)} aria-label="Open risk acknowledgment modal">
            {loading ? 'Signing...' : 'Continue to sign'}
          </button>
          {result ? (
            <div className="mt-4 space-y-3">
              {result.error ? (
                <p className="text-sm text-red-600">{result.error}</p>
              ) : (
                <>
                  <div className="rounded-2xl bg-emerald-50 border border-emerald-200 p-4">
                    <p className="text-sm font-semibold text-emerald-800">Document signed successfully</p>
                    <p className="mt-1 text-xs text-slate-600">Hash: {result.document_hash}</p>
                    <p className="text-xs text-slate-600">Signed at: {new Date(result.signed_at).toLocaleString()}</p>
                  </div>
                  {signedBlobUrl ? (
                    <a className="primary-button w-full text-center" href={signedBlobUrl} download={`signed-${documentId}.pdf`} aria-label="Download signed document">
                      Download signed PDF
                    </a>
                  ) : (
                    <p className="text-xs text-slate-500">Preparing download…</p>
                  )}
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>

      {showModal ? <RiskAcknowledgmentModal criticalClauses={criticalClauses} onConfirm={handleSign} onClose={() => setShowModal(false)} /> : null}
    </div>
  );
}
