// Insights (ADR-0008). CSP-konform: keine Inline-Handler.
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

const REPORT_HEADINGS = new Set(['Zusammenfassung', 'Kennzahlen', 'Einordnung', 'Hinweis']);

// Markdown-Fett rendern; esc() laeuft ZUERST, der Inhalt ist also schon sicher.
export function mdInline(s) {
    return esc(s).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

function renderBody(body) {
    return String(body || '')
        .split(/(?=^(?:Zusammenfassung|Kennzahlen|Einordnung|Hinweis)$)/m)
        .filter((section) => section.trim())
        .map((section) => {
            const [heading, ...lines] = section.trim().split(/\r?\n/);
            if (!REPORT_HEADINGS.has(heading)) {
                return `<p class="insight-body whitespace-pre-line">${mdInline(section)}</p>`;
            }
            const content = lines.join('\n').trim();
            const items = content.split(/\r?\n/).filter((line) => line.trim());
            const bodyHtml =
                heading === 'Kennzahlen' && items.every((line) => line.startsWith('- '))
                    ? `<ul class="list-disc pl-5 space-y-1">${items.map((line) => `<li>${mdInline(line.slice(2))}</li>`).join('')}</ul>`
                    : `<p class="insight-body whitespace-pre-line">${mdInline(content)}</p>`;
            return `<section class="mb-4"><h2 class="text-sm font-semibold mb-2">${esc(heading)}</h2>${bodyHtml}</section>`;
        })
        .join('');
}

export function renderInsight(data) {
    if (!data) return '';
    const text = data.text || {};
    const badge =
        text.generator === 'llm'
            ? `KI-generiert${text.model_id ? ` · ${esc(text.model_id)}` : ''}`
            : 'Standardtext (Fallback)';
    return `${renderBody(text.body)}<p class="insight-badge text-xs text-slate-500 mt-2">${esc(badge)}</p>`;
}

export function visibleReport(data) {
    return data?.status === 'ready' ? data : (data?.report ?? null);
}

export function statusMessage(data) {
    if (!data || data.status === 'ready') return '';
    const period = periodRangeLabel(data.period_start, data.period_end);
    const previous = data.report ? ' Der letzte fertige Bericht bleibt sichtbar.' : '';
    if (data.status === 'pending') return `Der Bericht für ${period} wird erstellt.${previous}`;
    if (data.status === 'failed') return `Der Bericht für ${period} konnte nicht erstellt werden.${previous}`;
    return `Für ${period} ist noch kein neuer Bericht verfügbar. Die Erstellung ist täglich um 05:00 Uhr (Wien) geplant.${previous}`;
}

const REPORT_CLOCK = new Intl.DateTimeFormat('de-AT', {
    timeZone: 'Europe/Vienna',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hourCycle: 'h23',
});

function viennaClock(now) {
    const parts = Object.fromEntries(
        REPORT_CLOCK.formatToParts(now)
            .filter(({ type }) => type !== 'literal')
            .map(({ type, value }) => [type, value]),
    );
    return { day: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour) };
}

export function shouldRefreshAtFive(lastRefreshDay, now) {
    const { day, hour } = viennaClock(now);
    return hour >= 5 && lastRefreshDay !== day;
}

// --- DOM-Anbindung ------------------------------------------------------- //

const state = {
    data: null,
};

let pollTimer = null;
let dailyRefreshDay = null;

function setRangeLabel(data) {
    const el = document.getElementById('ins-week');
    if (!el) return;
    const report = visibleReport(data);
    if (report) {
        el.textContent = `Bericht · ${periodRangeLabel(report.period_start, report.period_end)}`;
    } else {
        el.textContent = `Zeitraum · ${periodRangeLabel(data.period_start, data.period_end)}`;
    }
}

function paint(data) {
    const status = document.getElementById('ins-status');
    if (status) {
        status.textContent = statusMessage(data);
        status.hidden = data.status === 'ready';
    }
    const el = document.getElementById('ins-content');
    const report = visibleReport(data);
    if (el) {
        el.innerHTML = report
            ? renderInsight(report)
            : '<p class="text-sm text-slate-500">Noch kein Bericht vorhanden.</p>';
    }
    setRangeLabel(data);
}

function schedulePoll() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(load, 5000);
}

async function load() {
    const el = document.getElementById('ins-content');
    if (el && !visibleReport(state.data)) {
        el.innerHTML = '<p class="text-sm text-slate-500">Lade Auswertung…</p>';
    }
    try {
        const res = await fetch('/api/insights');
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        state.data = data;
        paint(data);
        if (data.status === 'pending') schedulePoll();
        else clearTimeout(pollTimer);
    } catch (_) {
        if (visibleReport(state.data)) {
            const status = document.getElementById('ins-status');
            if (status) {
                status.textContent = 'Der Bericht konnte nicht aktualisiert werden.';
                status.hidden = false;
            }
        } else if (el) {
            el.innerHTML = '<p class="text-sm text-red-500">Konnte Insights nicht laden.</p>';
        }
        clearTimeout(pollTimer);
    }
}

function refreshAtFive() {
    const now = new Date();
    if (shouldRefreshAtFive(dailyRefreshDay, now)) {
        dailyRefreshDay = viennaClock(now).day;
        load();
    }
    setTimeout(refreshAtFive, 60000 - (Date.now() % 60000) + 200);
}

function init() {
    const now = new Date();
    if (viennaClock(now).hour >= 5) dailyRefreshDay = viennaClock(now).day;
    load();
    refreshAtFive();
}

if (typeof document !== 'undefined' && document.getElementById('ins-content')) {
    init();
}
