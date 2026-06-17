// Insights (ADR-0003/0004). CSP-konform: keine Inline-Handler.
// esc lokal halten — NICHT aus dashboard-utils importieren: das zieht
// chart-utils.js, das beim Eval das globale `Chart` braucht (auf /insights
// nicht geladen) und die ganze Modul-Kette werfen liesse.
function esc(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// --- Datums-Helfer (pure, testbar) --------------------------------------- //

function _ddmm(iso) {
    const parts = String(iso).split('-'); // "YYYY-MM-DD"
    return parts.length === 3 ? `${parts[2]}.${parts[1]}.` : String(iso);
}

// Spanne aus ISO-Date-Strings, z. B. "08.06.–14.06.".
export function periodRangeLabel(startIso, endIso) {
    return `${_ddmm(startIso)}–${_ddmm(endIso)}`;
}

// --- Render (pure, testbar) ---------------------------------------------- //

const METRIC_LABEL = {
    readiness: 'Erholung',
    sleep: 'Schlaf',
    training_form: 'Trainingsform',
    stress: 'Stress',
    body_battery: 'Body Battery',
    hrv: 'HRV',
    training_volume: 'Trainingsvolumen',
    time_in_range: 'Zeit im Zielbereich',
};
const TREND_ARROW = {
    up: '↑',
    slightly_up: '↗',
    stable: '→',
    slightly_down: '↘',
    down: '↓',
};

// Markdown-Fett rendern; esc() laeuft ZUERST, der Inhalt ist also schon sicher.
export function mdInline(s) {
    return esc(s).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

export function renderInsight(data, segment) {
    if (!data) return '';
    const text = data.texts?.[segment] || {};
    const metrics = (data.insight?.metrics || [])
        .map((m) => {
            const label = METRIC_LABEL[m.key] || m.key;
            const chg = m.change_pct != null ? ` (${esc(m.change_pct)} %)` : '';
            const arrow = TREND_ARROW[m.trend] || '';
            return (
                `<li><span class="font-medium">${esc(label)}</span>: ` +
                `${esc(m.value)} ${esc(m.unit)}${chg} ${arrow}</li>`
            );
        })
        .join('');
    const badge =
        text.generator === 'llm'
            ? `KI-generiert${text.model_id ? ` · ${esc(text.model_id)}` : ''}`
            : 'Standardtext (Fallback)';
    return (
        `<ul class="insight-metrics mb-3">${metrics || '<li>Keine Kennzahlen.</li>'}</ul>` +
        `<p class="insight-body whitespace-pre-line">${mdInline(text.body || '')}</p>` +
        `<p class="insight-badge text-xs text-slate-500 mt-2">${esc(badge)}</p>`
    );
}

// --- DOM-Anbindung ------------------------------------------------------- //

const state = {
    periodStart: null,
    periodEnd: null,
    data: null,
    segment: 'hobby',
};
const PENDING_HTML =
    '<p class="text-sm text-slate-500">Deine Auswertung wird gerade erstellt — ' +
    'beim ersten Mal kann das einen Moment dauern. Die Seite aktualisiert sich ' +
    'automatisch, sobald sie fertig ist. 🙏</p>';

let pollTimer = null;
let waitingSince = null; // created_at, das eine Regenerierung uebertreffen muss

function setRangeLabel() {
    const el = document.getElementById('ins-week');
    if (el && state.periodStart && state.periodEnd) {
        el.textContent = `Letzte 7 Tage · ${periodRangeLabel(state.periodStart, state.periodEnd)}`;
    }
}

function paint() {
    if (!state.data) return;
    const el = document.getElementById('ins-content');
    if (el) el.innerHTML = renderInsight(state.data, state.segment);
    setRangeLabel();
}

function showPending() {
    const el = document.getElementById('ins-content');
    if (el) el.innerHTML = PENDING_HTML;
    setRangeLabel();
}

function schedulePoll() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(load, 5000);
}

async function load() {
    const el = document.getElementById('ins-content');
    if (el && !state.data) {
        el.innerHTML = '<p class="text-sm text-slate-500">Lade Auswertung…</p>';
    }
    try {
        const res = await fetch('/api/insights');
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        state.periodStart = data.period_start;
        state.periodEnd = data.period_end;
        const stale = waitingSince && data.created_at === waitingSince;
        if (data.status === 'pending' || stale) {
            showPending();
            schedulePoll();
            return;
        }
        waitingSince = null;
        clearTimeout(pollTimer);
        state.data = data;
        paint();
    } catch (_) {
        if (el) {
            el.innerHTML = '<p class="text-sm text-red-500">Konnte Insights nicht laden.</p>';
        }
    }
}

async function regenerate() {
    const btn = document.getElementById('ins-regen');
    if (btn) btn.disabled = true;
    waitingSince = state.data?.created_at || null;
    try {
        const res = await fetch('/api/insights/regenerate', { method: 'POST' });
        if (res.ok) {
            showPending();
            schedulePoll();
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

function setSegment(seg) {
    state.segment = seg;
    document.querySelectorAll('.ins-seg').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.seg === seg));
    });
    paint();
}

function init() {
    document.getElementById('ins-regen')?.addEventListener('click', regenerate);
    document.querySelectorAll('.ins-seg').forEach((b) => {
        b.addEventListener('click', () => setSegment(b.dataset.seg));
    });
    load();
}

if (typeof document !== 'undefined' && document.getElementById('ins-content')) {
    init();
}
