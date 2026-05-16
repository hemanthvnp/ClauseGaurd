/**
 * useWebSocket — real-time document processing status
 *
 * Connects to WS /ws/document/{documentId}?token=<jwt> and streams
 * progress events until the document reaches a terminal state.
 *
 * Returns:
 *   stage      — current processing stage (string)
 *   pct        — progress percentage (0-100)
 *   detail     — optional detail message
 *   connected  — WebSocket is open
 *   error      — connection/protocol error
 *
 * Usage:
 *   const { stage, pct, connected } = useWebSocket(documentId, token);
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const TERMINAL_STAGES = new Set(['complete', 'failed']);
const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECTS = 5;

export function useWebSocket(documentId, token, { enabled = true } = {}) {
  const [stage, setStage]       = useState('queued');
  const [pct, setPct]           = useState(0);
  const [detail, setDetail]     = useState(null);
  const [connected, setConnected] = useState(false);
  const [error, setError]       = useState(null);

  const wsRef          = useRef(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef(null);
  const isTerminal     = useRef(false);

  const connect = useCallback(() => {
    if (!documentId || !token || !enabled || isTerminal.current) return;

    const apiBase = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')
      .replace(/^http/, 'ws');
    const url = `${apiBase}/ws/document/${documentId}?token=${encodeURIComponent(token)}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
        reconnectCount.current = 0;
      };

      ws.onmessage = (evt) => {
        try {
          const event = JSON.parse(evt.data);
          if (event.error) {
            setError(event.error);
            return;
          }
          setStage(event.stage  ?? 'processing');
          setPct(event.pct     ?? 0);
          setDetail(event.detail ?? null);

          if (TERMINAL_STAGES.has(event.stage)) {
            isTerminal.current = true;
            ws.close(1000, 'done');
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        setError('WebSocket connection error');
        setConnected(false);
      };

      ws.onclose = (evt) => {
        setConnected(false);
        wsRef.current = null;
        if (isTerminal.current || evt.code === 1000) return;

        if (reconnectCount.current < MAX_RECONNECTS) {
          reconnectCount.current += 1;
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
        } else {
          setError('Connection lost. Refresh to check status.');
        }
      };
    } catch (err) {
      setError(`WebSocket unavailable: ${err.message}`);
    }
  }, [documentId, token, enabled]);

  useEffect(() => {
    isTerminal.current = false;
    reconnectCount.current = 0;
    connect();

    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { stage, pct, detail, connected, error, isTerminal: isTerminal.current };
}
