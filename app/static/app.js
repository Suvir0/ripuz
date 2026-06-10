'use strict';

/* ── theme ──────────────────────────────────────────────────────── */
const root = document.documentElement;
const savedTheme = localStorage.getItem('ripuz-theme');
if (savedTheme) root.setAttribute('data-theme', savedTheme);
document.getElementById('theme-toggle').addEventListener('click', () => {
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('ripuz-theme', next);
});

/* ── tabs ───────────────────────────────────────────────────────── */
const tabBtns = document.querySelectorAll('nav.tabs button');
function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  tabBtns.forEach(b => b.setAttribute('aria-selected', b.dataset.tab === name ? 'true' : 'false'));
  location.hash = name;
  if (name === 'library' && !libData) loadLibrary();
}
tabBtns.forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
const initHash = location.hash.replace('#', '');
if (['add', 'jobs', 'library', 'settings'].includes(initHash)) showTab(initHash);

/* ── messages ───────────────────────────────────────────────────── */
function flash(id, text, cls = 'ok') {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = 'msg ' + cls + ' show';
  setTimeout(() => el.classList.remove('show'), 2400);
}

/* ── helpers ────────────────────────────────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function fmtBytes(b) {
  if (b >= 1e12) return (b / 1e12).toFixed(1) + ' TB';
  if (b >= 1e9)  return (b / 1e9).toFixed(1) + ' GB';
  if (b >= 1e6)  return (b / 1e6).toFixed(1) + ' MB';
  return b + ' B';
}

function fmtDuration(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h) return `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  return `${m}:${String(sec).padStart(2,'0')}`;
}

const TYPE_META = {
  track:                  { label: 'single track',       icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>` },
  album:                  { label: 'album',              icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/></svg>` },
  discography:            { label: 'discography',        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>` },
  playlist:               { label: 'playlist',           icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>` },
  expand_albums:          { label: 'playlist → albums',  icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>` },
  expand_discographies:   { label: 'playlist → discos',  icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>` },
  explicit_upgrade:       { label: 'fix clean → explicit', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>` },
  retag_library:          { label: 'retag library',       icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>` },
  fetch_lyrics:           { label: 'fetch lyrics',        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>` },
  fetch_art:              { label: 'fetch album art',     icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>` },
};

const LIBRARY_ONLY_MODES = new Set(['retag_library', 'fetch_lyrics', 'fetch_art']);

function typeIcon(type) { return (TYPE_META[type] || TYPE_META['playlist']).icon; }
function typeLabel(type) { return (TYPE_META[type] || { label: type }).label; }

/* ── settings ───────────────────────────────────────────────────── */
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const s = await res.json();
    const tokenStatus = document.getElementById('token-status');
    if (s.qobuz_token) {
      tokenStatus.textContent = 'saved';
      tokenStatus.style.color = 'var(--success)';
    } else {
      tokenStatus.textContent = 'not set';
      tokenStatus.style.color = 'var(--faint)';
    }
    document.getElementById('downloads_dir').value = s.downloads_dir || '';
    document.getElementById('music_dir').value = s.music_dir || '';
    if (s.music_quality) document.getElementById('music_quality').value = String(s.music_quality);
    document.getElementById('download_lyrics').checked = !!s.download_lyrics;
    document.getElementById('prefer_explicit').checked = !!s.prefer_explicit;
    document.getElementById('notify_webhook_url').value = s.notify_webhook_url || '';
  } catch (e) { console.error('loadSettings', e); }
}

document.getElementById('settings-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const token = document.getElementById('qobuz_token').value.trim();
  const body = {
    qobuz_token: token,
    downloads_dir: document.getElementById('downloads_dir').value.trim(),
    music_dir: document.getElementById('music_dir').value.trim(),
    music_quality: parseInt(document.getElementById('music_quality').value, 10),
    download_lyrics: document.getElementById('download_lyrics').checked,
    prefer_explicit: document.getElementById('prefer_explicit').checked,
    notify_webhook_url: document.getElementById('notify_webhook_url').value.trim(),
  };
  try {
    const res = await fetch('/api/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (res.ok) {
      flash('settings-msg', '✓ saved', 'ok');
      document.getElementById('qobuz_token').value = '';
      loadSettings();
    } else {
      const d = await res.json();
      flash('settings-msg', d.error || 'error saving', 'err');
    }
  } catch (err) { flash('settings-msg', String(err), 'err'); }
});

/* ── mode selector ──────────────────────────────────────────────── */
let selectedMode = 'track';

const libraryScanField = document.getElementById('library-scan-field');
const libraryScanToggle = document.getElementById('library-scan-toggle');
const urlInput = document.getElementById('playlist-url');
const urlField = urlInput.closest('.field');

function updateModeUI() {
  if (LIBRARY_ONLY_MODES.has(selectedMode)) {
    libraryScanField.style.display = 'none';
    urlField.style.display = 'none';
    urlInput.required = false;
    urlInput.disabled = true;
    return;
  }
  urlField.style.display = '';
  urlInput.disabled = false;
  if (selectedMode !== 'explicit_upgrade') {
    libraryScanField.style.display = 'none';
    urlInput.required = true;
    return;
  }
  libraryScanField.style.display = '';
  if (libraryScanToggle.checked) {
    urlInput.required = false;
    urlInput.value = '';
    urlInput.disabled = true;
  } else {
    urlInput.required = true;
    urlInput.disabled = false;
  }
}

libraryScanToggle.addEventListener('change', updateModeUI);

document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedMode = btn.dataset.mode;
    urlInput.placeholder = btn.dataset.placeholder;
    libraryScanToggle.checked = false;
    urlInput.disabled = false;
    updateModeUI();
  });
});

/* ── add form ───────────────────────────────────────────────────── */
document.getElementById('add-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  let url = urlInput.value.trim();
  if (selectedMode === 'explicit_upgrade' && libraryScanToggle.checked) url = 'library';
  if (LIBRARY_ONLY_MODES.has(selectedMode)) url = 'library';
  if (!url) return;
  try {
    const res = await fetch('/api/jobs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: selectedMode, url }),
    });
    const data = await res.json();
    if (res.ok) {
      flash('add-msg', `✓ job #${data.job_id} queued`, 'ok');
      urlInput.value = '';
      libraryScanToggle.checked = false;
      urlInput.disabled = false;
      updateModeUI();
      setTimeout(() => showTab('jobs'), 350);
      loadJobs();
    } else {
      flash('add-msg', data.error || 'error creating job', 'err');
    }
  } catch (err) { flash('add-msg', String(err), 'err'); }
});

/* ── Qobuz search ───────────────────────────────────────────────── */
let _searchTimer = null;
document.getElementById('toggle-search').addEventListener('click', () => {
  const panel = document.getElementById('search-panel');
  const visible = panel.style.display !== 'none';
  panel.style.display = visible ? 'none' : 'block';
  if (!visible) document.getElementById('search-input').focus();
});

document.getElementById('search-input').addEventListener('input', (e) => {
  clearTimeout(_searchTimer);
  const q = e.target.value.trim();
  if (!q) { document.getElementById('search-results').innerHTML = ''; return; }
  _searchTimer = setTimeout(() => runSearch(q), 400);
});
document.getElementById('search-type').addEventListener('change', () => {
  const q = document.getElementById('search-input').value.trim();
  if (q) runSearch(q);
});

async function runSearch(q) {
  const type = document.getElementById('search-type').value;
  const container = document.getElementById('search-results');
  container.innerHTML = '<span style="color:var(--muted);font-size:12px;">Searching…</span>';
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&type=${type}&limit=12`);
    const data = await res.json();
    if (!res.ok) { container.innerHTML = `<span style="color:var(--error);font-size:12px;">${escHtml(data.error||'error')}</span>`; return; }
    const results = data.results || [];
    if (!results.length) { container.innerHTML = '<span style="color:var(--muted);font-size:12px;">No results</span>'; return; }
    container.innerHTML = results.map(r => {
      const explicitTag = r.explicit ? `<span class="explicit-tag">E</span>` : '';
      const sub = r.type === 'track'
        ? `${escHtml(r.artist)} · ${escHtml(r.album)}`
        : r.type === 'artist'
          ? 'Artist'
          : `${escHtml(r.artist)}${r.year ? ' · ' + escHtml(r.year) : ''}${r.track_count ? ' · ' + r.track_count + ' tracks' : ''}`;
      const jobType = r.type === 'artist' ? 'discography' : r.type === 'track' ? 'track' : 'album';
      const thumb = r.cover_url
        ? `<img class="search-thumb" src="${escHtml(r.cover_url)}" loading="lazy" onerror="this.style.display='none'">`
        : `<div class="search-thumb"></div>`;
      return `<div class="search-result">
        ${thumb}
        <div class="search-info">
          <div class="search-title">${escHtml(r.title)}${explicitTag}</div>
          <div class="search-sub">${sub}</div>
        </div>
        <button class="btn btn-ghost" style="flex-shrink:0;font-size:11px;" onclick="queueSearchResult('${escHtml(r.url)}','${jobType}')">Queue</button>
      </div>`;
    }).join('');
  } catch (e) { container.innerHTML = `<span style="color:var(--error);font-size:12px;">${escHtml(String(e))}</span>`; }
}

window.queueSearchResult = async function(url, jobType) {
  try {
    const res = await fetch('/api/jobs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: jobType, url }),
    });
    const data = await res.json();
    if (res.ok) {
      flash('add-msg', `✓ job #${data.job_id} queued`, 'ok');
      setTimeout(() => showTab('jobs'), 350);
      loadJobs();
    } else {
      alert(data.error || 'error creating job');
    }
  } catch (e) { alert(String(e)); }
};

/* ── jobs ───────────────────────────────────────────────────────── */
const STATUS_MAP = {
  queued:             { label: 'queued',      cls: 'pill-queued'   },
  resolving:          { label: 'resolving',   cls: 'pill-running'  },
  awaiting_confirm:   { label: 'review',      cls: 'pill-review'   },
  confirmed:          { label: 'confirmed',   cls: 'pill-queued'   },
  downloading:        { label: 'downloading', cls: 'pill-running'  },
  tagging:            { label: 'tagging',     cls: 'pill-tagging'  },
  verifying:          { label: 'verifying',   cls: 'pill-tagging'  },
  cancelling:         { label: 'cancelling',  cls: 'pill-error'    },
  cancelled:          { label: 'cancelled',   cls: 'pill-cancelled'},
  done:               { label: 'done',        cls: 'pill-done'     },
  done_with_warnings: { label: 'done · warn', cls: 'pill-warn'     },
  error:              { label: 'error',       cls: 'pill-error'    },
};

const ACTIVE_STATUSES = new Set([
  'queued', 'resolving', 'awaiting_confirm', 'confirmed',
  'downloading', 'tagging', 'verifying', 'cancelling',
]);
const CANCELLABLE_STATUSES = new Set([
  'queued', 'resolving', 'awaiting_confirm', 'confirmed',
  'downloading', 'tagging', 'verifying',
]);
const DELETABLE_STATUSES = new Set(['done', 'done_with_warnings', 'error', 'cancelled']);

let cachedJobs = [];
let currentFilter = 'all';

function formatPlan(planJson) {
  if (!planJson) return '';
  let plan;
  try { plan = JSON.parse(planJson); } catch { return ''; }
  // fetch_art plan
  if (plan.missing_albums !== undefined && plan.scanned_albums !== undefined) {
    return `${plan.missing_albums || 0} of ${plan.scanned_albums || 0} album(s) missing cover art`;
  }
  // fetch_lyrics plan
  if (plan.missing_files !== undefined) {
    return `${plan.missing_files || 0} of ${plan.scanned_files || 0} file(s) missing lyrics · ${plan.album_count || 0} album dir(s)`;
  }
  // retag_library plan (dirs list)
  if (plan.dirs !== undefined) {
    return `${plan.album_count || 0} album dir(s) to retag · ${plan.untagged_files || 0} of ${plan.scanned_files || 0} file(s) untagged or unmatched`;
  }
  const albums = plan.albums || [];
  const skipped = plan.skipped_existing || 0;
  const dup = plan.skipped_duplicate || 0;
  const est = plan.est_gb || 0;
  const capped = plan.capped ? ` · capped at ${plan.cap}` : '';
  const dupMsg = dup > 0 ? ` · ${dup} claimed by other job(s)` : '';
  return `${albums.length} album(s) to download${capped} · ${skipped} already present${dupMsg} · ~${est} GB`;
}

function renderJobs() {
  const container = document.getElementById('jobs-list');
  const filtered = cachedJobs.filter(j => {
    if (currentFilter === 'all') return true;
    if (currentFilter === 'active') return ACTIVE_STATUSES.has(j.status);
    if (currentFilter === 'done') return j.status === 'done' || j.status === 'done_with_warnings';
    if (currentFilter === 'error') return j.status === 'error';
    return true;
  });
  if (!filtered.length) {
    container.innerHTML = `<div class="empty"><span class="mono">no jobs</span>Paste a playlist URL on the <b>Add</b> tab to start a download.</div>`;
    return;
  }
  container.innerHTML = filtered.map(job => {
    const s = STATUS_MAP[job.status] || { label: job.status, cls: 'pill-queued' };
    const label = typeLabel(job.type);
    const isAwaitingConfirm = job.status === 'awaiting_confirm';
    const isCancellable = CANCELLABLE_STATUSES.has(job.status);
    const planSummary = isAwaitingConfirm ? formatPlan(job.plan) : '';
    const confirmRow = isAwaitingConfirm ? `
      <div class="job-confirm-row">
        <span class="job-plan-summary">${escHtml(planSummary)}</span>
        <div class="job-confirm-btns">
          <button class="btn btn-confirm" onclick="confirmJob(${job.id})">Confirm download</button>
          <button class="btn btn-cancel-job" onclick="cancelJob(${job.id})">Cancel</button>
        </div>
      </div>` : '';
    const cancelBtn = (!isAwaitingConfirm && isCancellable)
      ? `<button class="job-cancel-btn" onclick="cancelJob(${job.id})" title="Cancel job">✕</button>` : '';
    const deleteBtn = DELETABLE_STATUSES.has(job.status)
      ? `<button class="job-delete-btn" onclick="deleteJob(${job.id})" title="Delete job">🗑</button>` : '';
    return `
      <div class="job-card${isAwaitingConfirm ? ' job-card--review' : ''}">
        <div class="job-num">#${String(job.id).padStart(3, '0')}</div>
        <div class="job-main">
          <div class="job-title">${typeIcon(job.type)} ${escHtml(label)}</div>
          <div class="job-url">${escHtml(job.url)}</div>
          <div class="job-meta"><span>${escHtml(job.created_at)}</span></div>
        </div>
        <span class="pill ${s.cls}">${s.label}</span>
        ${cancelBtn}${deleteBtn}
        <button class="job-log-btn" onclick="showLog(${job.id})">Log</button>
        ${confirmRow}
      </div>`;
  }).join('');
  const hasActive = cachedJobs.some(j => ACTIVE_STATUSES.has(j.status));
  const dot = document.getElementById('worker-status');
  dot.textContent = hasActive ? 'worker · running' : 'worker · idle';
  dot.classList.toggle('active', hasActive);
}

async function loadJobs() {
  try {
    const res = await fetch('/api/jobs');
    cachedJobs = await res.json();
    renderJobs();
  } catch (e) {
    document.getElementById('jobs-list').innerHTML =
      `<div class="empty"><span class="mono">error</span>Failed to load jobs.</div>`;
  }
}

window.confirmJob = async function(jobId) {
  const res = await fetch(`/api/jobs/${jobId}/confirm`, { method: 'POST' });
  if (res.ok) { await loadJobs(); } else { const d = await res.json(); alert(`Could not confirm: ${d.error||res.status}`); }
};
window.cancelJob = async function(jobId) {
  const res = await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
  if (res.ok) { await loadJobs(); } else { const d = await res.json(); alert(`Could not cancel: ${d.error||res.status}`); }
};
window.deleteJob = async function(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
  if (res.ok) { await loadJobs(); } else { const d = await res.json(); alert(`Could not delete: ${d.error||res.status}`); }
};

document.querySelectorAll('.jobs-filter button').forEach(b => {
  b.addEventListener('click', () => {
    currentFilter = b.dataset.filter;
    document.querySelectorAll('.jobs-filter button').forEach(x =>
      x.setAttribute('aria-selected', x === b ? 'true' : 'false'));
    renderJobs();
  });
});
document.getElementById('refresh-jobs').addEventListener('click', loadJobs);

/* ── modal / log viewer (SSE + polling fallback) ────────────────── */
function colorLine(text) {
  const low = text.toLowerCase();
  if (/error|failed|exception/.test(low)) return 'err';
  if (/warn|warning/.test(low)) return 'warn';
  if (/\[pipeline\]|\[pipeline\//.test(low)) return 'dim';
  return '';
}

let currentLogJobId = null;
let _logEventSource = null;
let _logPollInterval = null;

function _stopLogStream() {
  if (_logEventSource) { try { _logEventSource.close(); } catch {} _logEventSource = null; }
  if (_logPollInterval) { clearInterval(_logPollInterval); _logPollInterval = null; }
}

function renderLogContent(data) {
  const logEl = document.getElementById('modal-log');
  const job = cachedJobs.find(j => j.id === data.id) || data;
  document.getElementById('modal-sub').textContent = `${typeLabel(job.type)} · ${job.status}`;
  const planBar = document.getElementById('modal-plan-bar');
  const planEl = document.getElementById('modal-plan');
  if (job.status === 'awaiting_confirm' && job.plan) {
    planEl.textContent = formatPlan(job.plan);
    planBar.style.display = '';
  } else { planBar.style.display = 'none'; }
  const modalActions = document.getElementById('modal-actions');
  if (job.status === 'awaiting_confirm') {
    modalActions.style.display = 'flex';
    modalActions.dataset.jobId = data.id;
  } else { modalActions.style.display = 'none'; }
  const lines = (data.log || '(no log yet)').split('\n');
  const atBottom = logEl.parentElement.scrollHeight - logEl.parentElement.scrollTop
    <= logEl.parentElement.clientHeight + 40;
  logEl.innerHTML = lines.map((line, i) => {
    const num = String(i + 1).padStart(2, '0');
    return `<span class="line-num">${num}</span><span class="${colorLine(line)}">${escHtml(line)}</span>\n`;
  }).join('');
  if (atBottom) logEl.parentElement.scrollTop = logEl.parentElement.scrollHeight;
}

async function refreshModalLog() {
  if (currentLogJobId === null) return;
  try {
    const res = await fetch('/api/jobs/' + currentLogJobId);
    const data = await res.json();
    renderLogContent(data);
  } catch (e) {}
}

function _startLogStream(jobId) {
  _stopLogStream();
  try {
    const es = new EventSource(`/api/jobs/${jobId}/stream`);
    _logEventSource = es;
    es.addEventListener('log', () => refreshModalLog());
    es.addEventListener('status', (e) => {
      try {
        const d = JSON.parse(e.data);
        const job = cachedJobs.find(j => j.id === jobId);
        if (job) job.status = d.status;
        refreshModalLog();
        if (!ACTIVE_STATUSES.has(d.status)) { _stopLogStream(); loadJobs(); }
      } catch {}
    });
    es.onerror = () => {
      _stopLogStream();
      // fallback to polling
      _logPollInterval = setInterval(() => {
        const job = cachedJobs.find(j => j.id === jobId);
        if (job && ACTIVE_STATUSES.has(job.status)) refreshModalLog();
      }, 2000);
    };
  } catch (e) {
    // SSE not available — use polling
    _logPollInterval = setInterval(() => {
      const job = cachedJobs.find(j => j.id === jobId);
      if (job && ACTIVE_STATUSES.has(job.status)) refreshModalLog();
    }, 2000);
  }
}

window.showLog = async function(jobId) {
  const job = cachedJobs.find(j => j.id === jobId);
  const modal = document.getElementById('job-modal');
  const logEl = document.getElementById('modal-log');
  currentLogJobId = jobId;
  document.getElementById('modal-title').textContent = `Job #${String(jobId).padStart(3, '0')} log`;
  document.getElementById('modal-sub').textContent = job ? `${typeLabel(job.type)} · ${job.status}` : '';
  logEl.innerHTML = '<span class="dim">loading…</span>';
  modal.classList.remove('hidden');
  await refreshModalLog();
  if (job && ACTIVE_STATUSES.has(job.status)) _startLogStream(jobId);
};

function closeModal() {
  _stopLogStream();
  currentLogJobId = null;
  document.getElementById('job-modal').classList.add('hidden');
}
document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('job-modal').addEventListener('click', e => { if (e.target.id === 'job-modal') closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeModal(); closeAlbumModal(); } });

document.getElementById('modal-confirm-btn').addEventListener('click', async () => {
  const jobId = parseInt(document.getElementById('modal-actions').dataset.jobId, 10);
  await window.confirmJob(jobId); closeModal();
});
document.getElementById('modal-cancel-btn').addEventListener('click', async () => {
  const jobId = parseInt(document.getElementById('modal-actions').dataset.jobId, 10);
  await window.cancelJob(jobId); closeModal();
});

/* ── library dashboard ──────────────────────────────────────────── */
let libData = null;
let libQuery = '';
let libSort = 'artist';
let libShown = 0;
const LIB_PAGE = 200;

async function loadLibrary(refresh = false) {
  try {
    const url = '/api/library' + (refresh ? '?refresh=1' : '');
    const res = await fetch(url);
    libData = await res.json();
    libShown = 0;
    renderLibStats();
    renderLibGrid();
  } catch (e) { console.error('loadLibrary', e); }
}

function renderLibStats() {
  if (!libData) return;
  const s = libData.stats || {};
  document.getElementById('stat-artists').textContent = (s.artists ?? '—').toLocaleString();
  document.getElementById('stat-albums').textContent = (s.albums ?? '—').toLocaleString();
  document.getElementById('stat-tracks').textContent = (s.tracks ?? '—').toLocaleString();
  document.getElementById('stat-size').textContent = s.total_size_bytes != null ? fmtBytes(s.total_size_bytes) : '—';
  document.getElementById('stat-missing-art').textContent = (s.missing_art_count ?? '—').toLocaleString();
  document.getElementById('stat-missing-lrc').textContent = (s.missing_lyrics_count ?? '—').toLocaleString();
}

function _sortedFiltered() {
  if (!libData) return [];
  let albums = libData.albums || [];
  if (libQuery) {
    const q = libQuery.toLowerCase();
    albums = albums.filter(a =>
      (a.artist + ' ' + a.album).replace(/_/g, ' ').toLowerCase().includes(q)
    );
  }
  albums = [...albums];
  if (libSort === 'artist') albums.sort((a, b) => a.artist.localeCompare(b.artist) || a.album.localeCompare(b.album));
  else if (libSort === 'album') albums.sort((a, b) => a.album.localeCompare(b.album));
  else if (libSort === 'tracks') albums.sort((a, b) => b.track_count - a.track_count);
  else if (libSort === 'size') albums.sort((a, b) => b.size_bytes - a.size_bytes);
  return albums;
}

function _coverUrl(albumId) {
  return '/api/library/cover/' + albumId.split('/').map(encodeURIComponent).join('/');
}

function renderLibGrid() {
  const grid = document.getElementById('lib-grid');
  const albums = _sortedFiltered();
  const slice = albums.slice(0, libShown + LIB_PAGE);
  grid.innerHTML = slice.map(a => {
    const displayArtist = escHtml(a.artist.replace(/_/g, ' '));
    const displayAlbum = escHtml(a.album.replace(/_/g, ' '));
    const thumb = a.has_cover
      ? `<img src="${escHtml(_coverUrl(a.id))}" loading="lazy" alt="" onerror="this.parentElement.classList.add('lib-thumb--no-cover');this.remove()">`
      : `<div class="lib-thumb-placeholder">♪</div>`;
    return `<div class="lib-card" onclick="showAlbumDetail('${escHtml(a.id)}')">
      <div class="lib-thumb">${thumb}</div>
      <div class="lib-info">
        <div class="lib-album" title="${displayAlbum}">${displayAlbum}</div>
        <div class="lib-artist" title="${displayArtist}">${displayArtist}</div>
        <div class="lib-meta">${a.track_count} tracks · ${fmtBytes(a.size_bytes)}</div>
      </div>
    </div>`;
  }).join('');
  const moreBtn = document.getElementById('lib-more');
  const hasMore = slice.length < albums.length;
  moreBtn.style.display = hasMore ? '' : 'none';
  if (hasMore) moreBtn.textContent = `Load more (${albums.length - slice.length} remaining)`;
}

document.getElementById('lib-refresh').addEventListener('click', () => loadLibrary(true));
document.getElementById('lib-more').addEventListener('click', () => { libShown += LIB_PAGE; renderLibGrid(); });

let _libSearchTimer = null;
document.getElementById('lib-search').addEventListener('input', e => {
  clearTimeout(_libSearchTimer);
  _libSearchTimer = setTimeout(() => { libQuery = e.target.value.trim(); libShown = 0; renderLibGrid(); }, 150);
});
document.getElementById('lib-sort').addEventListener('change', e => {
  libSort = e.target.value; libShown = 0; renderLibGrid();
});

/* ── album detail modal ─────────────────────────────────────────── */
// Reuse job-modal for album detail by adding a second mode; simpler than a new modal element.
let _albumModalOpen = false;

window.showAlbumDetail = async function(albumId) {
  try {
    const res = await fetch('/api/library/album/' + albumId.split('/').map(encodeURIComponent).join('/'));
    if (!res.ok) return;
    const d = await res.json();
    const modal = document.getElementById('job-modal');
    _albumModalOpen = true;
    document.getElementById('modal-title').textContent =
      d.album.replace(/_/g, ' ') || albumId;
    document.getElementById('modal-sub').textContent =
      d.artist.replace(/_/g, ' ') + ' · ' + d.track_count + ' tracks · ' + fmtBytes(d.size_bytes || 0);
    document.getElementById('modal-plan-bar').style.display = 'none';
    document.getElementById('modal-actions').style.display = 'none';
    const coverUrl = d.has_cover ? _coverUrl(albumId) : null;
    const coverHtml = coverUrl
      ? `<img class="album-detail-cover" src="${escHtml(coverUrl)}" onerror="this.style.display='none'" alt="">`
      : `<div class="album-detail-cover" style="display:flex;align-items:center;justify-content:center;font-size:32px;color:var(--faint);">♪</div>`;
    const rows = (d.tracks || []).map((t, i) => {
      const quality = t.sample_rate ? `<span class="quality-badge">${t.bit_depth}/${Math.round(t.sample_rate/1000)}</span>` : '';
      const lrcDot = t.has_lyrics ? '<span title="has lyrics" style="color:var(--success)">♪</span>' : '';
      return `<tr>
        <td style="color:var(--muted);font-family:var(--font-mono);font-size:10px;">${i+1}</td>
        <td>${escHtml(t.title.replace(/_/g,' '))} ${lrcDot}</td>
        <td style="font-family:var(--font-mono);font-size:11px;">${fmtDuration(t.duration)}</td>
        <td>${quality}</td>
      </tr>`;
    }).join('');
    const logEl = document.getElementById('modal-log');
    logEl.innerHTML = `<div class="album-detail">
      <div class="album-detail-head">${coverHtml}
        <div class="album-detail-info">
          <h3>${escHtml(d.album.replace(/_/g,' '))}</h3>
          <div style="color:var(--muted);font-size:13px;">${escHtml(d.artist.replace(/_/g,' '))}</div>
          <div style="font-size:11px;color:var(--faint);margin-top:6px;">${d.track_count} tracks · ${fmtDuration(d.total_duration)} · ${fmtBytes(d.size_bytes||0)}</div>
          ${d.mbid_present ? '<div style="font-size:10px;color:var(--success);margin-top:4px;">✓ MusicBrainz matched</div>' : '<div style="font-size:10px;color:var(--muted);margin-top:4px;">No MusicBrainz ID</div>'}
        </div>
      </div>
      <table class="track-table">
        <thead><tr><th>#</th><th>Title</th><th>Duration</th><th>Quality</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
    modal.classList.remove('hidden');
  } catch (e) { console.error('showAlbumDetail', e); }
};

function closeAlbumModal() {
  if (_albumModalOpen) {
    _albumModalOpen = false;
    document.getElementById('job-modal').classList.add('hidden');
  }
}

/* ── auto-refresh ───────────────────────────────────────────────── */
setInterval(() => {
  if (document.getElementById('tab-jobs').classList.contains('active')) loadJobs();
}, 5000);

/* ── init ───────────────────────────────────────────────────────── */
loadSettings();
loadJobs();
