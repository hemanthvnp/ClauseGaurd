import { useEffect, useRef } from 'react';

import PropTypes from 'prop-types';
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = workerUrl;

export default function DocumentViewer({ fileUrl, fileType, text }) {
  const canvasRef = useRef(null);
  const canRenderPdf = typeof fileUrl === 'string' && /^(https?:|blob:|data:)/i.test(fileUrl);

  useEffect(() => {
    let cancelled = false;

    async function renderPdf() {
      if (!canRenderPdf || fileType !== 'pdf' || !canvasRef.current) {
        return;
      }

      const loadingTask = getDocument(fileUrl);
      const pdf = await loadingTask.promise;
      if (cancelled) {
        return;
      }
      const page = await pdf.getPage(1);
      const viewport = page.getViewport({ scale: 1.2 });
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: context, viewport }).promise;
    }

    void renderPdf();

    return () => {
      cancelled = true;
    };
  }, [fileUrl, fileType]);

  if (!fileUrl) {
    return (
      <div className="glass-card flex min-h-[420px] items-center justify-center p-6 text-center text-slate-500">
        Upload a document to render it here.
      </div>
    );
  }

  if (fileType === 'pdf' && canRenderPdf) {
    return (
      <div className="glass-card overflow-hidden p-4">
        <canvas ref={canvasRef} className="h-auto w-full rounded-2xl bg-slate-100" />
      </div>
    );
  }

  return (
    <div className="glass-card p-5">
      <p className="section-label">Document preview</p>
      <pre className="mt-4 max-h-[520px] overflow-auto whitespace-pre-wrap rounded-2xl bg-slate-950 p-4 text-sm leading-6 text-slate-100">{text || 'Preview text will appear here for DOCX files.'}</pre>
    </div>
  );
}

DocumentViewer.propTypes = {
  fileUrl: PropTypes.string,
  fileType: PropTypes.oneOf(['pdf', 'docx']),
  text: PropTypes.string,
};
