const DEFAULT_SERVER_URL = 'http://127.0.0.1:3000';

const serverUrlInput = document.getElementById('serverUrl');
const tokenInput = document.getElementById('token');
const scanBtn = document.getElementById('scanBtn');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.classList.toggle('err', !!isError);
}

function isSupportedUrl(url) {
  return /^https:\/\/www\.linkedin\.com\/(feed|jobs)\//.test(url || '');
}

function renderResults(results) {
  resultsEl.innerHTML = '';
  for (const r of results) {
    const item = document.createElement('div');
    item.className = 'item';

    const row1 = document.createElement('div');
    row1.className = 'row1';
    const title = document.createElement('span');
    title.className = 'title';
    title.textContent = r.title || '(no title)';
    const badge = document.createElement('span');
    badge.className = 'badge ' + (r.queued ? 'queued' : 'skip');
    badge.textContent = r.queued ? 'queued' : 'skip';
    row1.append(title, badge);

    const company = document.createElement('div');
    company.className = 'company';
    const scoreBits = [`score ${r.score}`];
    if (r.llm_score !== null && r.llm_score !== undefined) {
      scoreBits.push(`fit ${r.llm_score}`);
    }
    company.textContent = `${r.company} — ${scoreBits.join(', ')}`;

    item.append(row1, company);

    if (r.fit_note) {
      const fit = document.createElement('div');
      fit.className = 'fit';
      fit.textContent = r.fit_note;
      item.append(fit);
    }

    if (r.flags && r.flags.length) {
      const flags = document.createElement('div');
      flags.className = 'flags';
      flags.textContent = r.flags.join(' · ');
      item.append(flags);
    }

    resultsEl.append(item);
  }
}

async function loadSettings() {
  const { serverUrl, token } = await chrome.storage.local.get(['serverUrl', 'token']);
  serverUrlInput.value = serverUrl || DEFAULT_SERVER_URL;
  tokenInput.value = token || '';
}

serverUrlInput.addEventListener('change', () => {
  chrome.storage.local.set({ serverUrl: serverUrlInput.value.trim() || DEFAULT_SERVER_URL });
});
tokenInput.addEventListener('change', () => {
  chrome.storage.local.set({ token: tokenInput.value.trim() });
});

async function refreshScanAvailability() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab && isSupportedUrl(tab.url)) {
    scanBtn.disabled = false;
    setStatus('');
    return tab;
  }
  scanBtn.disabled = true;
  setStatus('Open the LinkedIn feed or a Jobs page to scan.');
  return null;
}

async function scan() {
  const tab = await refreshScanAvailability();
  if (!tab) return;

  scanBtn.disabled = true;
  resultsEl.innerHTML = '';
  setStatus('Reading the page…');

  let items;
  try {
    const resp = await chrome.tabs.sendMessage(tab.id, { type: 'EXTRACT_ITEMS' });
    items = (resp && resp.items) || [];
  } catch {
    setStatus('Could not read this page — try reloading it, then scan again.', true);
    scanBtn.disabled = false;
    return;
  }

  if (items.length === 0) {
    setStatus('No items found on this page.');
    scanBtn.disabled = false;
    return;
  }

  const serverUrl = (serverUrlInput.value.trim() || DEFAULT_SERVER_URL).replace(/\/$/, '');
  const token = tokenInput.value.trim();
  setStatus(`Rating ${items.length} item${items.length === 1 ? '' : 's'}…`);

  let data;
  try {
    const resp = await fetch(`${serverUrl}/api/rate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Extension-Token': token },
      body: JSON.stringify({ items }),
    });
    if (!resp.ok) {
      setStatus(`Server rejected the request (${resp.status}) — check the token matches config.toml's [extension].token.`, true);
      scanBtn.disabled = false;
      return;
    }
    data = await resp.json();
  } catch {
    setStatus("Can't reach the local server — is `python -m webapp` running?", true);
    scanBtn.disabled = false;
    return;
  }

  const results = data.results || [];
  const queuedCount = results.filter((r) => r.queued).length;
  setStatus(`${results.length} item${results.length === 1 ? '' : 's'} — ${queuedCount} queued`);
  renderResults(results);
  scanBtn.disabled = false;
}

scanBtn.addEventListener('click', scan);

loadSettings().then(refreshScanAvailability);
