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
}
tabBtns.forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
const initHash = location.hash.replace('#', '');
if (['add', 'jobs', 'settings'].includes(initHash)) showTab(initHash);

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

const TYPE_META = {
  track:                  { label: 'single track',       icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>` },
  album:                  { label: 'album',              icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/></svg>` },
  discography:            { label: 'discography',        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>` },
  playlist:               { label: 'playlist',           icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>` },
  expand_albums:          { label: 'playlist → albums',  icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>` },
  expand_discographies:   { label: 'playlist → discos',  icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>` },
  explicit_upgrade:       { label: 'fix clean → explicit', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>` },
};

function typeIcon(type) {
  return (TYPE_META[type] || TYPE_META['playlist']).icon;
}

function typeLabel(type) {
  return (TYPE_META[type] || { label: type }).label;
}

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
    if (s.music_quality) {
      document.getElementById('music_quality').value = String(s.music_quality);
    }
    document.getElementById('download_lyrics').checked = !!s.download_lyrics;
    document.getElementById('prefer_explicit').checked = !!s.prefer_explicit;
  } catch (e) {
    console.error('loadSettings', e);
  }
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
  };
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      flash('settings-msg', '✓ saved', 'ok');
      document.getElementById('qobuz_token').value = '';
      loadSettings();
    } else {
      flash('settings-msg', 'error saving', 'err');
    }
  } catch (err) {
    flash('settings-msg', String(err), 'err');
  }
});

/* ── mode selector ──────────────────────────────────────────────── */
let selectedMode = 'track';

const libraryScanField = document.getElementById('library-scan-field');
const libraryScanToggle = document.getElementById('library-scan-toggle');
const urlInput = document.getElementById('playlist-url');

function updateExplicitUpgradeUI() {
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

libraryScanToggle.addEventListener('change', updateExplicitUpgradeUI);

document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedMode = btn.dataset.mode;
    urlInput.placeholder = btn.dataset.placeholder;
    libraryScanToggle.checked = false;
    urlInput.disabled = false;
    updateExplicitUpgradeUI();
  });
});

/* ── add form ───────────────────────────────────────────────────── */
document.getElementById('add-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  // For explicit_upgrade with library scan, use the "library" sentinel instead of a URL.
  let url = urlInput.value.trim();
  if (selectedMode === 'explicit_upgrade' && libraryScanToggle.checked) {
    url = 'library';
  }
  if (!url) return;
  try {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: selectedMode, url }),
    });
    const data = await res.json();
    if (res.ok) {
      flash('add-msg', `✓ job #${data.job_id} queued`, 'ok');
      urlInput.value = '';
      libraryScanToggle.checked = false;
      urlInput.disabled = false;
      updateExplicitUpgradeUI();
      setTimeout(() => showTab('jobs'), 350);
      loadJobs();
    } else {
      flash('add-msg', data.error || 'error creating job', 'err');
    }
  } catch (err) {
    flash('add-msg', String(err), 'err');
  }
});

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

// Statuses that should keep the worker-running dot lit and the log modal auto-refreshing.
const ACTIVE_STATUSES = new Set([
  'queued', 'resolving', 'awaiting_confirm', 'confirmed',
  'downloading', 'tagging', 'verifying', 'cancelling',
]);

// Statuses where we show a Cancel button.
const CANCELLABLE_STATUSES = new Set([
  'queued', 'resolving', 'awaiting_confirm', 'confirmed',
  'downloading', 'tagging', 'verifying',
]);

// Statuses where we show a Delete button.
const DELETABLE_STATUSES = new Set(['done', 'done_with_warnings', 'error', 'cancelled']);

let cachedJobs = [];
let currentFilter = 'all';

function formatPlan(planJson) {
  if (!planJson) return '';
  let plan;
  try { plan = JSON.parse(planJson); } catch { return ''; }
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
      ? `<button class="job-cancel-btn" onclick="cancelJob(${job.id})" title="Cancel job">✕</button>`
      : '';

    const deleteBtn = DELETABLE_STATUSES.has(job.status)
      ? `<button class="job-delete-btn" onclick="deleteJob(${job.id})" title="Delete job">🗑</button>`
      : '';

    return `
      <div class="job-card${isAwaitingConfirm ? ' job-card--review' : ''}">
        <div class="job-num">#${String(job.id).padStart(3, '0')}</div>
        <div class="job-main">
          <div class="job-title">${typeIcon(job.type)} ${escHtml(label)}</div>
          <div class="job-url">${escHtml(job.url)}</div>
          <div class="job-meta"><span>${escHtml(job.created_at)}</span></div>
        </div>
        <span class="pill ${s.cls}">${s.label}</span>
        ${cancelBtn}
        ${deleteBtn}
        <button class="job-log-btn" onclick="showLog(${job.id})">Log</button>
        ${confirmRow}
      </div>
    `;
  }).join('');

  // update worker status indicator
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
  try {
    const res = await fetch(`/api/jobs/${jobId}/confirm`, { method: 'POST' });
    if (res.ok) {
      await loadJobs();
    } else {
      const d = await res.json();
      alert(`Could not confirm: ${d.error || res.status}`);
    }
  } catch (err) {
    alert(`Error: ${err}`);
  }
};

window.cancelJob = async function(jobId) {
  try {
    const res = await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
    if (res.ok) {
      await loadJobs();
    } else {
      const d = await res.json();
      alert(`Could not cancel: ${d.error || res.status}`);
    }
  } catch (err) {
    alert(`Error: ${err}`);
  }
};

window.deleteJob = async function(jobId) {
  try {
    const res = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
    if (res.ok) {
      await loadJobs();
    } else {
      const d = await res.json();
      alert(`Could not delete: ${d.error || res.status}`);
    }
  } catch (err) {
    alert(`Error: ${err}`);
  }
};

document.querySelectorAll('.jobs-filter button').forEach(b => {
  b.addEventListener('click', () => {
    currentFilter = b.dataset.filter;
    document.querySelectorAll('.jobs-filter button').forEach(x =>
      x.setAttribute('aria-selected', x === b ? 'true' : 'false')
    );
    renderJobs();
  });
});

document.getElementById('refresh-jobs').addEventListener('click', loadJobs);

/* ── modal / log viewer ─────────────────────────────────────────── */
function colorLine(text) {
  const low = text.toLowerCase();
  if (/error|failed|exception/.test(low)) return 'err';
  if (/warn|warning/.test(low)) return 'warn';
  if (/\[pipeline\]|\[pipeline\//.test(low)) return 'dim';
  return '';
}

let currentLogJobId = null;

function renderLogContent(data) {
  const logEl = document.getElementById('modal-log');
  const job = cachedJobs.find(j => j.id === data.id) || data;
  document.getElementById('modal-sub').textContent =
    `${typeLabel(job.type)} · ${job.status}`;

  // Show plan summary in modal for awaiting_confirm jobs.
  const planBar = document.getElementById('modal-plan-bar');
  const planEl = document.getElementById('modal-plan');
  if (job.status === 'awaiting_confirm' && job.plan) {
    planEl.textContent = formatPlan(job.plan);
    planBar.style.display = '';
  } else {
    planBar.style.display = 'none';
  }

  // Show confirm/cancel buttons in modal for awaiting_confirm jobs.
  const modalActions = document.getElementById('modal-actions');
  if (job.status === 'awaiting_confirm') {
    modalActions.style.display = 'flex';
    modalActions.dataset.jobId = data.id;
  } else {
    modalActions.style.display = 'none';
  }

  const lines = (data.log || '(no log yet)').split('\n');
  const atBottom = logEl.parentElement.scrollHeight - logEl.parentElement.scrollTop
    <= logEl.parentElement.clientHeight + 40;
  logEl.innerHTML = lines.map((line, i) => {
    const num = String(i + 1).padStart(2, '0');
    const cls = colorLine(line);
    return `<span class="line-num">${num}</span><span class="${cls}">${escHtml(line)}</span>\n`;
  }).join('');
  if (atBottom) logEl.parentElement.scrollTop = logEl.parentElement.scrollHeight;
}

async function refreshModalLog() {
  if (currentLogJobId === null) return;
  try {
    const res = await fetch('/api/jobs/' + currentLogJobId);
    const data = await res.json();
    renderLogContent(data);
  } catch (e) { /* silent */ }
}

window.showLog = async function(jobId) {
  const job = cachedJobs.find(j => j.id === jobId);
  const modal = document.getElementById('job-modal');
  const logEl = document.getElementById('modal-log');

  currentLogJobId = jobId;
  document.getElementById('modal-title').textContent = `Job #${String(jobId).padStart(3, '0')} log`;
  document.getElementById('modal-sub').textContent = job
    ? `${typeLabel(job.type)} · ${job.status}`
    : '';

  logEl.innerHTML = '<span class="dim">loading…</span>';
  modal.classList.remove('hidden');

  await refreshModalLog();
};

function closeModal() {
  currentLogJobId = null;
  document.getElementById('job-modal').classList.add('hidden');
}
document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('job-modal').addEventListener('click', e => {
  if (e.target.id === 'job-modal') closeModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// Modal confirm/cancel buttons
document.getElementById('modal-confirm-btn').addEventListener('click', async () => {
  const jobId = parseInt(document.getElementById('modal-actions').dataset.jobId, 10);
  await window.confirmJob(jobId);
  closeModal();
});
document.getElementById('modal-cancel-btn').addEventListener('click', async () => {
  const jobId = parseInt(document.getElementById('modal-actions').dataset.jobId, 10);
  await window.cancelJob(jobId);
  closeModal();
});

/* ── auto-refresh ───────────────────────────────────────────────── */
setInterval(() => {
  if (document.getElementById('tab-jobs').classList.contains('active')) loadJobs();
}, 5000);

// Refresh the open log modal every 2 s while the job is active.
setInterval(() => {
  if (currentLogJobId === null) return;
  const job = cachedJobs.find(j => j.id === currentLogJobId);
  if (job && ACTIVE_STATUSES.has(job.status)) refreshModalLog();
}, 2000);

/* ── init ───────────────────────────────────────────────────────── */
loadSettings();
loadJobs();
