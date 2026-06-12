/* global C */
import { sparklineSvg, esc, scoreColor, scoreLabel, EV_LEVEL_SHORT, EV_LEVEL_CLS } from './dashboard-utils.js';
import { feedbackButtons } from './dashboard-ml-feedback.js';
import { getEvidence, openEvidenceDialog } from './dashboard-evidence.js';
export { applyFeedbackState, loadMlFeedback, submitMlFeedback } from './dashboard-ml-feedback.js';
export { loadEvidence, openEvidenceDialog, evBadge } from './dashboard-evidence.js';

export const _heroData = {
    readiness: null,
    daily: null,
    sleep: null,
    hrv: null,
    trainingStatus: null,
    energy: null,
    ml: null,
    hrvTrend: null,
};

// ── Kuratierte „Deine Metriken"-Leiste (Phase 2) ─────────────────────────────
// Eigen-Metriken, die die Hero-Card NICHT zeigt. Werte aus bereits geladenem
// _heroData.ml (/api/ml-insights), Evidence aus _evidence (/api/evidence) → kein
// zusätzlicher Request. Render rein aus eigenen Daten: kein Inline-Handler, keine
// Fremddaten in innerHTML, alle Interpolationen via esc() → CSP-/XSS-sicher.
const CURATED = [
    {
        name: 'training-monotony',
        title: 'Training Monotony',
        icon: '🔁',
        evKey: 'training_monotony',
        val: (d) => d.training_monotony?.monotony?.toFixed(2),
        unit: '',
    },
    {
        name: 'sleep-consistency',
        title: 'Schlaf-Konsistenz',
        icon: '🌙',
        evKey: 'sleep_consistency',
        val: (d) => d.sleep_consistency?.score?.toFixed(0),
        unit: '',
    },
    {
        name: 'hrv-recovery',
        title: 'HRV Recovery',
        icon: '⬆️',
        evKey: 'hrv_recovery',
        val: (d) => d.hrv_recovery?.recovery_speed?.toFixed(1),
        unit: ' HRV/d',
    },
    {
        name: 'spo2-trend',
        title: 'SpO₂ Trend',
        icon: '🩸',
        evKey: 'spo2_trend',
        val: (d) => d.spo2_trend?.mean_spo2?.toFixed(1),
        unit: ' %',
    },
    {
        name: 'running-economy',
        title: 'Running Economy',
        icon: '🏃',
        evKey: 'running_economy',
        val: (d) => d.running_economy?.score?.toFixed(0),
        unit: '',
    },
];

export function buildCuratedMetrics() {
    const section = document.getElementById('curated-metrics');
    const grid = document.getElementById('curated-metrics-grid');
    if (!section || !grid) return;
    const ml = _heroData.ml || {};
    const ev = getEvidence();

    const tiles = CURATED.map((item) => {
        let valStr = '—';
        try {
            const v = item.val(ml);
            valStr = v != null ? String(v) + item.unit : '—';
        } catch (_) {}
        const color = scoreColor(valStr);
        const e = item.evKey ? ev[item.evKey] : null;
        const badge = e
            ? `<span class="ev-badge ${EV_LEVEL_CLS[e.level] ?? 'ev-model'}" title="${esc(e.label ?? '')}: ${esc(e.name ?? '')}">${EV_LEVEL_SHORT[e.level] ?? '?'}</span>`
            : '';
        const horizon = e?.time_horizon ? `<span class="metric-horizon">${esc(e.time_horizon)}</span>` : '';
        return `<a href="/metrics/${esc(item.name)}" class="metric-overview-tile card">
            <div style="display:flex;align-items:center;justify-content:space-between">
                <span class="metric-overview-icon">${esc(item.icon)}</span>
                ${badge}
            </div>
            <span class="metric-overview-title">${esc(item.title)}</span>
            <span class="metric-overview-val" style="color:${color}">${esc(valStr)}</span>
            ${horizon}
        </a>`;
    }).join('');

    grid.innerHTML = tiles;
    section.hidden = false;
}

function _tileCls(s) {
    return s == null ? 'heute-muted' : s >= 70 ? 'heute-green' : s >= 45 ? 'heute-amber' : 'heute-red';
}

function _signalTiles(auton, cog, ml, sparkHrv, sparkSleep, sparkStress) {
    const stressRaw = ml.stress_score_custom?.score;
    const stressForColor = stressRaw != null ? 100 - stressRaw : null;
    const stressLbl = stressRaw == null ? '—' : stressRaw < 30 ? 'Niedrig' : stressRaw < 60 ? 'Moderat' : 'Hoch';
    const devRaw = auton?.deviation;
    const autDevLbl = devRaw != null ? (devRaw >= 0 ? `+${devRaw.toFixed(1)}σ` : `${devRaw.toFixed(1)}σ`) : '—';
    const debtRaw = cog?.debt_hours;
    const cogDebtLbl = debtRaw != null ? (debtRaw > 0.1 ? `${debtRaw.toFixed(1)}h Schuld` : 'Kein Defizit') : '—';

    return [
        {
            label: 'HRV',
            href: '/metrics/autonomic',
            s: auton?.score,
            val: autDevLbl,
            spark: sparkHrv,
            col: C.green,
            horizon: 'Heute Nacht · 90T-Basis',
        },
        {
            label: 'Schlaf',
            href: '/metrics/cognitive',
            s: cog?.score,
            val: cogDebtLbl,
            spark: sparkSleep,
            col: C.violet,
            horizon: '7-Tage kumulativ',
        },
        {
            label: 'Stress',
            href: '/metrics/stress-score-custom',
            s: stressForColor,
            val: stressLbl,
            spark: sparkStress,
            col: C.orange,
            horizon: 'Heute · Tageswert',
        },
    ]
        .map(
            ({ label, href, s, val, spark, col, horizon }) =>
                `<a href="${esc(href)}" class="hero-heute-item">
            <span class="hero-heute-val ${_tileCls(s)}" style="font-size:1.05rem">${esc(val)}</span>
            ${sparklineSvg(spark, col, 56, 16)}
            <span class="hero-heute-label">${esc(label)}</span>
            <span class="metric-horizon">${esc(horizon)}</span>
        </a>`,
        )
        .join('');
}

function _capacityTilesOnly(_bbScore, _tsb, sparkBatt) {
    const bbTile =
        _bbScore != null
            ? `<a href="/metrics/body-battery-custom" class="hero-heute-item">
            <span class="hero-heute-val ${_tileCls(_bbScore)}" style="font-size:1.05rem">${Math.round(_bbScore)} %</span>
            ${sparklineSvg(sparkBatt, C.green, 56, 16)}
            <span class="hero-heute-label">Energie</span>
            <span class="metric-horizon">Heute · Snapshot</span>
        </a>`
            : '';
    const tsbCls =
        _tsb == null ? 'heute-muted' : _tsb >= -15 ? 'heute-green' : _tsb >= -30 ? 'heute-amber' : 'heute-red';
    const tsbStr = _tsb != null ? (_tsb >= 0 ? `+${_tsb.toFixed(1)}` : _tsb.toFixed(1)) : '—';
    const tsbLbl = _tsb == null ? '—' : _tsb >= -15 ? 'Erholt' : _tsb >= -30 ? 'Trainingsphase' : 'Hohe Last';
    const tsbTile =
        _tsb != null
            ? `<a href="/metrics/physical" class="hero-heute-item">
            <span class="hero-heute-val ${tsbCls}" style="font-size:1.05rem">TSB ${esc(tsbStr)}</span>
            <span class="hero-heute-score-lbl">${esc(tsbLbl)}</span>
            <span class="hero-heute-label">Trainingsform</span>
            <span class="metric-horizon">42-Tage-Verlauf</span>
        </a>`
            : '';
    return bbTile + tsbTile;
}

function _animateRing(progress, scoreEl, fill, score) {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) {
        if (progress) progress.setAttribute('stroke-dasharray', `${fill} 327`);
        if (scoreEl) scoreEl.textContent = String(score);
    } else {
        requestAnimationFrame(() => {
            if (progress || scoreEl) {
                const t0 = performance.now();
                (function tick(now) {
                    const p = Math.min((now - t0) / 600, 1);
                    const eased = 1 - (1 - p) ** 3;
                    const f = Math.round(eased * fill);
                    if (progress) progress.setAttribute('stroke-dasharray', `${f} 327`);
                    if (scoreEl) scoreEl.textContent = String(Math.round(eased * score));
                    if (p < 1) requestAnimationFrame(tick);
                })(performance.now());
            }
        });
    }
}

export function heroRecommendation(s) {
    if (s == null) return '';
    const [text, cls] =
        s >= 75
            ? ['Deutet auf gute Erholung hin — intensives Training wäre möglich', 'rec-green']
            : s >= 60
              ? ['Erholung läuft — moderates Training wäre passend', 'rec-amber']
              : s >= 40
                ? ['Erholung scheint noch im Gang — eher leicht trainieren', 'rec-amber']
                : ['Deutet auf eingeschränkte Erholung — heute eher ruhen', 'rec-red'];
    return `<p class="hero-recommendation ${cls}">${text}</p>`;
}

export function buildHeroCard() {
    const el = document.getElementById('bento-hero');
    if (!el) return;

    const r = _heroData.readiness;
    const energy = _heroData.energy || {};
    const daily = _heroData.daily || [];
    const sleep = _heroData.sleep || [];
    const _hrv = _heroData.hrv;
    const hrvTrend = _heroData.hrvTrend || [];
    const ml = _heroData.ml || {};
    const _phys = energy.energy_physical;
    const auton = energy.energy_autonomic;
    const cog = energy.energy_cognitive;

    const sparkHrv = hrvTrend.slice(-14).map((d) => d.hrv_last_night);
    const sparkSleep = sleep.slice(-14).map((d) => d.sleep_score);
    const sparkBatt = daily.slice(-14).map((d) => d.body_battery_high);
    const sparkStress = daily.slice(-14).map((d) => d.avg_stress);

    const score = r?.score ?? null;
    const circumference = 218;
    const fill = score != null ? Math.round((score / 100) * circumference) : 0;
    const ringColor =
        score == null ? 'var(--muted)' : score >= 75 ? 'var(--green)' : score >= 45 ? 'var(--amber)' : 'var(--red)';

    const today = new Date();
    const dateLabel = today.toLocaleDateString('de-AT', { weekday: 'short', day: 'numeric', month: 'long' });

    const svgRing = `<svg viewBox="0 0 120 120" class="readiness-ring">
        <circle cx="60" cy="60" r="52" fill="none" class="ring-track" stroke-width="8"
            stroke-dasharray="218 327" transform="rotate(120 60 60)"/>
        <circle cx="60" cy="60" r="52" fill="none"
            stroke="${ringColor}" stroke-width="8" stroke-linecap="round"
            stroke-dasharray="0 327" transform="rotate(120 60 60)"
            class="readiness-ring-progress" id="hero-ring-progress"/>
        <text x="60" y="56" text-anchor="middle" class="ring-score-text" id="hero-ring-score">0</text>
        <text x="60" y="72" text-anchor="middle" class="ring-label-text">Erholung${score != null ? ` · ${scoreLabel(score)}` : ''}</text>
    </svg>`;

    const _last = daily.length ? daily[daily.length - 1] : null;
    const _anomaly = ml.anomaly_hr;
    const rf = ml.readiness_rf;
    const _hrvSt = ml.hrv_status_custom;
    const _im = ml.intensity_minutes_custom;

    const _hrvLabel = { BALANCED: 'Erholt', UNBALANCED: 'Leicht gedämpft', LOW: 'Niedrig', POOR: 'Stark gedämpft' };

    const rfScore = rf?.value != null ? Math.round(rf.value) : null;
    const rfLo = rf?.confidence_low != null ? Math.round(rf.confidence_low) : null;
    const rfHi = rf?.confidence_high != null ? Math.round(rf.confidence_high) : null;
    const rfSubCls =
        rfScore != null ? (rfScore >= 75 ? 'heute-green' : rfScore >= 50 ? 'heute-amber' : 'heute-red') : '';

    // Capacity recommendation (displayed in HEUTE MÖGLICH header)
    let capRecText = '',
        capRecCls = '';
    const _bb = ml.body_battery_custom;
    const _bbScore = _bb?.score ?? null;
    const _tsb = _phys?.tsb ?? null;
    if (_bbScore != null || _tsb != null) {
        const bbLow = _bbScore != null && _bbScore < 40;
        const tsbHeavy = _tsb != null && _tsb < -30;
        const tsbMod = _tsb != null && _tsb >= -30 && _tsb < -15;
        const tsbFresh = _tsb == null || _tsb >= -15;
        const bbGood = _bbScore == null || _bbScore >= 60;
        if (bbLow) {
            capRecText = 'Aktive Erholung';
            capRecCls = 'rec-red';
        } else if (tsbHeavy) {
            capRecText = 'Leichtes Training';
            capRecCls = 'rec-amber';
        } else if (bbGood && tsbFresh) {
            capRecText = 'Intensives Training';
            capRecCls = 'rec-green';
        } else if (bbGood && tsbMod) {
            capRecText = 'Normales Training';
            capRecCls = 'rec-green';
        } else {
            capRecText = 'Moderates Training';
            capRecCls = 'rec-amber';
        }
    }

    const minSamplesMet = ml.min_samples_met !== false;
    const nSamples = ml.n_samples ?? 0;
    const mlTile =
        rfScore != null
            ? `<a href="/metrics/readiness-rf" class="hero-heute-item">
            <span class="hero-heute-val ${rfSubCls}" style="font-size:1.05rem">~${rfScore}</span>
            <span class="hero-heute-score-lbl">KI-Prognose</span>
            <span class="hero-heute-label">Readiness Morgen</span>
            ${rfLo != null && rfHi != null ? `<span class="metric-horizon">Spanne ${rfLo}–${rfHi}</span>` : ''}
            ${!minSamplesMet ? `<span class="metric-horizon" style="color:var(--amber)">Noch ${30 - nSamples} Trainingstage bis Modell aktiv</span>` : ''}
            <span class="metric-horizon">Prognose · Morgen</span>
        </a>`
            : '';

    // Conflict explainer: battery pattern "erschoepft" while readiness is good
    const _bp = ml.battery_pattern;
    const conflictInfo =
        _bp?.pattern === 'erschoepft' && score != null && score >= 60
            ? `<span class="metric-conflict-info" title="Battery-Muster beschreibt die letzten Wochen. Readiness misst heute Nacht.">ⓘ Verschiedene Zeiträume</span>`
            : '';

    el.innerHTML = `<div class="hero-header">
            <span class="hero-title">TAGESSTATUS</span>
            <span class="hero-date">${esc(dateLabel)}</span>
        </div>
        <div class="hero-grid">
            <div class="hero-ring-panel">
                ${svgRing}
                <div class="hero-ring-meta">
                    <span class="hero-ring-status">${esc(r?.label ?? '—')}</span>
                    ${heroRecommendation(score)}
                </div>
            </div>
            <div class="hero-right-panel">
                <div class="hero-capacity-header" style="margin-bottom:4px">
                    <span class="hero-section-label">ERHOLUNGSSIGNALE</span>
                    ${conflictInfo}
                </div>
                <div class="hero-signals-row">${_signalTiles(auton, cog, ml, sparkHrv, sparkSleep, sparkStress)}</div>
                <div class="hero-capacity-header">
                    <span class="hero-section-label">TRAININGSKAPAZITÄT</span>
                    ${capRecText ? `<span class="${capRecCls} hero-cap-rec">${esc(capRecText)}</span>` : ''}
                </div>
                <div class="hero-capacity-grid">${_capacityTilesOnly(_bbScore, _tsb, sparkBatt)}</div>
                ${mlTile}
                ${rfScore != null ? feedbackButtons('readiness_rf') : ''}
                ${rfScore != null ? '<p class="disclosure-disclaimer" style="margin-top:6px">Automatisierte KI-Prognose auf Basis deiner Daten — kein medizinischer Befund (EU AI Act Art. 52).</p>' : ''}
            </div>
        </div>`;

    el.addEventListener('click', (e) => {
        const badge = e.target.closest('[data-ev-badge]');
        if (badge) {
            e.preventDefault();
            e.stopPropagation();
            openEvidenceDialog(badge.dataset.evBadge);
        }
    });

    if (score != null) {
        const progress = document.getElementById('hero-ring-progress');
        const scoreEl = document.getElementById('hero-ring-score');
        _animateRing(progress, scoreEl, fill, score);
    } else {
        const scoreEl = document.getElementById('hero-ring-score');
        if (scoreEl) scoreEl.textContent = '—';
    }
}

function mlStatTile(label, value, sub, href) {
    const tag = href ? 'a' : 'div';
    const hrefAttr = href ? ` href="${href}"` : '';
    return `<${tag} class="stat-tile"${hrefAttr}>
        <div class="stat-label">${esc(label)}</div>
        <div class="stat-value" style="font-size:1.3rem">${value}</div>
        ${sub ? `<div style="font-size:.73rem;color:var(--muted);margin-top:3px">${sub}</div>` : ''}
    </${tag}>`;
}

export function buildMlTabs() {
    const ml = _heroData.ml || {};

    // ── Erholung Tab: Anomalie + Battery Pattern ────────────────────────────
    const erholungEl = document.getElementById('ml-erholung-content');
    if (erholungEl) {
        const anomaly = ml.anomaly_hr;
        const bp = ml.battery_pattern;
        if (anomaly || bp) {
            document.getElementById('ml-erholung-card').classList.remove('hidden');
            let html = '<div class="ml-kpi-row">';
            if (anomaly) {
                const z = anomaly.z_score;
                const zTip =
                    z != null ? `z-Score ${z.toFixed(2)} · Schwelle |Z| > 2` : 'statistisches Signal, keine Diagnose';
                const flag = anomaly.is_anomaly
                    ? `<span style="color:var(--red)" title="${esc(zTip)}">⚠ Mögliche Auffälligkeit</span>`
                    : '<span style="color:var(--green)">✓ Normal</span>';
                html += mlStatTile(
                    'Ruhepuls z-Score',
                    z != null ? z.toFixed(2) : '—',
                    flag,
                    '/metrics/hr-zscore?back=erholung',
                );
            }
            if (bp?.pattern) {
                const BP_LABELS = {
                    stabil_hoch: 'Hohe & stabile Energie',
                    erholung: 'Erholung',
                    erschoepft: 'Erschöpft',
                };
                html += mlStatTile(
                    'Battery Muster',
                    BP_LABELS[bp.pattern] ?? esc(bp.pattern),
                    'Verlaufsmuster · Letzte Wochen',
                    '/metrics/battery-pattern?back=erholung',
                );
            }
            html += '</div>';
            if (anomaly) html += feedbackButtons('anomaly_hr');
            erholungEl.innerHTML = html;
        }
    }

    // ── Verlauf Tab: Readiness RF + Korrelationen ────────────────────────────
    const verlaufEl = document.getElementById('ml-verlauf-content');
    if (verlaufEl) {
        const rf = ml.readiness_rf;
        const corr = ml.correlation_sleep_hrv;
        if (rf || corr) {
            document.getElementById('ml-verlauf-card').classList.remove('hidden');
            let html = '<div class="ml-kpi-row">';
            if (rf?.value != null) {
                const score = Math.round(rf.value);
                const cls = score >= 80 ? 'sub-green' : score >= 50 ? 'sub-amber' : 'sub-red';
                html += mlStatTile(
                    'Readiness Morgen',
                    `<span class="${cls}">${score}</span>`,
                    'ML-Prognose',
                    '/metrics/readiness-rf?back=verlauf',
                );
            }
            if (corr?.r != null) {
                html += mlStatTile(
                    'Schlaf → HRV',
                    `r = ${corr.r.toFixed(2)}`,
                    `n = ${corr.n} Nächte`,
                    '/metrics/correlations?back=verlauf',
                );
            }
            html += '</div>';
            verlaufEl.innerHTML = html;
        }
    }
}
