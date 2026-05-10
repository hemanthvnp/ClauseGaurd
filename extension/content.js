const TITLE_PATTERNS = /(terms of service|terms and conditions|privacy policy|user agreement|legal)/i;
const URL_PATTERNS = /(terms|privacy|legal|agreement)/i;
const TEXT_LIMIT = 50000;

const RISK_COLORS = {
  critical: '#fecaca',
  high: '#fed7aa',
  medium: '#fde68a',
  low: '#d1fae5',
};

const RISK_BADGES = {
  critical: { bg: '#dc2626', text: '#fff' },
  high: { bg: '#ea580c', text: '#fff' },
  medium: { bg: '#ca8a04', text: '#fff' },
  low: { bg: '#16a34a', text: '#fff' },
};

function shouldInject() {
  return TITLE_PATTERNS.test(document.title) || URL_PATTERNS.test(window.location.href);
}

function createAnalyzeButton() {
  const button = document.createElement('button');
  button.id = 'clauseguard-analyze-btn';
  button.textContent = 'Analyze with ClauseGuard';
  button.setAttribute('aria-label', 'Analyze this page with ClauseGuard');
  Object.assign(button.style, {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    zIndex: '2147483647',
    background: '#0f172a',
    color: '#fff',
    border: '0',
    borderRadius: '999px',
    padding: '12px 20px',
    fontSize: '14px',
    fontWeight: '600',
    boxShadow: '0 12px 40px rgba(15, 23, 42, 0.35)',
    cursor: 'pointer',
    transition: 'opacity 0.2s',
  });
  return button;
}

function extractVisibleText() {
  if (!document.body) {
    return { text: '', truncated: false };
  }
  const full = document.body.innerText || '';
  return {
    text: full.slice(0, TEXT_LIMIT),
    truncated: full.length > TEXT_LIMIT,
  };
}

function ensureSidebar() {
  let sidebar = document.getElementById('clauseguard-sidebar');
  if (sidebar) {
    return sidebar;
  }

  sidebar = document.createElement('aside');
  sidebar.id = 'clauseguard-sidebar';
  sidebar.setAttribute('aria-label', 'ClauseGuard Analysis');
  Object.assign(sidebar.style, {
    position: 'fixed',
    top: '0',
    right: '0',
    width: '380px',
    height: '100vh',
    background: '#ffffff',
    borderLeft: '1px solid #e2e8f0',
    boxShadow: '-12px 0 30px rgba(15, 23, 42, 0.18)',
    zIndex: '2147483646',
    overflow: 'auto',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    fontSize: '14px',
    color: '#1e293b',
  });

  sidebar.innerHTML = `
    <div style="position:sticky;top:0;background:#fff;border-bottom:1px solid #e2e8f0;padding:16px 20px;display:flex;justify-content:space-between;align-items:center;">
      <div>
        <div style="font-size:13px;font-weight:700;letter-spacing:0.08em;color:#0f766e;text-transform:uppercase;">ClauseGuard</div>
        <div style="font-size:12px;color:#64748b;">Risk Analysis</div>
      </div>
      <button id="clauseguard-close" aria-label="Close sidebar" style="background:none;border:none;cursor:pointer;padding:4px;color:#64748b;font-size:18px;">✕</button>
    </div>
    <div id="clauseguard-sidebar-body" style="padding:16px 20px;">Waiting for analysis.</div>
  `;

  document.body.appendChild(sidebar);

  sidebar.querySelector('#clauseguard-close').addEventListener('click', () => {
    sidebar.style.display = 'none';
  });

  return sidebar;
}

function renderBadge(level) {
  const colors = RISK_BADGES[level] || RISK_BADGES.medium;
  return `<span style="display:inline-block;background:${colors.bg};color:${colors.text};border-radius:4px;padding:1px 6px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">${level}</span>`;
}

function renderResults(data, truncated) {
  const { clauses = [], overall_risk_score = 0, overall_risk_level = 'low', summary = {} } = data;

  const summaryHtml = Object.entries(summary)
    .map(([level, count]) => `<span style="margin-right:8px;">${renderBadge(level)} ${count}</span>`)
    .join('');

  const truncationWarning = truncated
    ? `<div style="margin-bottom:12px;padding:8px 12px;background:#fef3c7;border:1px solid #fcd34d;border-radius:6px;font-size:12px;color:#92400e;">
        ⚠ Page text was truncated to ${TEXT_LIMIT.toLocaleString()} characters. Analysis may be incomplete.
       </div>`
    : '';

  const clauseHtml = clauses
    .map(
      (c) => `
      <div style="margin-bottom:12px;padding:12px;border:1px solid #e2e8f0;border-radius:8px;border-left:4px solid ${RISK_COLORS[c.risk_level] ? '#' + (c.risk_level === 'critical' ? 'dc2626' : c.risk_level === 'high' ? 'ea580c' : c.risk_level === 'medium' ? 'ca8a04' : '16a34a') : '#94a3b8'};">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span style="font-size:12px;font-weight:600;color:#475569;">${c.category || 'General'}</span>
          ${renderBadge(c.risk_level)}
        </div>
        <div style="font-size:12px;color:#64748b;margin-bottom:6px;line-height:1.5;">${c.explanation || ''}</div>
        <details style="font-size:11px;color:#94a3b8;">
          <summary style="cursor:pointer;color:#64748b;">Show clause text</summary>
          <div style="margin-top:6px;padding:8px;background:#f8fafc;border-radius:4px;line-height:1.5;">${c.text}</div>
        </details>
      </div>
    `,
    )
    .join('');

  return `
    ${truncationWarning}
    <div style="margin-bottom:16px;padding:12px;background:#f8fafc;border-radius:8px;">
      <div style="font-size:12px;color:#64748b;margin-bottom:4px;">Overall Risk Score</div>
      <div style="font-size:22px;font-weight:700;color:#0f172a;">${Math.round(overall_risk_score)}<span style="font-size:13px;color:#64748b;">/100</span></div>
      <div style="margin-top:6px;">${renderBadge(overall_risk_level)}</div>
    </div>
    <div style="margin-bottom:12px;">${summaryHtml}</div>
    <div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.05em;">${clauses.length} Clauses Analyzed</div>
    ${clauseHtml}
  `;
}

function highlightClauses(clauses) {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.parentElement) {
        return NodeFilter.FILTER_REJECT;
      }
      const tag = node.parentElement.tagName;
      if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(tag) || node.parentElement.closest('#clauseguard-sidebar')) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  const textNodes = [];
  while (walker.nextNode()) {
    textNodes.push(walker.currentNode);
  }

  clauses
    .filter((clause) => clause.risk_level !== 'low')
    .forEach((clause) => {
      const matchText = clause.text.trim().slice(0, 200);
      if (!matchText) {
        return;
      }
      for (const textNode of textNodes) {
        const index = textNode.nodeValue.indexOf(matchText);
        if (index < 0) {
          continue;
        }
        const span = document.createElement('span');
        span.style.background = RISK_COLORS[clause.risk_level] || '#fde68a';
        span.style.borderRadius = '3px';
        span.style.padding = '0 2px';
        span.title = `${clause.category} · ${clause.risk_level} risk`;

        const before = textNode.nodeValue.slice(0, index);
        const after = textNode.nodeValue.slice(index + matchText.length);
        const parent = textNode.parentNode;
        const fragment = document.createDocumentFragment();
        if (before) {
          fragment.appendChild(document.createTextNode(before));
        }
        span.appendChild(document.createTextNode(matchText));
        fragment.appendChild(span);
        if (after) {
          fragment.appendChild(document.createTextNode(after));
        }
        parent.replaceChild(fragment, textNode);
        break;
      }
    });
}

async function analyzePage() {
  const sidebar = ensureSidebar();
  sidebar.style.display = '';
  const body = sidebar.querySelector('#clauseguard-sidebar-body');
  body.innerHTML = '<div style="color:#64748b;padding:20px 0;text-align:center;">Analyzing page…</div>';

  const btn = document.getElementById('clauseguard-analyze-btn');
  if (btn) {
    btn.disabled = true;
    btn.style.opacity = '0.6';
  }

  const { text, truncated } = extractVisibleText();

  const response = await chrome.runtime.sendMessage({
    type: 'ANALYZE_TEXT',
    payload: {
      text,
      source_url: window.location.href,
      title: document.title,
    },
  });

  if (btn) {
    btn.disabled = false;
    btn.style.opacity = '1';
  }

  if (!response?.ok) {
    body.innerHTML = `<div style="padding:12px;background:#fee2e2;border-radius:8px;color:#991b1b;">
      <strong>Analysis failed</strong><br>${response?.error || 'Unknown error. Is the ClauseGuard server running?'}
    </div>`;
    return;
  }

  highlightClauses(response.data.clauses || []);
  body.innerHTML = renderResults(response.data, truncated);
}

if (shouldInject()) {
  const button = createAnalyzeButton();
  button.addEventListener('click', () => {
    void analyzePage();
  });
  document.documentElement.appendChild(button);
}
