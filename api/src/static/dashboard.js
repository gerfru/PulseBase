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
            plugins: { legend: { display: datasets.length > 1 } },
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
    loadWeekly(Math.max(4, Math.ceil(currentDays / 7)), getEndDate()).catch(() => {});
}

function setDays(days) {
    currentDays   = days;
    currentOffset = 0;
    document.querySelectorAll('.time-btn').forEach(b => {
        b.classList.toggle('active', +b.dataset.days === days);
    });
    updateNavBar();
    load(days);
    loadWeekly(Math.max(4, Math.ceil(days / 7))).catch(() => {});
}

// ─── Tab Navigation ────────────────────────────────────────────────────────
function setTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => { p.style.display = 'none'; });
    document.getElementById('tab-' + name).style.display = '';
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === name);
    });
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

function scoreColor(score) {
    if (score == null) return 'var(--muted)';
    if (score >= 75)   return 'var(--green)';
    if (score >= 50)   return 'var(--amber)';
    return 'var(--red)';
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
    const circumference = 327; // 2π × 52
    const fill         = score != null ? Math.round(score / 100 * circumference) : 0;
    const ringColor    = scoreColor(score);

    const today     = new Date();
    const dateLabel = today.toLocaleDateString('de-AT', { weekday: 'short', day: 'numeric', month: 'long' });

    // ── SVG Ring ────────────────────────────────────────────────────────────
    const svgRing = `<svg viewBox="0 0 120 120" class="readiness-ring">
        <circle cx="60" cy="60" r="52" fill="none" class="ring-track" stroke-width="8"/>
        <circle cx="60" cy="60" r="52" fill="none"
            stroke="${ringColor}" stroke-width="8" stroke-linecap="round"
            stroke-dasharray="${circumference}" stroke-dashoffset="${circumference}"
            transform="rotate(-90 60 60)"
            class="readiness-ring-progress" id="hero-ring-progress"/>
        <text x="60" y="56" text-anchor="middle" class="ring-score-text" id="hero-ring-score">0</text>
        <text x="60" y="72" text-anchor="middle" class="ring-label-text">READINESS</text>
    </svg>`;

    const ringSection = `<div class="hero-ring-section">
        ${svgRing}
        <div class="hero-ring-meta">
            <span class="hero-ring-status">${esc(r?.label ?? '—')}</span>
            <a class="hero-ring-link" href="/metrics/readiness">→ Details</a>
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

    const tsbStr  = phys?.tsb != null ? (phys.tsb >= 0 ? `TSB +${phys.tsb.toFixed(1)}` : `TSB ${phys.tsb.toFixed(1)}`) : '';
    const devStr  = auton?.deviation != null ? `${auton.deviation >= 0 ? '+' : ''}${auton.deviation.toFixed(1)}σ` : '';
    const debtStr = cog?.debt_hours != null ? `${cog.debt_hours.toFixed(1)}h Schulden` : '';

    const energySection = `<div class="hero-energy-section">
        ${energyRow(phys?.score,  'Physisch', tsbStr,  'physical')}
        ${energyRow(auton?.score, 'Autonom',  devStr,  'autonomic')}
        ${energyRow(cog?.score,   'Kognitiv', debtStr, 'cognitive', (cog?.score ?? 100) < 30)}
    </div>`;

    // ── Vitals Strip ────────────────────────────────────────────────────────
    const last   = daily.length ? daily[daily.length - 1] : null;
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

    const vitalsSection = `<div class="hero-vitals">
        <a class="hero-vital" href="/metrics/steps">
            <span class="hero-vital-val">${stepsVal}</span>
            <span class="hero-vital-label">Schritte</span>
        </a>
        <a class="hero-vital" href="/metrics/sleep">
            <span class="hero-vital-val">${sleepVal}</span>
            <span class="hero-vital-label">Schlaf-Score</span>
        </a>
        <a class="hero-vital" href="/metrics/hrv">
            <span class="hero-vital-val">${hrvVal}</span>
            <span class="hero-vital-label">HRV Wochenø</span>
        </a>
        <a class="hero-vital" href="/metrics/hr-zscore">
            <span class="hero-vital-val">${hrVal}</span>
            <span class="hero-vital-label">Ruhepuls</span>
        </a>
    </div>`;

    // ── Status Chips ────────────────────────────────────────────────────────
    const anomaly = ml.anomaly_hr;
    const rf      = ml.readiness_rf;
    const hrvSt   = ml.hrv_status_custom;
    const im      = ml.intensity_minutes_custom;
    const chips   = [];

    if (hrvSt?.status != null) {
        const cls = hrvSt.status === 'BALANCED' ? 'chip-green' : hrvSt.status === 'POOR' ? 'chip-red' : 'chip-amber';
        chips.push(`<span class="hero-chip ${cls}">${esc(hrvSt.status)}</span>`);
    }
    if (anomaly?.z_score != null) {
        const cls = anomaly.is_anomaly ? 'chip-red' : '';
        chips.push(`<span class="hero-chip ${cls}">z ${anomaly.z_score.toFixed(2)} ${anomaly.is_anomaly ? '⚠' : '✓'}</span>`);
    }
    if (rf?.value != null) {
        const s   = Math.round(rf.value);
        const cls = s >= 75 ? 'chip-green' : s >= 50 ? 'chip-amber' : 'chip-red';
        chips.push(`<span class="hero-chip ${cls}">Prognose ↓${s}</span>`);
    }
    if (im?.moderate_minutes != null) {
        const total = im.moderate_minutes + (im.vigorous_minutes || 0) * 2;
        chips.push(`<span class="hero-chip">Intensität ${total}min</span>`);
    }

    const chipsSection = chips.length ? `<div class="hero-chips">${chips.join('')}</div>` : '';

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

    // ── Ring animation ───────────────────────────────────────────────────────
    if (score != null) {
        const progress = document.getElementById('hero-ring-progress');
        const scoreEl  = document.getElementById('hero-ring-score');
        requestAnimationFrame(() => {
            if (progress) progress.style.strokeDashoffset = String(circumference - fill);
            if (scoreEl) {
                const t0 = performance.now();
                (function tick(now) {
                    const p = Math.min((now - t0) / 600, 1);
                    scoreEl.textContent = Math.round(p * score);
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

    const labels = daily.map(d => fmtDate(d.date));

    // ── Schritte ──────────────────────────────────────────────────────
    if (daily.some(d => d.steps)) {
        hideEmpty('steps');
        makeChart('steps-chart', 'bar', labels,
            [{ label: 'Schritte', data: daily.map(d => d.steps || 0),
               backgroundColor: '#6366f1', borderRadius: 4 }]);
    } else { showEmpty('steps'); }

    // ── Body Battery ──────────────────────────────────────────────────
    if (daily.some(d => d.body_battery_high)) {
        hideEmpty('battery');
        makeChart('battery-chart', 'line', labels, [
            { label: 'Hoch', data: daily.map(d => d.body_battery_high),
              borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
            { label: 'Niedrig', data: daily.map(d => d.body_battery_low),
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

async function loadWeekly(weeks = 12, endDate = null) {
    const ed   = endDate ? `&end_date=${endDate}` : '';
    const data = await fetch(`/api/weekly?weeks=${weeks}${ed}`).then(r => r.json());
    if (!data.length || !data.some(w => w.total_km || w.other_hours)) {
        showEmpty('weekly'); return;
    }
    hideEmpty('weekly');
    const labels = data.map(w => {
        const [y, mo, d] = String(w.week).slice(0, 10).split('-').map(Number);
        return new Date(y, mo - 1, d).toLocaleDateString('de-AT', { day: '2-digit', month: 'short' });
    });
    const hasStrength = data.some(w => w.other_hours);
    const datasets = [
        { label: 'Ausdauer',  data: data.map(w => w.run_km  || 0), backgroundColor: 'rgba(99,102,241,.75)',  stack: 'km', borderRadius: 3 },
        { label: 'Radfahren', data: data.map(w => w.ride_km || 0), backgroundColor: 'rgba(245,158,11,.75)', stack: 'km', borderRadius: 3 },
    ];
    if (hasStrength) {
        datasets.push({ label: 'Strength Training', data: data.map(w => w.other_hours || 0), backgroundColor: 'rgba(16,185,129,.65)', stack: 'st', borderRadius: 3, yAxisID: 'yh' });
    }
    const scales = hasStrength
        ? { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'km' }, position: 'left' }, yh: { stacked: true, title: { display: true, text: 'h' }, position: 'right', grid: { drawOnChartArea: false } } }
        : { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'km' } } };
    makeChart('weekly-chart', 'bar', labels, datasets, { scales });
}

// ── Toast ──────────────────────────────────────────────────────────────────
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
                loadWeekly(Math.max(4, Math.ceil(currentDays / 7)));
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
load(currentDays).catch(() => showToast('Dashboard konnte nicht geladen werden', 'error'));
loadWeekly().catch(() => showToast('Wochendaten konnten nicht geladen werden', 'error'));
loadReadiness().catch(() => showToast('Readiness-Score konnte nicht geladen werden', 'error'));
loadMlInsights().catch(() => {});
loadEnergyMetrics().catch(() => {});
loadSyncStatus();
loadMlStatus();
