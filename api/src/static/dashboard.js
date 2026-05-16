// Dark mode chart defaults
const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
Chart.defaults.borderColor = isDark ? 'rgba(51,65,85,.6)' : 'rgba(226,232,240,.8)';

const SPORT_EMOJI = {
    running: '🏃', cycling: '🚴', swimming: '🏊', walking: '🚶',
    hiking: '🥾', strength_training: '🏋️', yoga: '🧘',
    indoor_cycling: '🚴', trail_running: '🏔️', open_water_swimming: '🌊',
    cardio: '💪', cardio_training: '💪', elliptical: '🔄',
    fitness_equipment: '🏋️', other: '⚡', default: '⚡'
};
const SPORT_LABEL = {
    running: 'Laufen', cycling: 'Radfahren', swimming: 'Schwimmen',
    walking: 'Gehen', hiking: 'Wandern', strength_training: 'Krafttraining',
    yoga: 'Yoga', indoor_cycling: 'Indoor Cycling', trail_running: 'Trailrunning',
    open_water_swimming: 'Freiwasserschwimmen', cardio: 'Cardio',
    cardio_training: 'Cardio', elliptical: 'Ellipsentrainer',
    fitness_equipment: 'Fitnessgerät', other: 'Sonstige'
};

function sportLabel(type) {
    const emoji = SPORT_EMOJI[type] || SPORT_EMOJI.default;
    const name = SPORT_LABEL[type] || (type || 'Sonstige').replace(/_/g, ' ');
    return `${emoji} ${name}`;
}

function fmtDuration(s) {
    if (!s) return '—';
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function fmtDist(m) { return m ? (m / 1000).toFixed(1) + ' km' : '—'; }

function fmtDate(iso) {
    if (!iso) return '—';
    const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit' });
}

function secToH(s) { return s ? +(s / 3600).toFixed(1) : null; }

const charts = {};

function makeChart(id, type, labels, datasets, extra = {}) {
    if (charts[id]) charts[id].destroy();
    const canvas = document.getElementById(id);

    const scaleDefaults = extra.scales || {
        y: { beginAtZero: type === 'bar', stacked: extra.stacked || false }
    };

    charts[id] = new Chart(canvas, {
        type,
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: { display: datasets.length > 1 },
                ...(extra.plugins || {}),
            },
            scales: scaleDefaults,
        }
    });
}

function showEmpty(id) {
    const canvas = document.getElementById(id + '-chart');
    if (canvas) canvas.style.display = 'none';
    const empty = document.getElementById(id + '-empty');
    if (empty) empty.style.display = 'block';
}

function hideEmpty(id) {
    const canvas = document.getElementById(id + '-chart');
    if (canvas) canvas.style.display = '';
    const empty = document.getElementById(id + '-empty');
    if (empty) empty.style.display = 'none';
}

let currentDays   = 7;
let currentOffset = 0;

function getEndDate() {
    if (currentOffset === 0) return null;
    const d = new Date();
    d.setDate(d.getDate() - currentOffset * currentDays);
    return d.toISOString().slice(0, 10);
}

function updateNavBar() {
    const end   = new Date();
    end.setDate(end.getDate() - currentOffset * currentDays);
    const start = new Date(end);
    start.setDate(start.getDate() - currentDays + 1);
    const fmt = d => `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`;
    const rangeEl = document.getElementById('nav-range');
    const fwdEl   = document.getElementById('nav-forward');
    if (rangeEl) rangeEl.textContent = `${fmt(start)} – ${fmt(end)}`;
    if (fwdEl)   fwdEl.disabled = currentOffset === 0;
}

function shiftPeriod(delta) {
    currentOffset = Math.max(0, currentOffset + delta);
    updateNavBar();
    load(currentDays, getEndDate()).catch(() => {});
    loadTrainingLoad(currentDays).catch(() => {});
}

function setDays(days) {
    currentDays   = days;
    currentOffset = 0;
    document.querySelectorAll('.time-btn').forEach(b => {
        b.classList.toggle('active', +b.dataset.days === days);
    });
    updateNavBar();
    load(days);
    loadTrainingLoad(days).catch(() => {});
}

// ─── Tab Navigation ────────────────────────────────────────────────────────
const TABS = ['training', 'verlauf', 'erholung'];

// Maps hash → [tab, canvas-id] for direct chart navigation from external pages
const CHART_HASHES = {
    sleep:    ['erholung', 'sleep-chart'],
    hrv:      ['erholung', 'hrv-trend-chart'],
    stress:   ['verlauf',  'stress-chart'],
    battery:  ['verlauf',  'battery-chart'],
    hr:       ['verlauf',  'hr-chart'],
    training: ['training', 'training-load-chart'],
};

function setTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => { p.style.display = 'none'; });
    document.getElementById('tab-' + name).style.display = '';
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === name);
    });
    history.replaceState(null, '', '#' + name);
    setTimeout(() => Object.values(charts).forEach(c => c.resize()), 50);
}

// ─── Hero Card ─────────────────────────────────────────────────────────────
const _heroData = {
    readiness: null, daily: null, sleep: null, hrv: null,
    trainingStatus: null, energy: null, ml: null,
};

function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function openFormulaDialog(title, bodyHtml, href) {
    document.getElementById('formula-dialog-title').textContent = title;
    document.getElementById('formula-dialog-body').innerHTML = bodyHtml;
    document.getElementById('formula-dialog-link').href = href;
    document.getElementById('formula-dialog').showModal();
}

function scoreColor(score) {
    if (score == null) return 'var(--muted)';
    if (score >= 75)   return 'var(--green)';
    if (score >= 50)   return 'var(--amber)';
    return 'var(--red)';
}

async function buildWeeklyReview() {
    try {
        const weekly = await fetch('/api/weekly?weeks=2').then(r => r.json());
        if (!weekly || weekly.length < 2) return;
        const [thisWeek, lastWeek] = weekly.slice(-2).reverse();
        const d = thisWeek;
        if (!d) return;

        const weekLabel = `KW ${String(d.week).padStart(2, '0')} · ${d.start_date?.slice(5,10).replace('-', '.') || '?'} – ${d.end_date?.slice(5,10).replace('-', '.') || '?'}`;
        const actDelta = lastWeek ? d.activity_count - lastWeek.activity_count : 0;
        const actTrend = actDelta > 0 ? '↑' : actDelta < 0 ? '↓' : '→';
        const kmDelta = lastWeek ? d.total_km - lastWeek.total_km : 0;
        const kmPct = lastWeek && lastWeek.total_km > 0 ? ((kmDelta / lastWeek.total_km) * 100).toFixed(0) : 0;
        const kmTrend = kmDelta > 0 ? '↑' : kmDelta < 0 ? '↓' : '→';

        const reviewHtml = `
        <div style="padding: 1rem; border-radius: 0.5rem; background: rgba(0,0,0,0.1); margin-bottom: 1rem;">
            <div style="font-size: 0.875rem; color: rgba(255,255,255,0.6); margin-bottom: 0.5rem;">${weekLabel}</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div>
                    <div style="font-size: 0.75rem; text-transform: uppercase; color: rgba(255,255,255,0.5); margin-bottom: 0.25rem;">Aktivitäten</div>
                    <div style="font-size: 1.25rem; font-weight: bold;">${d.activity_count} ${actTrend}</div>
                    <div style="font-size: 0.75rem; color: rgba(255,255,255,0.6);">vs. ${lastWeek ? lastWeek.activity_count : '?'} Vorwoche</div>
                </div>
                <div>
                    <div style="font-size: 0.75rem; text-transform: uppercase; color: rgba(255,255,255,0.5); margin-bottom: 0.25rem;">Distanz</div>
                    <div style="font-size: 1.25rem; font-weight: bold;">${Math.round(d.total_km)} km ${kmTrend}</div>
                    <div style="font-size: 0.75rem; color: rgba(255,255,255,0.6);">${kmPct > 0 ? '+' : ''}${kmPct}%</div>
                </div>
            </div>
        </div>`;

        const card = document.getElementById('weekly-card');
        if (card) {
            const chartWrap = card.querySelector('.chart-wrap');
            if (chartWrap) {
                chartWrap.insertAdjacentHTML('beforebegin', reviewHtml);
            }
        }
    } catch (e) {
        console.warn('buildWeeklyReview error:', e);
    }
}

function metricTile({ label, value, sub = '', metric = '' }) {
    if (metric) {
        return `<a class="metric-tile" href="/metrics/${metric}">
            <div class="metric-tile-label">${label}</div>
            <div class="metric-tile-value">${value}</div>
            <div class="metric-tile-sub">${sub || '&nbsp;'}</div>
            <div class="metric-tile-arrow">↗</div>
        </a>`;
    }
    return `<div class="metric-tile metric-tile-static">
        <div class="metric-tile-label">${label}</div>
        <div class="metric-tile-value">${value}</div>
        <div class="metric-tile-sub">${sub || '&nbsp;'}</div>
    </div>`;
}

function buildHeroCard() {
    const el = document.getElementById('bento-hero');
    if (!el) return;

    const r      = _heroData.readiness;
    const energy = _heroData.energy || {};
    const daily  = _heroData.daily  || [];
    const sleep  = _heroData.sleep  || [];
    const hrv    = _heroData.hrv;
    const ml     = _heroData.ml     || {};
    const phys   = energy.energy_physical;
    const auton  = energy.energy_autonomic;
    const cog    = energy.energy_cognitive;

    const score        = r?.score ?? null;
    const circumference = 218; // 2π × 52 × (240/360) — Partial Arc 240°
    const fill         = score != null ? Math.round(score / 100 * circumference) : 0;
    const ringColor    = scoreColor(score);

    const today     = new Date();
    const dateLabel = today.toLocaleDateString('de-AT', { weekday: 'short', day: 'numeric', month: 'long' });

    // ── SVG Arc (240°, Öffnung unten — Oura/Whoop-Stil) ─────────────────────
    const svgRing = `<svg viewBox="0 0 120 120" class="readiness-ring">
        <circle cx="60" cy="60" r="52" fill="none" class="ring-track" stroke-width="8"
            stroke-dasharray="218 327" transform="rotate(120 60 60)"/>
        <circle cx="60" cy="60" r="52" fill="none"
            stroke="${ringColor}" stroke-width="8" stroke-linecap="round"
            stroke-dasharray="0 327" transform="rotate(120 60 60)"
            class="readiness-ring-progress" id="hero-ring-progress"/>
        <text x="60" y="56" text-anchor="middle" class="ring-score-text" id="hero-ring-score">0</text>
        <text x="60" y="72" text-anchor="middle" class="ring-label-text">READINESS</text>
    </svg>`;

    // ── Derived values (needed by ring + vitals) ────────────────────────────
    const last    = daily.length ? daily[daily.length - 1] : null;
    const anomaly = ml.anomaly_hr;
    const rf      = ml.readiness_rf;
    const hrvSt   = ml.hrv_status_custom;
    const im      = ml.intensity_minutes_custom;

    const _hrvLabel = { BALANCED: 'Erholt', UNBALANCED: 'Leicht gedämpft', LOW: 'Niedrig', POOR: 'Stark gedämpft' };

    // HRV-Balance sub-value
    let hrvSubVal = null, hrvSubCls = '';
    if (hrvSt?.status != null) {
        hrvSubVal = _hrvLabel[hrvSt.status] ?? hrvSt.status;
        hrvSubCls = hrvSt.status === 'BALANCED' ? 'sub-green' : hrvSt.status === 'POOR' ? 'sub-red' : 'sub-amber';
    }

    // Ruhepuls deviation sub-value
    let hrSubVal = null, hrSubCls = '';
    if (anomaly?.z_score != null && anomaly?.baseline_mean != null) {
        const todayHr = last?.resting_hr
            ?? Math.round(anomaly.baseline_mean + anomaly.z_score * (anomaly.baseline_std ?? 3));
        const devBpm  = Math.round(todayHr - anomaly.baseline_mean);
        const sign    = devBpm > 0 ? '+' : '';
        hrSubVal = `${sign}${devBpm} bpm vs. Ø${anomaly.is_anomaly ? ' ⚠' : ''}`;
        hrSubCls = anomaly.is_anomaly ? 'sub-red' : devBpm > 0 ? 'sub-amber' : '';
    }

    // ML prediction for tomorrow
    const rfScore = rf?.value != null ? Math.round(rf.value) : null;
    const rfSubCls = rfScore != null ? (rfScore >= 75 ? 'sub-green' : rfScore >= 50 ? 'sub-amber' : 'sub-red') : '';

    // ── Ring Section ─────────────────────────────────────────────────────────
    const rfTag = rfScore != null
        ? `<span class="hero-vital-derived ${rfSubCls}">~${rfScore}<span class="hero-derived-meta"> · ML · Morgen</span></span>`
        : '';

    const ringSection = `<div class="hero-ring-section">
        ${svgRing}
        <div class="hero-ring-meta">
            <span class="hero-ring-status">${esc(r?.label ?? '—')}</span>
            <a class="hero-ring-link" href="/metrics/readiness">→ Details</a>
            ${rfTag}
        </div>
    </div>`;

    // ── Energy Rows ─────────────────────────────────────────────────────────
    function energyRow(rowScore, label, sub, metric, isAlert) {
        const s     = rowScore != null ? Math.round(rowScore) : null;
        const color = scoreColor(s);
        const pfx   = isAlert ? '⚠ ' : '';
        const cls   = isAlert ? ' hero-energy-row-alert' : '';
        return `<a class="hero-energy-row${cls}" href="/metrics/${metric}">
            <span class="hero-energy-dot" style="background:${color}"></span>
            <span class="hero-energy-val">${pfx}${s ?? '—'}</span>
            <span class="hero-energy-label">${esc(label)}</span>
            <span class="hero-energy-sub">${esc(sub)}</span>
            <span class="hero-energy-arrow">↗</span>
        </a>`;
    }

    let tsbStr = '';
    if (phys?.tsb != null) {
        const sign = phys.tsb >= 0 ? '+' : '';
        tsbStr = `Form ${sign}${phys.tsb.toFixed(1)}`;
        if (phys?.ctl != null) tsbStr += ` · Fitness ${Math.round(phys.ctl)}`;
    }
    const devStr  = auton?.deviation != null ? `${auton.deviation >= 0 ? '+' : ''}${auton.deviation.toFixed(1)}σ` : '';
    const debtStr = cog?.debt_hours != null ? `${cog.debt_hours.toFixed(1)}h Schulden` : '';

    const energySection = `<div class="hero-energy-section">
        ${energyRow(phys?.score,  'Physisch', tsbStr,  'physical')}
        ${energyRow(auton?.score, 'Autonom',  devStr,  'autonomic')}
        ${energyRow(cog?.score,   'Kognitiv', debtStr, 'cognitive', (cog?.score ?? 100) < 30)}
    </div>`;

    // ── Vitals Strip ────────────────────────────────────────────────────────
    const stepsVal = last?.steps != null ? last.steps.toLocaleString('de-AT') : '—';
    const hrVal    = last?.resting_hr != null ? last.resting_hr + ' bpm' : '—';
    const hrvVal   = hrv?.hrv_weekly_avg != null ? hrv.hrv_weekly_avg + 'ms' : '—';

    const customSleep = ml.sleep_score_custom;
    let sleepVal;
    if (customSleep?.score != null) {
        const sc  = Math.round(customSleep.score);
        const cls = sc >= 75 ? 'chip-green' : sc >= 50 ? 'chip-amber' : 'chip-red';
        sleepVal  = `<span class="hero-chip ${cls}" style="display:inline;padding:2px 8px">${sc}</span>`;
    } else {
        sleepVal = sleep[0]?.sleep_score ?? '—';
    }

    function vitalTile(val, label, href, subVal = null, subCls = '', subMeta = '') {
        const sub = subVal != null
            ? `<span class="hero-vital-derived ${subCls}">${esc(String(subVal))}${subMeta ? `<span class="hero-derived-meta"> · ${subMeta}</span>` : ''}</span>`
            : '';
        const tag = href ? 'a' : 'div';
        const hrefAttr = href ? ` href="${href}"` : '';
        return `<${tag} class="hero-vital"${hrefAttr}>
            <span class="hero-vital-val">${val}</span>
            <span class="hero-vital-label">${esc(label)}</span>
            ${sub}
        </${tag}>`;
    }

    // SpO2 tile (conditional on settings)
    const spo2Enabled = window.__spo2Enabled === true;
    const spo2Val = last?.avg_spo2 != null ? last.avg_spo2 + ' %' : '—';
    const spo2Tile = spo2Enabled
        ? vitalTile(spo2Val, 'SpO₂ Ø', '/metrics/spo2-trend')
        : '';

    const vitalsSection = `<div class="hero-vitals">
        ${vitalTile(stepsVal, 'Schritte')}
        ${vitalTile(sleepVal, 'Schlaf-Score', ml.sleep_score_custom ? '/metrics/sleep-score-custom' : '/metrics/sleep')}
        ${vitalTile(hrvVal,  'HRV Wochenø',  '/metrics/hrv',       hrvSubVal, hrvSubCls, 'Balance')}
        ${vitalTile(hrVal,   'Ruhepuls',      '/metrics/hr-zscore', hrSubVal,  hrSubCls,  'vs. Ø')}
        ${spo2Tile}
    </div>`;

    // ── Intensity & New Metrics (ACWR, Monotony, Sleep Consistency) ──────────
    let chipsSection = '';
    const chips = [];

    if (im?.moderate_minutes != null) {
        const total = im.moderate_minutes + (im.vigorous_minutes || 0) * 2;
        chips.push(`<span class="hero-chip">Intensität: ${total} Min/Woche</span>`);
    }

    // ACWR chip
    const acwr = ml.acwr;
    if (acwr?.acwr != null) {
        const acolor = acwr.level === 'red' ? 'chip-red' : acwr.level === 'amber' ? 'chip-amber' : 'chip-green';
        chips.push(`<a href="/metrics/acwr" class="hero-chip ${acolor}" style="text-decoration:none">
            ACWR: ${acwr.acwr.toFixed(2)} · ${acwr.level === 'red' ? '⚠️ Risiko' : acwr.level === 'amber' ? '⚠️ Erhöht' : '✓ OK'}
        </a>`);
    }

    // Training Monotony chip
    const mono = ml.training_monotony;
    if (mono?.monotony != null) {
        const warnIcon = mono.monotony > 2.0 ? '⚠️' : '';
        chips.push(`<a href="/metrics/training-monotony" class="hero-chip chip-${mono.monotony > 2.0 ? 'red' : 'amber'}" style="text-decoration:none">
            Monotony: ${mono.monotony.toFixed(2)} ${warnIcon}
        </a>`);
    }

    // Sleep Consistency chip
    const cons = ml.sleep_consistency;
    if (cons?.score != null) {
        const ccolor = cons.score >= 80 ? 'chip-green' : cons.score >= 70 ? 'chip-amber' : 'chip-red';
        chips.push(`<a href="/metrics/sleep-consistency" class="hero-chip ${ccolor}" style="text-decoration:none">
            Schlafrhythmus: ${Math.round(cons.score)}
        </a>`);
    }

    // Body Battery Custom chip
    const bb = ml.body_battery_custom;
    if (bb?.score != null) {
        const bbcolor = bb.score >= 75 ? 'chip-green' : bb.score >= 40 ? 'chip-amber' : 'chip-red';
        chips.push(`<a href="/metrics/body-battery-custom" class="hero-chip ${bbcolor}" style="text-decoration:none">
            Energie: ${Math.round(bb.score)}% · ↑${bb.recovery} ↓${bb.activity_drain}
        </a>`);
    }

    // Stress Score Custom chip
    const ss = ml.stress_score_custom;
    if (ss?.score != null) {
        const sscolor = ss.score < 30 ? 'chip-green' : ss.score < 60 ? 'chip-amber' : 'chip-red';
        chips.push(`<a href="/metrics/stress-score-custom" class="hero-chip ${sscolor}" style="text-decoration:none">
            Stress: ${Math.round(ss.score)}
        </a>`);
    }

    if (chips.length > 0) {
        chipsSection = `<div class="hero-chips-wrap">
            <div class="hero-chips">
                ${chips.join('')}
            </div>
        </div>`;
    }

    // ── Assemble ────────────────────────────────────────────────────────────
    el.innerHTML = `<div class="hero-header">
            <span class="hero-title">TAGESSTATUS</span>
            <span class="hero-date">${esc(dateLabel)}</span>
        </div>
        <div class="hero-grid">
            ${ringSection}
            <div class="hero-right">
                ${energySection}
                ${vitalsSection}
            </div>
        </div>
        ${chipsSection}`;

    // ── Arc animation ────────────────────────────────────────────────────────
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

// ─── Loaders ───────────────────────────────────────────────────────────────

async function load(days, endDate = null) {
    const ed = endDate ? `&end_date=${endDate}` : '';
    const [activities, daily, sleep, hrv, hrvTrend, trainingStatus, mlHistory] = await Promise.all([
        fetch(`/api/activities?days=${days}${ed}`).then(r => r.json()),
        fetch(`/api/daily?days=${days}${ed}`).then(r => r.json()),
        fetch(`/api/sleep?days=${days}${ed}`).then(r => r.json()),
        fetch('/api/hrv').then(r => r.json()),
        fetch(`/api/hrv/trend?days=${days}${ed}`).then(r => r.json()),
        fetch('/api/training-status').then(r => r.json()),
        fetch(`/api/ml-history?days=${days}${ed}`).then(r => r.json()),
    ]);

    _heroData.daily = daily;
    _heroData.sleep = sleep;
    _heroData.hrv = hrv;
    _heroData.trainingStatus = trainingStatus;
    buildHeroCard();

    // Build weekly review widget
    buildWeeklyReview();

    // ── Aktivitäten ───────────────────────────────────────────────────
    const actEl = document.getElementById('activities-container');
    if (!activities.length) {
        actEl.innerHTML = '<p class="empty">Noch keine Aktivitäten — Sync läuft täglich um 6 Uhr.</p>';
    } else {
        actEl.innerHTML = `<div class="table-scroll"><table>
            <thead><tr>
                <th>Sport</th><th>Datum</th><th>Dauer</th>
                <th>Distanz</th><th>Kalorien</th><th>Ø HR</th>
            </tr></thead>
            <tbody>${activities.map(a => `<tr data-id="${a.id}" style="cursor:pointer">
                <td class="sport">${sportLabel(a.sport_type)}</td>
                <td>${fmtDate(a.started_at)}</td>
                <td>${fmtDuration(a.duration_seconds)}</td>
                <td>${fmtDist(a.distance_meters)}</td>
                <td>${a.calories ?? '—'}</td>
                <td>${a.avg_hr ? a.avg_hr + ' bpm' : '—'}</td>
            </tr>`).join('')}</tbody>
        </table></div>`;
    }

    // ── Trainingsübersicht (täglich) ─────────────────────────────────
    {
        const RUN_TYPES   = new Set(['running','trail_running','hiking','walking']);
        const RIDE_TYPES  = new Set(['cycling','indoor_cycling']);
        const dayMap = {};
        for (const a of activities) {
            const key = String(a.started_at).slice(0, 10);
            if (!dayMap[key]) dayMap[key] = { run_km: 0, ride_km: 0, other_h: 0 };
            const km = (a.distance_meters || 0) / 1000;
            const h  = (a.duration_seconds || 0) / 3600;
            const st = a.sport_type || '';
            if (RUN_TYPES.has(st))       dayMap[key].run_km  += km;
            else if (RIDE_TYPES.has(st)) dayMap[key].ride_km += km;
            else                         dayMap[key].other_h += h;
        }

        // Full date range — always include every day (empty = rest day)
        function _isoDate(dt) {
            return [dt.getFullYear(), String(dt.getMonth()+1).padStart(2,'0'), String(dt.getDate()).padStart(2,'0')].join('-');
        }
        const endDt = endDate
            ? (([y,m,d]) => new Date(y, m-1, d))(endDate.split('-').map(Number))
            : new Date(new Date().toDateString());
        const startDt = new Date(endDt);
        startDt.setDate(startDt.getDate() - days + 1);

        const actLabels = [], runKm = [], rideKm = [], otherH = [];
        for (let dt = new Date(startDt); dt <= endDt; dt.setDate(dt.getDate() + 1)) {
            const key = _isoDate(dt);
            const v = dayMap[key] || { run_km: 0, ride_km: 0, other_h: 0 };
            actLabels.push(fmtDate(key));
            runKm.push(+(v.run_km.toFixed(1)));
            rideKm.push(+(v.ride_km.toFixed(1)));
            otherH.push(+(v.other_h.toFixed(1)));
        }

        const hasRun   = runKm.some(v => v > 0);
        const hasRide  = rideKm.some(v => v > 0);
        const hasOther = otherH.some(v => v > 0);

        if (hasRun || hasRide || hasOther) {
            hideEmpty('weekly');
            const actDatasets = [];
            if (hasRun)   actDatasets.push({ label: 'Ausdauer',  data: runKm,  backgroundColor: 'rgba(99,102,241,.75)',  stack: 'km', borderRadius: 3 });
            if (hasRide)  actDatasets.push({ label: 'Radfahren', data: rideKm, backgroundColor: 'rgba(245,158,11,.75)', stack: 'km', borderRadius: 3 });
            if (hasOther) actDatasets.push({ label: 'Sonstiges', data: otherH, backgroundColor: 'rgba(16,185,129,.65)', stack: 'st', borderRadius: 3, yAxisID: 'yh' });
            const actScales = hasOther
                ? { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'km' }, position: 'left' }, yh: { stacked: true, title: { display: true, text: 'h' }, position: 'right', grid: { drawOnChartArea: false } } }
                : { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'km' } } };
            makeChart('weekly-chart', 'bar', actLabels, actDatasets, { scales: actScales });
        } else {
            showEmpty('weekly');
        }
    }

    const labels = daily.map(d => fmtDate(d.date));

    // ── Schritte ──────────────────────────────────────────────────────
    if (daily.some(d => d.steps)) {
        hideEmpty('steps');
        makeChart('steps-chart', 'bar', labels,
            [{ label: 'Schritte', data: daily.map(d => d.steps || 0),
               backgroundColor: '#6366f1', borderRadius: 4 }]);
    } else { showEmpty('steps'); }

    // ── Body Battery ──────────────────────────────────────────────────
    const bbDays = daily.filter(d => d.body_battery_high != null);
    if (bbDays.length) {
        hideEmpty('battery');
        makeChart('battery-chart', 'line', bbDays.map(d => fmtDate(d.date)), [
            { label: 'Hoch', data: bbDays.map(d => d.body_battery_high),
              borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
            { label: 'Niedrig', data: bbDays.map(d => d.body_battery_low),
              borderColor: '#f97316', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
        ]);
    } else { showEmpty('battery'); }

    // ── Ruhepuls ──────────────────────────────────────────────────────
    if (daily.some(d => d.resting_hr)) {
        hideEmpty('hr');
        makeChart('hr-chart', 'line', labels,
            [{ label: 'Ruhepuls', data: daily.map(d => d.resting_hr),
               borderColor: '#ef4444', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 }]);
    } else { showEmpty('hr'); }

    // ── Stress ────────────────────────────────────────────────────────
    if (daily.some(d => d.avg_stress)) {
        hideEmpty('stress');
        makeChart('stress-chart', 'line', labels,
            [{ label: 'Stress', data: daily.map(d => d.avg_stress),
               borderColor: '#f97316', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 }],
            { scales: { y: { beginAtZero: true, max: 100 } } });
    } else { showEmpty('stress'); }

    // ── HRV Trend ─────────────────────────────────────────────────────
    if (hrvTrend?.some(h => h.hrv_weekly_avg || h.hrv_last_night)) {
        hideEmpty('hrv-trend');
        const datasets = [];
        if (hrvTrend.some(h => h.hrv_last_night)) {
            datasets.push({ label: 'HRV letzte Nacht', data: hrvTrend.map(h => h.hrv_last_night),
               borderColor: '#6366f1', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 });
        }
        if (hrvTrend.some(h => h.hrv_weekly_avg)) {
            datasets.push({ label: 'Wochenø', data: hrvTrend.map(h => h.hrv_weekly_avg),
               borderColor: '#a5b4fc', backgroundColor: 'transparent', tension: 0.3,
               borderDash: [4, 4], pointRadius: 0 });
        }
        makeChart('hrv-trend-chart', 'line', hrvTrend.map(h => fmtDate(h.date)), datasets);
    } else { showEmpty('hrv-trend'); }

    // ── Schlaf-Score ──────────────────────────────────────────────────
    const sleepSorted = [...sleep].reverse();
    const sleepLabels = sleepSorted.map(s => fmtDate(s.date));
    const customSleepHist = (mlHistory?.sleep_score_custom || []).filter(s => s.value != null);
    if (customSleepHist.length >= 2) {
        hideEmpty('sleep');
        makeChart('sleep-chart', 'line',
            customSleepHist.map(s => fmtDate(s.date)),
            [{ label: 'Score', data: customSleepHist.map(s => s.value),
               borderColor: '#8b5cf6', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 }],
            { scales: { y: { min: 0, max: 100 } } });
    } else if (sleepSorted.some(s => s.sleep_score != null)) {
        hideEmpty('sleep');
        makeChart('sleep-chart', 'line', sleepLabels,
            [{ label: 'Score', data: sleepSorted.map(s => s.sleep_score ?? null),
               borderColor: '#8b5cf6', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 }],
            { scales: { y: { min: 0, max: 100 } } });
    } else { showEmpty('sleep'); }

    // ── Schlafphasen ──────────────────────────────────────────────────
    if (sleepSorted.some(s => s.deep_sleep_seconds)) {
        hideEmpty('sleep-stages');
        makeChart('sleep-stages-chart', 'bar', sleepLabels, [
            { label: 'Tief',   data: sleepSorted.map(s => secToH(s.deep_sleep_seconds)),
              backgroundColor: '#4f46e5', stack: 'sleep', borderRadius: 2 },
            { label: 'REM',    data: sleepSorted.map(s => secToH(s.rem_sleep_seconds)),
              backgroundColor: '#8b5cf6', stack: 'sleep', borderRadius: 2 },
            { label: 'Leicht', data: sleepSorted.map(s => secToH(s.light_sleep_seconds)),
              backgroundColor: '#a5b4fc', stack: 'sleep', borderRadius: 2 },
            { label: 'Wach',   data: sleepSorted.map(s => secToH(s.awake_seconds)),
              backgroundColor: isDark ? '#334155' : '#e2e8f0', stack: 'sleep', borderRadius: 2 },
        ], { scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'Stunden' } } } });
    } else { showEmpty('sleep-stages'); }

    // ── Intensitätsminuten ────────────────────────────────────────────
    const customIntHist = (mlHistory?.intensity_minutes_custom || []).filter(s => s.value != null);
    if (customIntHist.length >= 2) {
        hideEmpty('intensity');
        makeChart('intensity-chart', 'bar',
            customIntHist.map(s => fmtDate(s.date)), [
            { label: 'Moderat', data: customIntHist.map(s => s.moderate_minutes || 0),
              backgroundColor: '#22c55e', stack: 'intensity', borderRadius: 2 },
            { label: 'Intensiv', data: customIntHist.map(s => s.vigorous_minutes || 0),
              backgroundColor: '#06b6d4', stack: 'intensity', borderRadius: 2 },
        ], { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Minuten' } } } });
    } else if (daily.some(d => d.intensity_moderate || d.intensity_vigorous)) {
        hideEmpty('intensity');
        makeChart('intensity-chart', 'bar', labels, [
            { label: 'Moderat', data: daily.map(d => d.intensity_moderate || 0),
              backgroundColor: '#22c55e', stack: 'intensity', borderRadius: 2 },
            { label: 'Intensiv', data: daily.map(d => d.intensity_vigorous || 0),
              backgroundColor: '#06b6d4', stack: 'intensity', borderRadius: 2 },
        ], { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Minuten' } } } });
    } else { showEmpty('intensity'); }

    // ── Kalorien ──────────────────────────────────────────────────────
    if (daily.some(d => d.calories_total)) {
        hideEmpty('calories');
        makeChart('calories-chart', 'bar', labels,
            [{ label: 'Kalorien', data: daily.map(d => d.calories_total || 0),
               backgroundColor: '#f59e0b', borderRadius: 4 }]);
    } else { showEmpty('calories'); }
}

async function loadReadiness() {
    const r = await fetch('/api/readiness').then(res => res.json());
    _heroData.readiness = r;
    buildHeroCard();
}

async function loadMlInsights() {
    const d = await fetch('/api/ml-insights').then(r => r.json());
    _heroData.ml = d;
    buildHeroCard();
}

async function loadEnergyMetrics() {
    const d = await fetch('/api/energy').then(r => r.json());
    _heroData.energy = d;
    buildHeroCard();
}


async function loadTrainingLoad(days = null) {
    const qs   = days != null ? `?lookback_days=${days}` : '';
    const data = await fetch(`/api/training-load${qs}`).then(r => r.json());
    if (!data.history?.length) { showEmpty('training-load'); return; }
    hideEmpty('training-load');

    const history = data.history;
    const forecast = data.forecast || [];
    const n = history.length;
    const allLabels = [...history.map(h => fmtDate(h.date)), ...forecast.map(f => fmtDate(f.date))];

    // TRIMP bars: history only
    const trimpData = [...history.map(h => h.trimp), ...forecast.map(() => null)];

    // Ermüdung/Fitness/Form: solid für History, gestrichelt für Forecast
    const bridge = i => [...Array(n - 1).fill(null), history.at(-1)?.[i] ?? null, ...forecast.map(f => f[i])];
    const solid  = i => [...history.map(h => h[i]), ...forecast.map(() => null)];

    const datasets = [
        { type: 'bar',  label: 'Tagesimpuls',   data: trimpData,      backgroundColor: 'rgba(99,102,241,.2)', yAxisID: 'ytrimp', borderRadius: 3 },
        { type: 'line', label: 'Ermüdung',      data: solid('atl'),   borderColor: '#f97316', backgroundColor: 'transparent', tension: 0.2, pointRadius: 2 },
        { type: 'line', label: 'Ermüdung →',    data: bridge('atl'),  borderColor: '#f97316', backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderDash: [4, 4] },
        { type: 'line', label: 'Fitness',        data: solid('ctl'),   borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.2, pointRadius: 2 },
        { type: 'line', label: 'Fitness →',      data: bridge('ctl'),  borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderDash: [4, 4] },
        { type: 'line', label: 'Form',           data: solid('tsb'),   borderColor: '#a78bfa', backgroundColor: 'transparent', tension: 0.2, pointRadius: 2 },
        { type: 'line', label: 'Form →',         data: bridge('tsb'),  borderColor: '#a78bfa', backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderDash: [4, 4] },
    ];

    makeChart('training-load-chart', 'bar', allLabels, datasets, {
        plugins: {
            legend: {
                display: true,
                labels: { filter: item => !item.text.includes('→') },
            },
        },
        scales: {
            x: {},
            y:      { title: { display: true, text: 'TRIMP' }, position: 'left' },
            ytrimp: { position: 'right', grid: { drawOnChartArea: false }, display: false },
        },
    });

    const t = data.today;
    const atlEl = document.getElementById('tl-atl');
    const ctlEl = document.getElementById('tl-ctl');
    const tsbEl = document.getElementById('tl-tsb');
    if (atlEl && t.atl != null) atlEl.textContent = t.atl;
    if (ctlEl && t.ctl != null) ctlEl.textContent = t.ctl;
    if (tsbEl && t.tsb != null) {
        const sign = t.tsb > 0 ? '+' : '';
        tsbEl.textContent = sign + t.tsb;
        tsbEl.style.color = t.tsb > 5 ? 'var(--green)' : t.tsb < -5 ? 'var(--red)' : 'var(--amber)';
    }
}

// ── Toast ─────��──────────────────────────────────────────��─────────────────
let _toastTimer = null;
function showToast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast show' + (type ? ' ' + type : '');
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => el.classList.remove('show'), 3500);
}

// ── ML Status ──────────────────────────────────────────────────────────────
let _mlPollTimer = null;

function setMlStatus(text, visible) {
    const el = document.getElementById('ml-status');
    el.textContent = text;
    el.style.display = visible ? '' : 'none';
}

async function pollMlStatus() {
    try {
        const s = await fetch('/api/ml-status').then(r => r.json());
        if (s.pending) {
            setMlStatus('🤖 ML läuft…', true);
            _mlPollTimer = setTimeout(pollMlStatus, 8000);
        } else {
            const age = s.last_ml_at ? fmtSyncAge(s.last_ml_at) : null;
            setMlStatus(age ? `🤖 ML · ${age}` : '', !!age);
            if (_mlPollTimer) {
                showToast('ML Einblicke aktualisiert');
                loadMlInsights();
                loadEnergyMetrics().catch(() => {});
                loadReadiness().catch(() => {});
            }
            _mlPollTimer = null;
        }
    } catch { /* ignorieren */ }
}

async function loadMlStatus() {
    try {
        const s = await fetch('/api/ml-status').then(r => r.json());
        if (s.pending) {
            setMlStatus('🤖 ML läuft…', true);
            _mlPollTimer = setTimeout(pollMlStatus, 8000);
        } else if (s.last_ml_at) {
            setMlStatus(`🤖 ML · ${fmtSyncAge(s.last_ml_at)}`, true);
        }
    } catch { /* ignorieren */ }
}

// ── Sync Status ────────────────────────────────────────────────────────────
function fmtSyncAge(iso) {
    const mins = Math.round((Date.now() - new Date(iso)) / 60000);
    if (mins < 2)  return 'Gerade eben';
    if (mins < 60) return `vor ${mins}m`;
    return `vor ${Math.round(mins / 60)}h`;
}

function setSyncLoading(loading) {
    const btn = document.getElementById('sync-btn');
    btn.textContent = loading ? '↻ Läuft…' : '↻ Sync';
    btn.classList.toggle('sync-loading', loading);
}

let _syncPollTimer = null;

async function pollSyncStatus() {
    try {
        const s = await fetch('/api/sync-status').then(r => r.json());
        if (s.last_sync_at) {
            document.getElementById('sync-last').textContent = fmtSyncAge(s.last_sync_at);
        }
        if (s.pending) {
            _syncPollTimer = setTimeout(pollSyncStatus, 5000);
        } else {
            setSyncLoading(false);
            if (_syncPollTimer) {
                showToast('Sync abgeschlossen');
                currentOffset = 0;
                updateNavBar();
                load(currentDays);
                loadTrainingLoad(currentDays).catch(() => {});
                loadReadiness();
                loadEnergyMetrics().catch(() => {});
                _mlPollTimer = setTimeout(pollMlStatus, 5000);
            }
            _syncPollTimer = null;
        }
    } catch { /* Netzwerkfehler ignorieren */ }
}

async function loadSyncStatus() {
    try {
        const s = await fetch('/api/sync-status').then(r => r.json());
        if (s.last_sync_at) {
            document.getElementById('sync-last').textContent = fmtSyncAge(s.last_sync_at);
        }
        if (s.pending) {
            setSyncLoading(true);
            _syncPollTimer = setTimeout(pollSyncStatus, 5000);
        }
    } catch { /* ignorieren */ }
}

async function triggerSync() {
    if (document.getElementById('sync-btn').classList.contains('sync-loading')) return;
    try {
        const res = await fetch('/api/sync', { method: 'POST' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showToast(err?.error?.message || 'Sync fehlgeschlagen', 'error');
            return;
        }
        setSyncLoading(true);
        _syncPollTimer = setTimeout(pollSyncStatus, 5000);
    } catch {
        showToast('Verbindungsfehler', 'error');
    }
}

// ── Event Listeners ────────────────────────────────────────────────────────
document.querySelectorAll('.time-btn').forEach(btn => {
    btn.addEventListener('click', () => setDays(+btn.dataset.days));
});
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
});
document.getElementById('sync-btn').addEventListener('click', triggerSync);
document.getElementById('nav-back').addEventListener('click', () => shiftPeriod(1));
document.getElementById('nav-forward').addEventListener('click', () => shiftPeriod(-1));
document.getElementById('activities-container').addEventListener('click', e => {
    const tr = e.target.closest('tr[data-id]');
    if (tr) location.href = '/activity/' + tr.dataset.id;
});

// ── Init ───────────────────────────────────────────────────────────────────
updateNavBar();
const _hash = location.hash.slice(1);
if (TABS.includes(_hash)) {
    setTab(_hash);
} else if (CHART_HASHES[_hash]) {
    const [_tab, _chartId] = CHART_HASHES[_hash];
    setTab(_tab);
    setTimeout(() => {
        document.getElementById(_chartId)?.closest('.card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 200);
} else {
    setTab('training');
}
load(currentDays).catch(() => showToast('Dashboard konnte nicht geladen werden', 'error'));
loadTrainingLoad().catch(() => {});
loadReadiness().catch(() => showToast('Readiness-Score konnte nicht geladen werden', 'error'));
loadMlInsights().catch(() => {});
loadEnergyMetrics().catch(() => {});
loadSyncStatus();
loadMlStatus();
