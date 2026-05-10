import { useCallback, useEffect, useRef, useState } from 'react';

import { documentsApi } from '../api/documents';

const POLL_INTERVAL_MS = 3000;

export function useDocuments(shouldLoad = true) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const timerRef = useRef(null);

  const fetchDocuments = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const response = await documentsApi.list();
      setDocuments(response.data);
      setError('');
      return response.data;
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Unable to load documents.');
      return [];
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!shouldLoad) return undefined;

    let active = true;

    async function tick() {
      if (!active) return;
      const docs = await fetchDocuments(timerRef.current !== null);
      if (!active) return;

      const hasProcessing = docs.some((d) => d.status === 'processing');
      if (hasProcessing) {
        timerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
      } else {
        timerRef.current = null;
      }
    }

    void tick();

    return () => {
      active = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [shouldLoad, fetchDocuments]);

  return { documents, loading, error, setDocuments, refetch: fetchDocuments };
}
