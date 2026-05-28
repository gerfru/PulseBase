const SEVERITY_LABELS = ['', 'Sehr leicht', 'Leicht', 'Mittel', 'Schwer', 'Sehr schwer'];
let selectedSeverity = null;

function renderSeverityChips() {
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

async function loadRisk() {
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

    flagsEl.innerHTML = '';
    for (const f of r.flags || []) {
        const fc = { ok: 'emerald', amber: 'amber', red: 'red' }[f.color] || 'slate';
        const row = document.createElement('div');
        row.className = `flex items-center gap-2 px-3 py-2 rounded-lg bg-${fc}-500/10 border border-${fc}-500/20`;
        row.innerHTML = `<span class="text-xs font-medium text-${fc}-400">${f.label}</span>
                         <span class="text-xs text-slate-400">${f.detail}</span>`;
        flagsEl.appendChild(row);
    }
}

function formatDuration(sec) {
    if (!sec) return null;
    if (sec < 60) return `${sec}s`;
    return `${Math.floor(sec / 60)}min ${sec % 60}s`;
}

function formatDate(iso) {
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

async function loadEvents() {
    const events = await fetch('/api/seizures?days=365').then((r) => r.json());
    const el = document.getElementById('event-list');
    if (!events.length) {
        el.innerHTML = '<p class="text-sm text-slate-400">Noch keine Einträge.</p>';
        return;
    }
    el.innerHTML = events
        .map((e) => {
            const dur = formatDuration(e.duration_seconds);
            const sev = e.severity ? `${'●'.repeat(e.severity)}${'○'.repeat(5 - e.severity)}` : null;
            return `<div class="flex flex-col gap-1 px-4 py-3 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
            <div class="flex items-center gap-2">
                <span class="text-sm font-medium text-slate-700 dark:text-slate-200">${formatDate(e.occurred_at)}</span>
                <span class="text-xs px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-400">${TYPE_LABELS[e.type] || e.type}</span>
                ${dur ? `<span class="text-xs text-slate-400">${dur}</span>` : ''}
            </div>
            ${sev ? `<div class="text-sm tracking-widest text-violet-400" title="Schwere ${e.severity}/5">${sev}</div>` : ''}
            ${e.notes ? `<div class="text-xs text-slate-400 mt-0.5">${e.notes.replace(/</g, '&lt;')}</div>` : ''}
        </div>`;
        })
        .join('');
}

async function logSeizure() {
    const occurredAt = document.getElementById('occurred-at').value;
    if (!occurredAt) {
        alert('Bitte Datum und Uhrzeit angeben.');
        return;
    }
    const body = {
        occurred_at: new Date(occurredAt).toISOString(),
        type: document.getElementById('seizure-type').value,
        duration_seconds: parseInt(document.getElementById('duration').value, 10) || null,
        severity: selectedSeverity,
        notes: document.getElementById('notes').value.trim() || null,
    };
    const res = await fetch('/api/seizures', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        alert('Fehler beim Speichern.');
        return;
    }

    document.getElementById('occurred-at').value = '';
    document.getElementById('seizure-type').value = 'unknown';
    document.getElementById('duration').value = '';
    document.getElementById('notes').value = '';
    selectedSeverity = null;
    renderSeverityChips();

    const msg = document.getElementById('log-msg');
    msg.style.display = 'inline';
    setTimeout(() => {
        msg.style.display = 'none';
    }, 3000);

    await loadEvents();
}

document.getElementById('log-submit').addEventListener('click', logSeizure);

// Pre-fill datetime-local to now
const now = new Date();
now.setSeconds(0, 0);
document.getElementById('occurred-at').value = now.toISOString().slice(0, 16);

renderSeverityChips();
loadRisk();
loadEvents();
