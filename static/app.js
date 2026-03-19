'use strict';

// ── Clock ──────────────────────────────────────────────────────────────────

function updateClock() {
  const el = document.getElementById('sys-clock');
  if (el) el.textContent = new Date().toLocaleTimeString('en-GB');
}
updateClock();
setInterval(updateClock, 1000);

// ── Toast ──────────────────────────────────────────────────────────────────

let toastTimer = null;

function showToast(msg, type = 'ok') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = type;
  el.style.display = 'block';
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.style.display = 'none'; }, 4000);
}

// ── Utilities ──────────────────────────────────────────────────────────────

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function fileBadge(name) {
  const ext = name.split('.').pop().toLowerCase();
  const cls = { pdf: 'badge-pdf', jpg: 'badge-jpg', jpeg: 'badge-jpeg', png: 'badge-png', txt: 'badge-txt' };
  return `<span class="file-type-badge ${cls[ext] || 'badge-other'}">${ext.toUpperCase()}</span>`;
}

function setFileCount(n) {
  const el = document.getElementById('file-count');
  if (el) el.textContent = `${n} FILE${n !== 1 ? 'S' : ''}`;
}

// ── Sidebar nav ────────────────────────────────────────────────────────────

function initSidebarNav() {
  const items = document.querySelectorAll('.nav-item');
  const topbarSection = document.getElementById('topbar-section');

  items.forEach(item => {
    item.addEventListener('click', () => {
      items.forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      if (topbarSection) topbarSection.textContent = item.querySelector('.nav-label')?.textContent || '';
      const target = document.getElementById(item.dataset.target);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

// ── Printers ───────────────────────────────────────────────────────────────

async function loadPrinters() {
  const statusEl = document.getElementById('printer-status');
  const ledEl    = document.getElementById('printer-led');
  const sel      = document.getElementById('printer-dropdown');

  if (ledEl) { ledEl.className = 'led led-blink led-orange'; }

  try {
    const res = await fetch('/printers');
    const printers = await res.json();

    sel.innerHTML = '<option value="">-- USE DEFAULT PRINTER --</option>';
    printers.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = `${p.name}  [${p.status.toUpperCase()}]`;
      sel.appendChild(opt);
    });

    if (printers.length > 0) {
      if (ledEl) ledEl.className = 'led led-green';
      if (statusEl) statusEl.textContent = `> ${printers.length} DEVICE(S) DETECTED VIA CUPS`;
    } else {
      if (ledEl) ledEl.className = 'led';
      if (statusEl) statusEl.textContent = '> NO PRINTERS FOUND — ADD ONE AT http://<pi-ip>:631';
    }
  } catch {
    if (ledEl) ledEl.className = 'led led-red';
    if (statusEl) statusEl.textContent = '> CONNECTION ERROR';
  }
}

// ── File list ──────────────────────────────────────────────────────────────

async function loadFiles() {
  const ul = document.getElementById('file-list');

  try {
    const res = await fetch('/files');
    const files = await res.json();

    ul.innerHTML = '';
    setFileCount(files.length);

    if (files.length === 0) {
      ul.innerHTML = '<li class="empty-msg">[ QUEUE EMPTY ]</li>';
      return;
    }

    files.forEach(f => {
      const li = document.createElement('li');
      li.innerHTML = `
        ${fileBadge(f.name)}
        <span class="file-name" title="${f.name}">${f.name}</span>
        <span class="file-size">${formatBytes(f.size)}</span>
        <span class="file-actions">
          <button class="btn-print print-btn" data-name="${f.name}">&#9654; PRINT</button>
          <button class="btn-del   del-btn"   data-name="${f.name}">&#9249; DEL</button>
        </span>
      `;
      ul.appendChild(li);
    });

    ul.querySelectorAll('.print-btn').forEach(btn =>
      btn.addEventListener('click', () => printFile(btn.dataset.name, btn)));

    ul.querySelectorAll('.del-btn').forEach(btn =>
      btn.addEventListener('click', () => deleteFile(btn.dataset.name)));

  } catch {
    ul.innerHTML = '<li class="empty-msg">[ ERROR LOADING QUEUE ]</li>';
  }
}

// ── Print ──────────────────────────────────────────────────────────────────

async function printFile(name, btn) {
  const printer  = document.getElementById('printer-dropdown').value;
  const pageFrom = parseInt(document.getElementById('page-from').value, 10) || null;
  const pageTo   = parseInt(document.getElementById('page-to').value, 10)   || null;

  if (btn) { btn.disabled = true; btn.textContent = 'SENDING…'; }

  // Show indeterminate print progress bar in the parent list item
  let progressEl = null;
  if (btn) {
    const li = btn.closest('li');
    if (li) {
      progressEl = document.createElement('div');
      progressEl.className = 'print-progress-wrap';
      progressEl.innerHTML = '<div class="print-progress-bar"></div>';
      li.appendChild(progressEl);
    }
  }

  try {
    const res = await fetch(`/print/${encodeURIComponent(name)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ printer: printer || null, page_from: pageFrom, page_to: pageTo }),
    });
    const data = await res.json();
    showToast(data.message, data.success ? 'ok' : 'error');
    if (data.success) loadFiles();
  } catch {
    showToast('NETWORK ERROR — PRINT JOB FAILED', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '▶ PRINT'; }
    if (progressEl) progressEl.remove();
  }
}

// ── Delete ─────────────────────────────────────────────────────────────────

async function deleteFile(name) {
  if (!confirm(`DELETE: ${name} ?`)) return;

  try {
    const res = await fetch(`/file/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (res.status === 204) {
      showToast(`DELETED: ${name}`);
      loadFiles();
    } else {
      const data = await res.json();
      showToast(data.error || 'DELETE FAILED', 'error');
    }
  } catch {
    showToast('NETWORK ERROR — DELETE FAILED', 'error');
  }
}

// ── Upload ─────────────────────────────────────────────────────────────────

function uploadFiles(fileList) {
  const progressContainer = document.getElementById('upload-progress');

  Array.from(fileList).forEach(file => {
    const wrapper = document.createElement('div');
    wrapper.className = 'progress-item';
    wrapper.innerHTML = `
      <div class="p-name">&gt; ${file.name}</div>
      <div class="progress-bar-wrap"><div class="progress-bar" style="width:0%"></div></div>
    `;
    progressContainer.appendChild(wrapper);
    const bar = wrapper.querySelector('.progress-bar');

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload');

    xhr.upload.onprogress = ev => {
      if (ev.lengthComputable) {
        bar.style.width = Math.round((ev.loaded / ev.total) * 100) + '%';
      }
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        bar.style.width = '100%';
        showToast(`UPLOADED: ${file.name}`);
        loadFiles();
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          showToast(err.error || 'UPLOAD FAILED', 'error');
        } catch {
          showToast('UPLOAD FAILED', 'error');
        }
      }
      setTimeout(() => wrapper.remove(), 1800);
    };

    xhr.onerror = () => {
      showToast(`UPLOAD ERROR: ${file.name}`, 'error');
      wrapper.remove();
    };

    xhr.send(formData);
  });
}

// ── Drag & Drop ────────────────────────────────────────────────────────────

function initDragDrop() {
  const dropArea = document.getElementById('drop-area');

  ['dragenter', 'dragover'].forEach(evt =>
    dropArea.addEventListener(evt, e => {
      e.preventDefault();
      e.stopPropagation();
      dropArea.classList.add('highlight');
    })
  );

  ['dragleave', 'drop'].forEach(evt =>
    dropArea.addEventListener(evt, e => {
      e.preventDefault();
      e.stopPropagation();
      dropArea.classList.remove('highlight');
    })
  );

  dropArea.addEventListener('drop', e => {
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  });

  document.getElementById('file-input').addEventListener('change', e => {
    if (e.target.files.length) {
      uploadFiles(e.target.files);
      e.target.value = '';
    }
  });
}

// ── Init ───────────────────────────────────────────────────────────────────

initSidebarNav();
initDragDrop();
loadPrinters();
loadFiles();

document.getElementById('refresh-printers').addEventListener('click', loadPrinters);

document.getElementById('kill-jobs').addEventListener('click', async () => {
  const btn = document.getElementById('kill-jobs');
  btn.disabled = true;
  try {
    const res = await fetch('/jobs/cancel', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, data.success ? 'ok' : 'error');
    if (data.success) loadFiles();
  } catch {
    showToast('NETWORK ERROR — KILL FAILED', 'error');
  } finally {
    btn.disabled = false;
  }
});
