const SEVERITY_LABELS = ['', 'Sehr leicht', 'Leicht', 'Mittel', 'Schwer', 'Sehr schwer'];
let selectedSeverity = null;
let editingId = null;
let pendingDeleteId = null;
const _eventsById = new Map();

export function esc(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

export function _resetSelectedSeverity() {
    selectedSeverity = null;
    editingId = null;
}

export function _getEditingId() {
    return editingId;
}

export function renderSeverityChips() {
    const container = document.getElementById('severity-chips');
    container.innerHTML = '';
    for (let i = 1; i <= 5; i++) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = i;
        btn.title = SEVERITY_LABELS[i];
        btn.className = [
            'w-9 h-9 rounded-full text-sm font-semibold border transition-colors',
            selectedSeverity === i
                ? 'bg-violet-500 border-violet-500 text-white'
                : 'bg-black/[0.04] dark:bg-white/[0.06] border-black/10 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:border-violet-400',
        ].join(' ');
        btn.addEventListener('click', () => {
            selectedSeverity = selectedSeverity === i ? null : i;
            renderSeverityChips();
        });
        container.appendChild(btn);
    }
    const label = document.createElement('span');
    label.className = 'text-xs text-slate-400 self-center ml-1';
    label.textContent = selectedSeverity ? SEVERITY_LABELS[selectedSeverity] : 'Keine Angabe';
    container.appendChild(label);
}

export async function loadRisk() {
    const r = await fetch('/api/seizures/risk').then((r) => r.json());
    const dot = document.getElementById('risk-dot');
    const lbl = document.getElementById('risk-label');
    const detail = document.getElementById('risk-detail');
    const flagsEl = document.getElementById('risk-flags');

    const colorMap = { ok: '#10b981', amber: '#f59e0b', red: '#ef4444' };
    const textMap = { ok: 'Kein erhöhtes Risiko', amber: 'Leicht erhöhtes Risiko', red: 'Erhöhtes Risiko' };
    dot.style.background = colorMap[r.level] || '#94a3b8';
    lbl.textContent = textMap[r.level] || r.level;
    detail.textContent = `Schlafschuld letzte 7 Nächte: ${r.sleep_debt_h}h`;

    renderRiskFlags(flagsEl, r.flags || []);
}

export function renderRiskFlags(container, flags) {
    container.innerHTML = '';
    for (const f of flags) {
        const fc = { ok: 'emerald', amber: 'amber', red: 'red' }[f.color] || 'slate';
        const row = document.createElement('div');
        row.className = `flex items-center gap-2 px-3 py-2 rounded-lg bg-${fc}-500/10 border border-${fc}-500/20`;
        const span1 = document.createElement('span');
        span1.className = `text-xs font-medium text-${fc}-400`;
        span1.textContent = f.label;
        const span2 = document.createElement('span');
        span2.className = 'text-xs text-slate-400';
        span2.textContent = f.detail;
        row.appendChild(span1);
        row.appendChild(span2);
        container.appendChild(row);
    }
}

export function formatDuration(sec) {
    if (!sec) return null;
    if (sec < 60) return `${sec}s`;
    return `${Math.floor(sec / 60)}min ${sec % 60}s`;
}

export function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleString('de-AT', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

const TYPE_LABELS = { focal: 'Fokal', generalized: 'Generalisiert', unknown: 'Unbekannt' };

export async function loadEvents() {
    const events = await fetch('/api/seizures?days=365').then((r) => r.json());
    const el = document.getElementById('event-list');
    _eventsById.clear();
    if (!events.length) {
        el.innerHTML = '<p class="text-sm text-slate-400">Noch keine Einträge.</p>';
        return;
    }
    el.innerHTML = events
        .map((e) => {
            _eventsById.set(String(e.id), e);
            const dur = formatDuration(e.duration_seconds);
            const sev = e.severity ? `${'●'.repeat(e.severity)}${'○'.repeat(5 - e.severity)}` : null;
            return `<div class="flex flex-col gap-1 px-4 py-3 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
            <div class="flex items-center gap-2">
                <span class="text-sm font-medium text-slate-700 dark:text-slate-200">${formatDate(e.occurred_at)}</span>
                <span class="text-xs px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-400">${TYPE_LABELS[e.type] || esc(e.type)}</span>
                ${dur ? `<span class="text-xs text-slate-400">${dur}</span>` : ''}
                <span class="ml-auto flex items-center gap-1">
                    <button type="button" data-edit-id="${e.id}" aria-label="Eintrag bearbeiten"
                            class="px-2 py-0.5 rounded-lg text-xs text-slate-500 dark:text-slate-400 hover:text-violet-400 hover:bg-violet-500/10 transition-colors">Bearbeiten</button>
                    <button type="button" data-del-id="${e.id}" aria-label="Eintrag löschen"
                            class="px-2 py-0.5 rounded-lg text-xs text-slate-500 dark:text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors">Löschen</button>
                </span>
            </div>
            ${sev ? `<div class="text-sm tracking-widest text-violet-400" title="Schwere ${e.severity}/5">${sev}</div>` : ''}
            ${e.notes ? `<div class="text-xs text-slate-400 mt-0.5">${esc(e.notes)}</div>` : ''}
        </div>`;
        })
        .join('');
}

function showLogError(text) {
    const err = document.getElementById('log-error');
    if (!err) return;
    err.textContent = text;
    err.style.display = 'inline';
}

function clearLogMessages() {
    const err = document.getElementById('log-error');
    if (err) {
        err.textContent = '';
        err.style.display = 'none';
    }
    const msg = document.getElementById('log-msg');
    if (msg) msg.style.display = 'none';
}

export function enterEditMode(id) {
    const e = _eventsById.get(String(id));
    if (!e) return;
    editingId = e.id;
    clearLogMessages();
    document.getElementById('occurred-at').value = new Date(e.occurred_at).toISOString().slice(0, 16);
    document.getElementById('seizure-type').value = e.type || 'unknown';
    document.getElementById('duration').value = e.duration_seconds ?? '';
    document.getElementById('notes').value = e.notes ?? '';
    selectedSeverity = e.severity ?? null;
    renderSeverityChips();

    const title = document.getElementById('log-card-title');
    if (title) title.textContent = 'Anfall bearbeiten';
    document.getElementById('log-submit').textContent = 'Aktualisieren';
    const cancel = document.getElementById('log-cancel');
    if (cancel) cancel.style.display = '';
    document.getElementById('occurred-at').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

export function cancelEditMode() {
    editingId = null;
    clearLogMessages();
    document.getElementById('occurred-at').value = '';
    document.getElementById('seizure-type').value = 'unknown';
    document.getElementById('duration').value = '';
    document.getElementById('notes').value = '';
    selectedSeverity = null;
    renderSeverityChips();

    const title = document.getElementById('log-card-title');
    if (title) title.textContent = 'Anfall erfassen';
    document.getElementById('log-submit').textContent = 'Speichern';
    const cancel = document.getElementById('log-cancel');
    if (cancel) cancel.style.display = 'none';
}

export async function logSeizure() {
    clearLogMessages();
    const occurredAt = document.getElementById('occurred-at').value;
    if (!occurredAt) {
        showLogError('Bitte Datum und Uhrzeit angeben.');
        return;
    }
    const body = {
        occurred_at: new Date(occurredAt).toISOString(),
        type: document.getElementById('seizure-type').value,
        duration_seconds: parseInt(document.getElementById('duration').value, 10) || null,
        severity: selectedSeverity,
        notes: document.getElementById('notes').value.trim() || null,
    };
    const url = editingId ? `/api/seizures/${editingId}` : '/api/seizures';
    const method = editingId ? 'PATCH' : 'POST';
    let res;
    try {
        res = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    } catch {
        showLogError('Speichern fehlgeschlagen — bitte nochmal versuchen.');
        return;
    }
    if (!res.ok) {
        showLogError('Speichern fehlgeschlagen — bitte nochmal versuchen.');
        return;
    }

    cancelEditMode();

    const msg = document.getElementById('log-msg');
    msg.style.display = 'inline';
    setTimeout(() => {
        msg.style.display = 'none';
    }, 3000);

    await loadEvents();
}

export async function deleteSeizure(id) {
    let res;
    try {
        res = await fetch(`/api/seizures/${id}`, { method: 'DELETE' });
    } catch {
        showLogError('Löschen fehlgeschlagen — bitte nochmal versuchen.');
        return;
    }
    if (!res.ok) {
        showLogError('Löschen fehlgeschlagen — bitte nochmal versuchen.');
        return;
    }
    if (editingId != null && String(editingId) === String(id)) cancelEditMode();
    await loadEvents();
}

function requestDelete(id) {
    pendingDeleteId = id;
    const dialog = document.getElementById('seizure-delete-confirm');
    if (dialog && typeof dialog.showModal === 'function') {
        dialog.showModal();
    } else {
        // Fallback when <dialog> is unsupported.
        deleteSeizure(id);
    }
}

document.getElementById('log-submit').addEventListener('click', logSeizure);
document.getElementById('log-cancel')?.addEventListener('click', cancelEditMode);

// Event delegation for per-entry edit/delete buttons (CSP: no inline handlers).
document.getElementById('event-list').addEventListener('click', (ev) => {
    const editBtn = ev.target.closest('[data-edit-id]');
    if (editBtn) {
        enterEditMode(editBtn.dataset.editId);
        return;
    }
    const delBtn = ev.target.closest('[data-del-id]');
    if (delBtn) requestDelete(delBtn.dataset.delId);
});

document.getElementById('seizure-delete-cancel')?.addEventListener('click', () => {
    pendingDeleteId = null;
    document.getElementById('seizure-delete-confirm')?.close();
});
document.getElementById('seizure-delete-ok')?.addEventListener('click', async () => {
    document.getElementById('seizure-delete-confirm')?.close();
    if (pendingDeleteId != null) await deleteSeizure(pendingDeleteId);
    pendingDeleteId = null;
});

// Pre-fill datetime-local to now
const now = new Date();
now.setSeconds(0, 0);
document.getElementById('occurred-at').value = now.toISOString().slice(0, 16);

renderSeverityChips();
loadRisk();
loadEvents();
