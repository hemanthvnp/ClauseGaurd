import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { documentsApi } from '../api/documents';

const MAX_MB = 50;

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile]         = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError]       = useState('');

  function validateFile(f) {
    if (!f) return 'No file selected.';
    const ext = f.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) return 'Only PDF and DOCX files are supported.';
    if (f.size > MAX_MB * 1024 * 1024) return `File exceeds the ${MAX_MB} MB limit.`;
    return null;
  }

  function pickFile(f) {
    const err = validateFile(f);
    if (err) { setError(err); setFile(null); return; }
    setError('');
    setFile(f);
  }

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  }, []);

  const onDragOver = useCallback((e) => { e.preventDefault(); setDragging(true); }, []);
  const onDragLeave = useCallback(() => setDragging(false), []);

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) { setError('Please select a file first.'); return; }
    setLoading(true);
    setError('');
    setProgress(10);
    try {
      const simulateProgress = setInterval(() => {
        setProgress((p) => (p < 85 ? p + Math.random() * 15 : p));
      }, 300);
      const res = await documentsApi.upload(file);
      clearInterval(simulateProgress);
      setProgress(100);
      setTimeout(() => navigate(`/analysis/${res.data.document.id}`), 400);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Upload failed. Please try again.');
      setLoading(false);
      setProgress(0);
    }
  }

  const fileExt = file?.name.split('.').pop()?.toLowerCase();

  return (
    <div className="page-shell py-8">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <p className="section-label">Upload</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Analyze a contract</h1>
        <p className="mt-2 text-sm text-slate-500">
          Upload a PDF or DOCX and ClauseGuard will extract every clause, score the risk, and give you a plain-English breakdown.
        </p>

        {/* Drop zone */}
        <div
          onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}
          className={`mt-8 cursor-pointer rounded-3xl border-2 border-dashed transition-all ${
            dragging
              ? 'border-teal-400 bg-teal-50 scale-[1.01]'
              : file
              ? 'border-teal-300 bg-teal-50/50'
              : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
          }`}
        >
          <label className="flex min-h-56 cursor-pointer flex-col items-center justify-center p-8 text-center">
            <input
              type="file" accept=".pdf,.docx" className="sr-only"
              onChange={(e) => { if (e.target.files?.[0]) pickFile(e.target.files[0]); }}
            />
            {file ? (
              <>
                <div className={`flex h-16 w-16 items-center justify-center rounded-2xl text-3xl ${fileExt === 'pdf' ? 'bg-red-100' : 'bg-blue-100'}`}>
                  {fileExt === 'pdf' ? '📄' : '📝'}
                </div>
                <p className="mt-4 font-semibold text-slate-900">{file.name}</p>
                <p className="mt-1 text-sm text-slate-500">{formatBytes(file.size)} · {fileExt?.toUpperCase()}</p>
                <p className="mt-3 text-xs text-teal-600 font-medium">Click or drop to replace</p>
              </>
            ) : (
              <>
                <div className={`flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 transition-transform ${dragging ? 'scale-110' : ''}`}>
                  <svg className="h-8 w-8 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                  </svg>
                </div>
                <p className="mt-4 text-base font-semibold text-slate-700">
                  {dragging ? 'Drop it here' : 'Drop your contract here'}
                </p>
                <p className="mt-1 text-sm text-slate-400">or click to browse files</p>
                <div className="mt-4 flex gap-2">
                  {['PDF', 'DOCX'].map((fmt) => (
                    <span key={fmt} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-500">{fmt}</span>
                  ))}
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-500">Up to {MAX_MB} MB</span>
                </div>
              </>
            )}
          </label>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span className="mt-0.5 flex-shrink-0">⚠</span><span>{error}</span>
          </div>
        )}

        {/* Progress bar */}
        {loading && (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>Uploading…</span><span>{Math.round(progress)}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-teal-500 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Submit */}
        <button
          type="button" onClick={handleUpload}
          disabled={!file || loading}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 py-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? (
            <>
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              Uploading and processing…
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              Analyze contract
            </>
          )}
        </button>

        {/* What happens next */}
        <div className="mt-8 rounded-2xl border border-slate-100 bg-slate-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">What happens next</p>
          <div className="mt-4 space-y-3">
            {[
              ['📤', 'Your file is uploaded securely'],
              ['🔍', 'NLP extracts and classifies every clause'],
              ['⚖️', 'Each clause receives a risk score (0–100)'],
              ['💬', 'AI generates plain-English explanations'],
            ].map(([icon, text]) => (
              <div key={text} className="flex items-center gap-3 text-sm text-slate-600">
                <span className="text-base">{icon}</span>{text}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
