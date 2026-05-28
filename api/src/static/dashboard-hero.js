import { sparklineSvg, esc, scoreLabel, scoreColor, openFormulaDialog } from './dashboard-utils.js';

export const _heroData = {
    readiness: null, daily: null, sleep: null, hrv: null,
    trainingStatus: null, energy: null, ml: null, hrvTrend: null,
};

export let _evidence = {};

export async function loadEvidence() {
    try {
        _evidence = await fetch('/api/evidence').then(r => r.json());
    } catch (_) {}
}

export function openEvidenceDialog(key) {
    const e = _evidence[key];
    if (!e) return;
    const levelLabel = { meta: '🟢 Meta-Analyse', replicated: '🟡 Repliziert', model: '🔵 Eigenmodell' }[e.level] ?? e.level;
    const refs = (e.refs || []).map(r => `<li class="ml-3 list-disc">${esc(r)}</li>`).join('');
    const body = `
        <p class="mb-2"><span class="inline-block px-2 py-0.5 rounded text-xs font-semibold ${e.level === 'meta' ? 'bg-green-700/50 text-green-300' : e.level === 'replicated' ? 'bg-amber-700/50 text-amber-300' : 'bg-sky-700/50 text-sky-300'}">${levelLabel}</span></p>
        <p class="mb-3">${esc(e.summary)}</p>
        ${refs ? `<ul class="mb-3 text-xs text-slate-400 space-y-0.5">${refs}</ul>` : ''}
        ${e.limitations ? `<p class="text-xs text-slate-500 border-t border-slate-700 pt-2"><strong class="text-slate-400">Einschränkungen:</strong> ${esc(e.limitations)}</p>` : ''}
        <p class="text-xs text-slate-600 mt-3 border-t border-slate-700 pt-2">Methode validiert · Personalisierte Kalibrierung · Kein Ersatz für medizinische Diagnostik</p>`;
    openFormulaDialog(e.name || key, body, '#');
}

export function evBadge(key) {
    const e = _evidence[key];
    if (!e) return '';
    const cls = e.level === 'meta' ? 'ev-meta' : e.level === 'replicated' ? 'ev-rep' : 'ev-model';
    const short = e.level === 'meta' ? 'M' : e.level === 'replicated' ? 'R' : 'E';
    return `<button class="ev-badge ${cls}" data-ev-badge="${key}" title="${esc(e.label)}: ${esc(e.name)}">${short}</button>`;
}

export function buildHeroCard() {
    const el = document.getElementById('bento-hero');
    if (!el) return;

    const r         = _heroData.readiness;
    const energy    = _heroData.energy   || {};
    const daily     = _heroData.daily    || [];
    const sleep     = _heroData.sleep    || [];
    const hrv       = _heroData.hrv;
    const hrvTrend  = _heroData.hrvTrend || [];
    const ml        = _heroData.ml       || {};
    const phys      = energy.energy_physical;
    const auton     = energy.energy_autonomic;
    const cog       = energy.energy_cognitive;

    const sparkHrv    = hrvTrend.slice(-14).map(d => d.hrv_last_night);
    const sparkSleep  = sleep.slice(-14).map(d => d.sleep_score);
    const sparkBatt   = daily.slice(-14).map(d => d.body_battery_high);
    const sparkStress = daily.slice(-14).map(d => d.avg_stress);

    const score        = r?.score ?? null;
    const circumference = 218;
    const fill         = score != null ? Math.round(score / 100 * circumference) : 0;
    const ringColor    = score == null ? 'var(--muted)' : score >= 75 ? 'var(--green)' : score >= 45 ? 'var(--amber)' : 'var(--red)';

    const today     = new Date();
    const dateLabel = today.toLocaleDateString('de-AT', { weekday: 'short', day: 'numeric', month: 'long' });

    const svgRing = `<svg viewBox="0 0 120 120" class="readiness-ring">
        <circle cx="60" cy="60" r="52" fill="none" class="ring-track" stroke-width="8"
            stroke-dasharray="218 327" transform="rotate(120 60 60)"/>
        <circle cx="60" cy="60" r="52" fill="none"
            stroke="${ringColor}" stroke-width="8" stroke-linecap="round"
            stroke-dasharray="0 327" transform="rotate(120 60 60)"
            class="readiness-ring-progress" id="hero-ring-progress"/>
        <text x="60" y="56" text-anchor="middle" class="ring-score-text" id="hero-ring-score">0</text>
        <text x="60" y="72" text-anchor="middle" class="ring-label-text">Erholung${score != null ? ' · ' + scoreLabel(score) : ''}</text>
    </svg>`;

    const last    = daily.length ? daily[daily.length - 1] : null;
    const anomaly = ml.anomaly_hr;
    const rf      = ml.readiness_rf;
    const hrvSt   = ml.hrv_status_custom;
    const im      = ml.intensity_minutes_custom;

    const _hrvLabel = { BALANCED: 'Erholt', UNBALANCED: 'Leicht gedämpft', LOW: 'Niedrig', POOR: 'Stark gedämpft' };

    const rfScore = rf?.value != null ? Math.round(rf.value) : null;
    const rfSubCls = rfScore != null ? (rfScore >= 75 ? 'sub-green' : rfScore >= 50 ? 'sub-amber' : 'sub-red') : '';

    function heroRecommendation(s) {
        if (s == null) return '';
        const [text, cls] =
            s >= 80 ? ['Voll belasten — Körper ist erholt',         'rec-green']
          : s >= 60 ? ['Moderat trainieren — Erholung läuft',       'rec-amber']
          : s >= 40 ? ['Leichtes Training — Erholung bevorzugen',   'rec-amber']
          :           ['Heute ruhen — Erholung prioritär',          'rec-red'];
        return `<p class="hero-recommendation ${cls}">${text}</p>`;
    }

    function energyDots() {
        const stressRaw = ml.stress_score_custom?.score;
        const stressForColor = stressRaw != null ? (100 - stressRaw) : null;
        const stressLbl = stressRaw == null ? ''
            : stressRaw < 30 ? 'Niedrig' : stressRaw < 60 ? 'Moderat' : 'Hoch';

        const devRaw = auton?.deviation;
        const autDevLbl = devRaw != null
            ? (devRaw >= 0 ? `+${devRaw.toFixed(1)}σ` : `${devRaw.toFixed(1)}σ`)
            : null;
        const debtRaw = cog?.debt_hours;
        const cogDebtLbl = debtRaw != null
            ? (debtRaw > 0.1 ? `${debtRaw.toFixed(1)}h Schuld` : 'Kein Defizit')
            : null;

        const rows = [
            { s: auton?.score,   label: 'HRV',    href: '/metrics/autonomic',           spark: sparklineSvg(sparkHrv,   C.green,  52, 20), ctx: autDevLbl },
            { s: cog?.score,     label: 'Schlaf',  href: '/metrics/cognitive',           spark: sparklineSvg(sparkSleep, C.violet, 52, 20), ctx: cogDebtLbl },
            { s: stressForColor, label: 'Stress',  href: '/metrics/stress-score-custom', spark: sparklineSvg(sparkStress, C.orange, 52, 20), lbl: stressLbl },
        ];
        return `<span class="hero-zone-label">SIGNALE</span>
        <div class="hero-dot-row">${rows.map(({ s, label, href, spark, lbl, ctx }) => {
            const c = s == null ? 'var(--muted)'
                : s >= 70 ? 'var(--green)'
                : s >= 45 ? 'var(--amber)'
                : 'var(--red)';
            const sl = lbl !== undefined ? lbl : scoreLabel(s);
            const subtitle = ctx ?? sl;
            return `<a href="${esc(href)}" class="hero-dot-item" title="${esc(label)}: ${s ?? '—'}">
                <span class="hero-dot-circle" style="background:${c}"></span>
                ${spark}
                <span class="hero-dot-label">${esc(label)}</span>
                ${subtitle ? `<span class="hero-dot-score">${esc(subtitle)}</span>` : ''}
            </a>`;
        }).join('')}</div>`;
    }

    function todayCapacitySection() {
        const bb   = ml.body_battery_custom;
        const phys = energy.energy_physical;
        const bbScore = bb?.score  ?? null;
        const tsb     = phys?.tsb  ?? null;
        if (bbScore == null && tsb == null) return '';

        let recText, recCls;
        const bbLow    = bbScore != null && bbScore < 40;
        const tsbHeavy = tsb != null && tsb < -30;
        const tsbMod   = tsb != null && tsb >= -30 && tsb < -15;
        const tsbFresh = tsb == null || tsb >= -15;
        const bbGood   = bbScore == null || bbScore >= 60;

        if (bbLow)                     { recText = 'Aktive Erholung — Energie erschöpft';        recCls = 'rec-red';   }
        else if (tsbHeavy)             { recText = 'Leichtes Training — hohe Trainingsbelastung'; recCls = 'rec-amber'; }
        else if (bbGood && tsbFresh)   { recText = 'Intensives Training möglich';                 recCls = 'rec-green'; }
        else if (bbGood && tsbMod)     { recText = 'Normales Training';                           recCls = 'rec-green'; }
        else                           { recText = 'Leichtes bis moderates Training';              recCls = 'rec-amber'; }

        const bbCls = bbScore == null ? 'heute-muted'
            : bbScore >= 75 ? 'heute-green' : bbScore >= 40 ? 'heute-amber' : 'heute-red';
        const bbTile = bbScore != null
            ? `<a href="/metrics/body-battery-custom" class="hero-heute-item">
                   <span class="hero-heute-val ${bbCls}">${Math.round(bbScore)} %</span>
                   <span class="hero-heute-score-lbl">${scoreLabel(bbScore)}</span>
                   ${sparklineSvg(sparkBatt, C.green, 56, 18)}
                   <span class="hero-heute-label">Energie</span>
               </a>`
            : '';

        const tsbCls   = tsb == null ? 'heute-muted'
            : tsb >= -15 ? 'heute-green' : tsb >= -30 ? 'heute-amber' : 'heute-red';
        const tsbLabel = tsb == null ? '—'
            : tsb >= -15 ? 'Erholt' : tsb >= -30 ? 'Trainingsphase' : 'Hohe Last';
        const tsbStr   = tsb != null ? (tsb >= 0 ? `+${tsb.toFixed(1)}` : tsb.toFixed(1)) : '—';
        const tsbTile  = `<a href="/metrics/physical" class="hero-heute-item">
            <span class="hero-heute-val ${tsbCls}">TSB ${tsbStr}</span>
            <span class="hero-heute-label">${esc(tsbLabel)}</span>
        </a>`;

        return `<div class="hero-heute-section">
            <span class="hero-zone-label">HEUTE MÖGLICH</span>
            <div class="hero-heute-row">${bbTile}${tsbTile}</div>
            <p class="hero-recommendation ${recCls}">${recText}</p>
        </div>`;
    }

    const rfTag = rfScore != null
        ? `<span class="hero-vital-derived ${rfSubCls}">~${rfScore}<span class="hero-derived-meta"> · ML · Morgen</span></span>`
        : '';

    const ringSection = `<div class="hero-ring-section">
        ${svgRing}
    </div>`;

    el.innerHTML = `<div class="hero-header">
            <span class="hero-title">TAGESSTATUS</span>
            <span class="hero-date">${esc(dateLabel)}</span>
        </div>
        <div class="hero-grid">
            ${ringSection}
            <div class="hero-right">
                <div class="hero-ring-meta">
                    <span class="hero-ring-status">${esc(r?.label ?? '—')}</span>
                    ${heroRecommendation(score)}
                    ${energyDots()}
                    ${rfTag}
                </div>
            </div>
        </div>
        ${todayCapacitySection()}`;

    el.addEventListener('click', e => {
        const badge = e.target.closest('[data-ev-badge]');
        if (badge) { e.preventDefault(); e.stopPropagation(); openEvidenceDialog(badge.dataset.evBadge); }
    });

    if (score != null) {
        const progress = document.getElementById('hero-ring-progress');
        const scoreEl  = document.getElementById('hero-ring-score');
        requestAnimationFrame(() => {
            if (progress || scoreEl) {
                const t0 = performance.now();
                (function tick(now) {
                    const p = Math.min((now - t0) / 600, 1);
                    const f = Math.round(p * fill);
                    if (progress) progress.setAttribute('stroke-dasharray', `${f} 327`);
                    if (scoreEl) scoreEl.textContent = String(Math.round(p * score));
                    if (p < 1) requestAnimationFrame(tick);
                })(performance.now());
            }
        });
    } else {
        const scoreEl = document.getElementById('hero-ring-score');
        if (scoreEl) scoreEl.textContent = '—';
    }
}
