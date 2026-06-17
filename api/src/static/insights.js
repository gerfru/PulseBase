// Wochen-Insights (ADR-0003, P6). CSP-konform: keine Inline-Handler.
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

// --- ISO-Wochen-Helfer (pure, testbar) ----------------------------------- //

export function isoWeekStart(year, week) {
    // Montag der gegebenen ISO-Woche (ISO-Woche 1 enthaelt den 4. Januar).
    const jan4 = new Date(Date.UTC(year, 0, 4));
    const dow = (jan4.getUTCDay() + 6) % 7; // Mo=0
    const mondayW1 = new Date(jan4);
    mondayW1.setUTCDate(jan4.getUTCDate() - dow);
    const d = new Date(mondayW1);
    d.setUTCDate(mondayW1.getUTCDate() + (week - 1) * 7);
    return d;
}

export function isoYearWeek(d) {
    const date = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    const dayNum = (date.getUTCDay() + 6) % 7; // Mo=0
    date.setUTCDate(date.getUTCDate() - dayNum + 3); // Donnerstag der Woche
    const firstThu = new Date(Date.UTC(date.getUTCFullYear(), 0, 4));
    const fDow = (firstThu.getUTCDay() + 6) % 7;
    firstThu.setUTCDate(firstThu.getUTCDate() - fDow + 3);
    const week = 1 + Math.round((date - firstThu) / (7 * 86400000));
    return [date.getUTCFullYear(), week];
}

export function shiftWeek(year, week, delta) {
    const mon = isoWeekStart(year, week);
    mon.setUTCDate(mon.getUTCDate() + delta * 7);
    return isoYearWeek(mon);
}

// --- Render (pure, testbar) ---------------------------------------------- //

export function renderInsight(data, segment) {
    if (!data) return '';
    const text = data.texts?.[segment] || {};
    const metrics = (data.insight?.metrics || [])
        .map((m) => {
            const chg = m.change_pct != null ? ` (${esc(m.change_pct)} %)` : '';
            return (
                `<li><span class="font-medium">${esc(m.key)}</span>: ` +
                `${esc(m.value)} ${esc(m.unit)}${chg} — ${esc(m.trend)}</li>`
            );
        })
        .join('');
    const badge =
        text.generator === 'llm'
            ? `KI-generiert${text.model_id ? ` · ${esc(text.model_id)}` : ''}`
            : 'Standardtext (Fallback)';
    return (
        `<ul class="insight-metrics mb-3">${metrics || '<li>Keine Kennzahlen.</li>'}</ul>` +
        `<p class="insight-body whitespace-pre-line">${esc(text.body || '')}</p>` +
        `<p class="insight-badge text-xs text-slate-500 mt-2">${esc(badge)}</p>`
    );
}

// --- DOM-Anbindung ------------------------------------------------------- //

const state = { year: null, week: null, data: null, segment: 'hobby' };
const PENDING_HTML =
    '<p class="text-sm text-slate-500">Deine Wochen-Auswertung wird gerade ' +
    'erstellt — beim ersten Mal kann das einen Moment dauern. Die Seite ' +
    'aktualisiert sich automatisch, sobald sie fertig ist. 🙏</p>';

let pollTimer = null;
let waitingSince = null; // created_at, das eine Regenerierung uebertreffen muss

function setWeekLabel() {
    const wk = document.getElementById('ins-week');
    if (wk && state.year) wk.textContent = `KW ${state.week} · ${state.year}`;
}

function paint() {
    if (!state.data) return;
    const el = document.getElementById('ins-content');
    if (el) el.innerHTML = renderInsight(state.data, state.segment);
    setWeekLabel();
}

function showPending() {
    const el = document.getElementById('ins-content');
    if (el) el.innerHTML = PENDING_HTML;
    setWeekLabel();
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
    const q = state.year ? `?iso_year=${state.year}&iso_week=${state.week}` : '';
    try {
        const res = await fetch(`/api/insights${q}`);
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        state.year = data.iso_year;
        state.week = data.iso_week;
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
        const res = await fetch('/api/insights/regenerate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ iso_year: state.year, iso_week: state.week }),
        });
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

function goto(delta) {
    [state.year, state.week] = shiftWeek(state.year, state.week, delta);
    state.data = null; // neue Woche → Ladeanzeige
    load();
}

function init() {
    document.getElementById('ins-prev')?.addEventListener('click', () => goto(-1));
    document.getElementById('ins-next')?.addEventListener('click', () => goto(1));
    document.getElementById('ins-regen')?.addEventListener('click', regenerate);
    document.querySelectorAll('.ins-seg').forEach((b) => {
        b.addEventListener('click', () => setSegment(b.dataset.seg));
    });
    load();
}

if (typeof document !== 'undefined' && document.getElementById('ins-content')) {
    init();
}
