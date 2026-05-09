// Dark mode chart defaults
const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
Chart.defaults.borderColor = isDark ? 'rgba(51,65,85,.6)' : 'rgba(226,232,240,.8)';

const SPORT_EMOJI = {
    running: '🏃', cycling: '🚴', swimming: '🏊', walking: '🚶',
    hiking: '🥾', strength_training: '🏋️', yoga: '🧘',
    indoor_cycling: '🚴', trail_running: '🏔️', open_water_swimming: '🌊',
    cardio: '💪', elliptical: '🔄', fitness_equipment: '🏋️', default: '⚡'
};

function sportLabel(type) {
    const emoji = SPORT_EMOJI[type] || SPORT_EMOJI.default;
    const name = (type || 'unbekannt').replace(/_/g, ' ');
    return `${emoji} ${name.charAt(0).toUpperCase() + name.slice(1)}`;
}

function fmtDuration(s) {
    if (!s) return '—';
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function fmtDist(m) { return m ? (m / 1000).toFixed(1) + ' km' : '—'; }

function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit' });
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

let currentDays = 7;

function setDays(days) {
    currentDays = days;
    document.querySelectorAll('.time-btn').forEach(b => {
        b.classList.toggle('active', +b.dataset.days === days);
    });
    load(days);
}

// ─── Metric Hero ───────────────────────────────────────────────────────────
const _heroData = {
    readiness: null, daily: null, sleep: null, hrv: null,
    trainingStatus: null, energy: null, ml: null,
};

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

function buildReadinessCard() {
    const el = document.getElementById('bento-readiness');
    if (!el) return;
    const r = _heroData.readiness;
    let html = '<h2>Readiness</h2>';
    if (!r || r.score === null) {
        html += '<p class="empty" style="padding:var(--sp-4) 0">Noch keine Daten — Sync läuft täglich um 6 Uhr.</p>';
    } else {
        const scoreColors = { 'badge-balanced': '#22c55e', 'badge-unbalanced': '#f59e0b', 'badge-poor': '#ef4444' };
        const color = scoreColors[r.cls] || scoreColors['badge-poor'];
        html += `<a class="readiness-tile" href="/metrics/readiness">
            <div style="display:flex;align-items:baseline;gap:var(--sp-4);flex-wrap:wrap;margin-bottom:var(--sp-2)">
                <div class="readiness-score" style="color:${color}">${r.score}</div>
                <span class="badge ${r.cls}">${r.label}</span>
            </div>
            <div class="metric-tile-hint">→ Details zur Berechnung</div>
        </a>`;
    }
    el.innerHTML = html;
}

function buildGarminCard() {
    const el    = document.getElementById('bento-garmin');
    if (!el) return;
    const daily = _heroData.daily || [];
    const sleep = _heroData.sleep || [];
    const hrv   = _heroData.hrv;
    const last  = daily[daily.length - 1];
    const tiles = [
        metricTile({ label: 'Schritte',     value: last?.steps?.toLocaleString('de-AT') ?? '—', metric: 'steps' }),
        metricTile({ label: 'Schlaf-Score', value: sleep[0]?.sleep_score ?? '—',                metric: 'sleep' }),
        metricTile({ label: 'HRV Wochenø',  value: hrv?.hrv_weekly_avg ? hrv.hrv_weekly_avg + ' ms' : '—', metric: 'hrv' }),
        metricTile({ label: 'Body Battery', value: last?.body_battery_high ?? '—',              metric: 'body-battery' }),
    ];
    el.innerHTML = `<h2>Garmin</h2><div class="metric-grid">${tiles.join('')}</div>`;
}

function buildEnergieCard() {
    const el     = document.getElementById('bento-energie');
    if (!el) return;
    const energy = _heroData.energy || {};
    const phys   = energy.energy_physical;
    const auton  = energy.energy_autonomic;
    const cog    = energy.energy_cognitive;
    const tsbStr  = phys?.tsb != null ? (phys.tsb >= 0 ? `TSB +${phys.tsb.toFixed(1)}` : `TSB ${phys.tsb.toFixed(1)}`) : '';
    const devStr  = auton?.deviation != null ? `${auton.deviation >= 0 ? '+' : ''}${auton.deviation.toFixed(1)}σ` : '';
    const debtStr = cog?.debt_hours != null ? `${cog.debt_hours.toFixed(1)}h Schulden` : '';
    const tiles = [
        metricTile({ label: 'Physisch', value: phys?.score != null ? Math.round(phys.score) : '—',  sub: tsbStr  || (phys  == null ? 'noch keine Daten' : ''), metric: 'physical' }),
        metricTile({ label: 'Autonom',  value: auton?.score != null ? Math.round(auton.score) : '—', sub: devStr  || (auton == null ? 'noch keine Daten' : ''), metric: 'autonomic' }),
        metricTile({ label: 'Kognitiv', value: cog?.score != null ? Math.round(cog.score) : '—',    sub: debtStr || (cog   == null ? 'noch keine Daten' : ''), metric: 'cognitive' }),
    ];
    el.innerHTML = `<h2>Energie</h2><div class="metric-grid">${tiles.join('')}</div>`;
}

function buildMlCard() {
    const el  = document.getElementById('bento-ml');
    if (!el) return;
    const ml  = _heroData.ml || {};
    const hrv = _heroData.hrv;
    const ts  = _heroData.trainingStatus;
    const anomaly = ml.anomaly_hr;
    const rf      = ml.readiness_rf;
    const tiles   = [];

    if (anomaly?.z_score != null) {
        tiles.push(metricTile({
            label: 'Ruhepuls Z-Score', value: anomaly.z_score.toFixed(2),
            sub: anomaly.is_anomaly ? '⚠ Anomalie' : `✓ Normal (Ø ${Math.round(anomaly.baseline_mean)} bpm)`,
            metric: 'hr-zscore',
        }));
    } else {
        tiles.push(metricTile({ label: 'Ruhepuls Z-Score', value: '—', sub: 'zu wenig Daten', metric: 'hr-zscore' }));
    }

    if (rf?.value != null) {
        const score = Math.round(rf.value);
        const cls   = score >= 80 ? 'badge-balanced' : score >= 50 ? 'badge-unbalanced' : 'badge-poor';
        const rfLbl = score >= 80 ? 'Gut' : score >= 50 ? 'Moderat' : 'Niedrig';
        tiles.push(metricTile({
            label: 'Prognose morgen',
            value: `<span class="badge ${cls}" style="font-size:1.4rem;padding:.1rem .5rem">${score}</span>`,
            sub: `${rfLbl} · Readiness (0–100)`, metric: 'readiness-rf',
        }));
    } else {
        tiles.push(metricTile({ label: 'Prognose morgen', value: '—', sub: 'Modell trainiert sonntags', metric: 'readiness-rf' }));
    }

    const hrvStatusLabels = { balanced: 'Ausgeglichen', unbalanced: 'Unausgeglichen', low: 'Niedrig', poor: 'Niedrig' };
    const hrvStatusKey = (hrv?.hrv_status || '').toLowerCase();
    const hrvStatusVal = hrvStatusLabels[hrvStatusKey] ?? (hrv?.hrv_status ?? '—');
    const hrvStatusCls = hrvStatusKey === 'balanced' ? 'badge-balanced'
        : hrvStatusKey === 'unbalanced' ? 'badge-unbalanced'
        : (hrvStatusKey === 'low' || hrvStatusKey === 'poor') ? 'badge-poor' : '';
    tiles.push(metricTile({
        label: 'HRV-Status',
        value: hrvStatusCls ? `<span class="badge ${hrvStatusCls}" style="font-size:1rem;padding:.1rem .5rem">${hrvStatusVal}</span>` : '—',
        sub: hrv?.hrv_last_night ? `${hrv.hrv_last_night} ms letzte Nacht` : '',
        metric: 'hrv-status',
    }));

    const tsMap = {
        PRODUCTIVE:   { label: 'Aufbauend',       cls: 'badge-balanced'   },
        MAINTAINING:  { label: 'Erhalt',           cls: 'badge-balanced'   },
        RECOVERY:     { label: 'Erholung',         cls: 'badge-unbalanced' },
        UNPRODUCTIVE: { label: 'Nicht produktiv',  cls: 'badge-unbalanced' },
        OVERREACHING: { label: 'Übertraining',     cls: 'badge-poor'       },
        DETRAINING:   { label: 'Abfall',           cls: 'badge-poor'       },
    };
    if (ts?.training_status) {
        const key   = (ts.training_status || '').toUpperCase();
        const entry = tsMap[key] || { label: ts.training_status, cls: 'badge-unbalanced' };
        const dStr  = ts.date ? new Date(ts.date).toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit' }) : '';
        tiles.push(metricTile({
            label: 'Trainingszustand',
            value: `<span class="badge ${entry.cls}" style="font-size:1rem;padding:.1rem .5rem">${entry.label}</span>`,
            sub: dStr ? `Stand ${dStr}` : '', metric: 'training-status',
        }));
    } else {
        tiles.push(metricTile({ label: 'Trainingszustand', value: '—', sub: 'wird nach Sync befüllt', metric: 'training-status' }));
    }

    el.innerHTML = `<h2>ML &amp; Status</h2><div class="metric-grid">${tiles.join('')}</div>`;
}

function buildAllBentoCards() {
    buildReadinessCard();
    buildGarminCard();
    buildEnergieCard();
    buildMlCard();
}

// ─── Loaders ───────────────────────────────────────────────────────────────

async function load(days) {
    const [activities, daily, sleep, hrv, hrvTrend, trainingStatus] = await Promise.all([
        fetch(`/api/activities?days=${days}`).then(r => r.json()),
        fetch(`/api/daily?days=${days}`).then(r => r.json()),
        fetch(`/api/sleep?days=${days}`).then(r => r.json()),
        fetch('/api/hrv').then(r => r.json()),
        fetch(`/api/hrv/trend?days=${days}`).then(r => r.json()),
        fetch('/api/training-status').then(r => r.json()),
    ]);

    _heroData.daily = daily;
    _heroData.sleep = sleep;
    _heroData.hrv = hrv;
    _heroData.trainingStatus = trainingStatus;
    buildAllBentoCards();

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
    if (sleepSorted.some(s => s.sleep_score != null)) {
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
    if (daily.some(d => d.intensity_moderate || d.intensity_vigorous)) {
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
    buildAllBentoCards();
}

async function loadMlInsights() {
    const d = await fetch('/api/ml-insights').then(r => r.json());
    _heroData.ml = d;
    buildAllBentoCards();
}

async function loadEnergyMetrics() {
    const d = await fetch('/api/energy').then(r => r.json());
    _heroData.energy = d;
    buildAllBentoCards();
}

async function loadWeekly() {
    const data = await fetch('/api/weekly?weeks=12').then(r => r.json());
    if (!data.length || !data.some(w => w.run_km || w.ride_km)) {
        showEmpty('weekly'); return;
    }
    hideEmpty('weekly');
    const labels = data.map(w =>
        new Date(w.week).toLocaleDateString('de-AT', { day: '2-digit', month: 'short' })
    );
    makeChart('weekly-chart', 'bar', labels, [
        { label: 'Laufen',    data: data.map(w => w.run_km  || 0), backgroundColor: 'rgba(99,102,241,.75)',  stack: 'km', borderRadius: 3 },
        { label: 'Radfahren', data: data.map(w => w.ride_km || 0), backgroundColor: 'rgba(245,158,11,.75)', stack: 'km', borderRadius: 3 },
    ], { scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'km' } } } });
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
                load(currentDays);
                loadWeekly();
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
document.getElementById('sync-btn').addEventListener('click', triggerSync);
document.getElementById('activities-container').addEventListener('click', e => {
    const tr = e.target.closest('tr[data-id]');
    if (tr) location.href = '/activity/' + tr.dataset.id;
});

// ── Init ───────────────────────────────────────────────────────────────────
load(currentDays).catch(() => showToast('Dashboard konnte nicht geladen werden', 'error'));
loadWeekly().catch(() => showToast('Wochendaten konnten nicht geladen werden', 'error'));
loadReadiness().catch(() => showToast('Readiness-Score konnte nicht geladen werden', 'error'));
loadMlInsights().catch(() => {});
loadEnergyMetrics().catch(() => {});
loadSyncStatus();
loadMlStatus();
