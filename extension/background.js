const DEFAULT_API_BASE = 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 30000;

chrome.runtime.onInstalled.addListener(() => {
  console.log('ClauseGuard extension installed');
  chrome.storage.sync.get({ apiBase: '' }, (items) => {
    if (!items.apiBase) {
      chrome.storage.sync.set({ apiBase: DEFAULT_API_BASE });
    }
  });
});

function getApiBase() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE }, (items) => {
      resolve(items.apiBase || DEFAULT_API_BASE);
    });
  });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'GET_API_BASE') {
    getApiBase().then((apiBase) => sendResponse({ apiBase }));
    return true;
  }

  if (message?.type === 'SET_API_BASE') {
    const url = (message.apiBase || '').trim().replace(/\/$/, '');
    chrome.storage.sync.set({ apiBase: url || DEFAULT_API_BASE }, () => {
      sendResponse({ ok: true });
    });
    return true;
  }

  if (message?.type !== 'ANALYZE_TEXT') {
    return false;
  }

  getApiBase().then((apiBase) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    fetch(`${apiBase}/api/v1/extension/analyze-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message.payload),
      signal: controller.signal,
    })
      .then(async (response) => {
        clearTimeout(timeoutId);
        if (!response.ok) {
          const errorText = await response.text().catch(() => '');
          let detail = errorText;
          try {
            detail = JSON.parse(errorText)?.detail || errorText;
          } catch (_) {}
          throw new Error(detail || `Server error ${response.status}`);
        }
        return response.json();
      })
      .then((data) => sendResponse({ ok: true, data }))
      .catch((error) => {
        clearTimeout(timeoutId);
        const msg =
          error.name === 'AbortError'
            ? `Analysis timed out after ${REQUEST_TIMEOUT_MS / 1000} seconds.`
            : error.message || 'ClauseGuard analysis failed.';
        sendResponse({ ok: false, error: msg });
      });
  });

  return true;
});
