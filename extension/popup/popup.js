const DEFAULT_API_BASE = 'http://localhost:8000';

const apiBaseInput = document.getElementById('api-base');
const saveBtn = document.getElementById('save-btn');
const saveStatus = document.getElementById('save-status');
const openDashboardBtn = document.getElementById('open-dashboard');

// Load saved API URL
chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE }, (items) => {
  apiBaseInput.value = items.apiBase || DEFAULT_API_BASE;
});

// Save settings
saveBtn.addEventListener('click', () => {
  const url = (apiBaseInput.value || '').trim().replace(/\/$/, '') || DEFAULT_API_BASE;
  apiBaseInput.value = url;
  chrome.storage.sync.set({ apiBase: url }, () => {
    saveStatus.textContent = 'Saved!';
    setTimeout(() => { saveStatus.textContent = ''; }, 2000);
  });
});

// Open API docs using the saved URL
openDashboardBtn.addEventListener('click', () => {
  chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE }, (items) => {
    const base = (items.apiBase || DEFAULT_API_BASE).replace(/\/$/, '');
    chrome.tabs.create({ url: `${base}/docs` });
  });
});
