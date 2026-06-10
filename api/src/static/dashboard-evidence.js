import { esc, openFormulaDialog } from './dashboard-utils.js';

let _evidence = {};

export function getEvidence() {
    return _evidence;
}

export async function loadEvidence() {
    try {
        _evidence = await fetch('/api/evidence').then((r) => r.json());
    } catch (_) {}
}

export function openEvidenceDialog(key) {
    const e = _evidence[key];
    if (!e) return;
    const levelLabel =
        { meta: '🟢 Meta-Analyse', replicated: '🟡 Repliziert', model: '🔵 Eigenmodell' }[e.level] ?? e.level;
    const typeLabels = {
        recovery: 'Erholung',
        capacity: 'Kapazität',
        trend: 'Verlauf',
        prediction: 'Prognose',
        screening: 'Screening',
    };
    const typeBadge = e.metric_type
        ? `<span class="metric-type-chip type-${e.metric_type}">${typeLabels[e.metric_type] ?? e.metric_type}</span>`
        : '';
    const horizon = e.time_horizon ? `<p class="disclosure-horizon">⏱ ${esc(e.time_horizon)}</p>` : '';
    const intendedUse = e.intended_use
        ? `<div class="disclosure-block intended"><strong>Wofür:</strong> ${esc(e.intended_use)}</div>`
        : '';
    const notFor = e.not_for
        ? `<div class="disclosure-block not-for"><strong>Nicht geeignet für:</strong> ${esc(e.not_for)}</div>`
        : '';
    const refs = (e.refs || []).map((r) => `<li class="ml-3 list-disc">${esc(r)}</li>`).join('');
    const body = `
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:6px">
            <span class="inline-block px-2 py-0.5 rounded text-xs font-semibold ${e.level === 'meta' ? 'bg-green-100 text-green-800 dark:bg-green-700/50 dark:text-green-300' : e.level === 'replicated' ? 'bg-amber-100 text-amber-800 dark:bg-amber-700/50 dark:text-amber-300' : 'bg-sky-100 text-sky-800 dark:bg-sky-700/50 dark:text-sky-300'}">${levelLabel}</span>
            ${typeBadge}
        </div>
        ${horizon}
        ${intendedUse}
        ${notFor}
        <p class="mb-3" style="margin-top:8px">${esc(e.summary)}</p>
        ${refs ? `<ul class="mb-3 text-xs text-slate-600 dark:text-slate-400 space-y-0.5">${refs}</ul>` : ''}
        ${e.limitations ? `<p class="text-xs text-slate-600 dark:text-slate-400 border-t border-slate-200 dark:border-slate-700 pt-2"><strong class="text-slate-700 dark:text-slate-300">Einschränkungen:</strong> ${esc(e.limitations)}</p>` : ''}
        <p class="disclosure-disclaimer">Kein Ersatz für ärztliche Beratung · Keine medizinische Diagnose · Personalisierte Kalibrierung</p>`;
    openFormulaDialog(e.name || key, body, '#');
}

export function evBadge(key) {
    const e = _evidence[key];
    if (!e) return '';
    const cls = e.level === 'meta' ? 'ev-meta' : e.level === 'replicated' ? 'ev-rep' : 'ev-model';
    const short = e.level === 'meta' ? 'M' : e.level === 'replicated' ? 'R' : 'E';
    return `<button class="ev-badge ${cls}" data-ev-badge="${key}" title="${esc(e.label)}: ${esc(e.name)}">${short}</button>`;
}
