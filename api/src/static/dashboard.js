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

async function load(days) {
    const [activities, daily, sleep, hrv, hrvTrend, trainingStatus] = await Promise.all([
        fetch(`/api/activities?days=${days}`).then(r => r.json()),
        fetch(`/api/daily?days=${days}`).then(r => r.json()),
        fetch(`/api/sleep?days=${days}`).then(r => r.json()),
        fetch('/api/hrv').then(r => r.json()),
        fetch(`/api/hrv/trend?days=${days}`).then(r => r.json()),
        fetch('/api/training-status').then(r => r.json()),
    ]);

    // ── Hero Stats ────────────────────────────────────────────────────
    const last = daily[daily.length - 1];
    document.getElementById('stat-steps').textContent   = last?.steps?.toLocaleString('de-AT') ?? '—';
    document.getElementById('stat-sleep').textContent   = sleep[0]?.sleep_score ?? '—';
    document.getElementById('stat-hrv').textContent     = hrv?.hrv_weekly_avg ? hrv.hrv_weekly_avg + ' ms' : '—';
    document.getElementById('stat-battery').textContent = last?.body_battery_high ?? '—';

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
    if (hrvTrend && hrvTrend.some(h => h.hrv_weekly_avg || h.hrv_last_night)) {
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

    // ── HRV letzter Wert ──────────────────────────────────────────────
    const hrvEl = document.getElementById('hrv-container');
    if (!hrv) {
        hrvEl.innerHTML = '<p class="empty">Noch keine HRV-Daten.</p>';
    } else {
        const statusClass = (hrv.hrv_status || 'poor').toLowerCase();
        const statusLabels = { balanced: 'Ausgeglichen', unbalanced: 'Unausgeglichen', poor: 'Niedrig' };
        hrvEl.innerHTML = `<div class="kv-card">
            <div class="kv-row">
                <span class="kv-label">Wochenø</span>
                <span class="kv-value">${hrv.hrv_weekly_avg ?? '—'} ms</span>
            </div>
            <div class="kv-row">
                <span class="kv-label">Status</span>
                <span class="badge badge-${statusClass}">
                    ${statusLabels[statusClass] ?? hrv.hrv_status}
                </span>
            </div>
        </div>`;
    }

    // ── Trainingszustand ──────────────────────────────────────────────
    const tsEl = document.getElementById('training-status-container');
    if (!trainingStatus || !trainingStatus.training_status) {
        tsEl.innerHTML = '<p class="empty">Noch keine Daten — wird nach dem nächsten Sync befüllt.</p>';
    } else {
        const tsMap = {
            PRODUCTIVE:   { label: 'Aufbauend',       cls: 'badge-balanced' },
            MAINTAINING:  { label: 'Erhalt',          cls: 'badge-balanced' },
            RECOVERY:     { label: 'Erholung',        cls: 'badge-unbalanced' },
            UNPRODUCTIVE: { label: 'Nicht produktiv', cls: 'badge-unbalanced' },
            OVERREACHING: { label: 'Übertraining',    cls: 'badge-poor' },
            DETRAINING:   { label: 'Abfall',          cls: 'badge-poor' },
        };
        const key = (trainingStatus.training_status || '').toUpperCase();
        const entry = tsMap[key] || { label: trainingStatus.training_status, cls: 'badge-unbalanced' };
        const d = trainingStatus.date
            ? new Date(trainingStatus.date).toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit' })
            : '';
        tsEl.innerHTML = `<div class="kv-card">
            <div class="kv-row">
                <span class="kv-label">Status</span>
                <span class="badge ${entry.cls}">${entry.label}</span>
            </div>
            ${d ? `<div class="kv-row"><span class="kv-label">Stand</span><span class="kv-value" style="font-size:.85rem;color:var(--muted)">${d}</span></div>` : ''}
        </div>`;
    }
}

async function loadMlInsights() {
    const d = await fetch('/api/ml-insights').then(r => r.json());
    const anomaly = d['anomaly_hr'];
    const rf      = d['readiness_rf'];

    const tiles = [];

    if (anomaly && anomaly.z_score !== null) {
        const z   = anomaly.z_score.toFixed(2);
        const warn = anomaly.is_anomaly;
        const sub  = `Baseline Ø ${Math.round(anomaly.baseline_mean)} bpm`;
        tiles.push(`
            <a class="ml-kpi-tile${warn ? ' ml-kpi-tile-warn' : ''}" href="/ml/anomaly">
                <div class="stat-label">Ruhepuls z-Score</div>
                <div class="ml-kpi-val">${z}</div>
                <div class="ml-kpi-status">${warn ? '⚠ Anomalie' : '✓ Normal'}</div>
                <div class="ml-kpi-status" style="margin-top:3px;font-size:.74rem">${sub}</div>
            </a>`);
    }

    if (rf && rf.value !== null) {
        const score = Math.round(rf.value);
        const cls   = score >= 80 ? 'badge-balanced' : score >= 50 ? 'badge-unbalanced' : 'badge-poor';
        const label = score >= 80 ? 'Gut' : score >= 50 ? 'Moderat' : 'Niedrig';
        tiles.push(`
            <a class="ml-kpi-tile" href="/ml/readiness">
                <div class="stat-label">Prognose morgen</div>
                <div class="ml-kpi-val"><span class="badge ${cls}" style="font-size:1.8rem;padding:.15rem .55rem;vertical-align:middle">${score}</span></div>
                <div class="ml-kpi-status" style="margin-top:var(--sp-2)">${label} · Readiness (0–100)</div>
            </a>`);
    }

    if (!tiles.length) return;

    document.getElementById('ml-container').innerHTML = `<div class="ml-kpi-row">${tiles.join('')}</div>`;
    document.getElementById('ml-card').style.display = '';
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

async function loadReadiness() {
    const r = await fetch('/api/readiness').then(res => res.json());
    const el = document.getElementById('readiness-hero');
    if (!r || r.score === null) {
        el.innerHTML = '<p class="empty" style="padding:var(--sp-8) 0">Noch keine Readiness-Daten — Sync läuft täglich um 6 Uhr.</p>';
        return;
    }
    const scoreColors = {
        'badge-balanced':   { color: '#22c55e', glow: 'rgba(34,197,94,.3)'   },
        'badge-unbalanced': { color: '#f59e0b', glow: 'rgba(245,158,11,.25)' },
        'badge-poor':       { color: '#ef4444', glow: 'rgba(239,68,68,.25)'  },
    };
    const { color, glow } = scoreColors[r.cls] || scoreColors['badge-poor'];
    el.style.boxShadow = `0 0 80px ${glow}, 0 4px 24px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.06)`;

    const hrvLabels = { balanced: 'Ausgeglichen', unbalanced: 'Unausgeglichen', low: 'Niedrig', poor: 'Niedrig' };
    const factors = [
        r.hrv_status     ? { label: 'HRV',          val: hrvLabels[(r.hrv_status||'').toLowerCase()] ?? r.hrv_status } : null,
        r.sleep_score   != null ? { label: 'Schlaf',       val: r.sleep_score + ' / 100' } : null,
        r.body_battery  != null ? { label: 'Body Battery', val: r.body_battery }             : null,
        r.avg_stress    != null ? { label: 'Stress',       val: r.avg_stress }               : null,
    ].filter(Boolean);

    el.innerHTML = `
        <div class="readiness-header">
            <h2>Readiness</h2>
            <div class="readiness-info-wrap">
                <button class="readiness-info-btn" aria-label="Berechnungsmethode" aria-expanded="false">ⓘ</button>
                <div class="readiness-info-panel" role="tooltip">
                    <p class="readiness-info-title">Wie wird der Score berechnet?</p>
                    <ul class="readiness-info-list">
                        <li><strong>HRV-Status</strong> <span style="color:var(--muted)">30&nbsp;%</span> — BALANCED=100, UNBALANCED=50, LOW=25, POOR=0</li>
                        <li><strong>Schlaf-Score</strong> <span style="color:var(--muted)">30&nbsp;%</span> — Garmin Schlaf-Score (0–100)</li>
                        <li><strong>Body Battery</strong> <span style="color:var(--muted)">20&nbsp;%</span> — Tages-Maximum (0–100)</li>
                        <li><strong>Stress</strong> <span style="color:var(--muted)">20&nbsp;%</span> — (100 − Ø Stress), niedriger = besser</li>
                    </ul>
                    <p class="readiness-info-note">Fehlende Werte werden herausgerechnet; Gewichte proportional verteilt.</p>
                </div>
            </div>
        </div>
        <div style="display:flex;align-items:baseline;gap:var(--sp-4);flex-wrap:wrap">
            <div class="readiness-score" style="color:${color}">${r.score}</div>
            <span class="badge ${r.cls}" style="margin-bottom:var(--sp-2)">${r.label}</span>
        </div>
        <div class="readiness-factors">
            ${factors.map(f => `<span class="readiness-factor">${f.label}<strong>${f.val}</strong></span>`).join('')}
        </div>`;

    const infoBtn = el.querySelector('.readiness-info-btn');
    const infoPanel = el.querySelector('.readiness-info-panel');
    infoBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const pinned = infoPanel.classList.toggle('pinned');
        infoBtn.setAttribute('aria-expanded', String(pinned));
    });
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
document.addEventListener('click', () => {
    const panel = document.querySelector('.readiness-info-panel.pinned');
    if (!panel) return;
    panel.classList.remove('pinned');
    const btn = document.querySelector('.readiness-info-btn');
    if (btn) btn.setAttribute('aria-expanded', 'false');
});

// ── Glukose ────────────────────────────────────────────────────────────────

async function loadGlucose() {
    if (!document.getElementById('glucose-val')) return;
    const data = await fetch('/api/glucose?hours=1').then(r => r.json());
    if (!data.length) return;
    const latest = data[0];
    const TREND  = { 1: '↓↓', 2: '↓', 3: '→', 4: '↑', 5: '↑↑' };
    document.getElementById('glucose-val').textContent =
        `${Math.round(latest.value_mgdl)} mg/dL`;
    const trend = TREND[latest.trend] ?? '';
    const flag  = latest.is_low ? ' · Hypo ⚠' : latest.is_high ? ' · Hoch' : '';
    document.getElementById('glucose-sub').textContent = `${trend}${flag}`;
}

// ── Init ───────────────────────────────────────────────────────────────────
load(currentDays).catch(() => showToast('Dashboard konnte nicht geladen werden', 'error'));
loadWeekly().catch(() => showToast('Wochendaten konnten nicht geladen werden', 'error'));
loadReadiness().catch(() => showToast('Readiness-Score konnte nicht geladen werden', 'error'));
loadMlInsights().catch(() => {});
loadGlucose().catch(() => {});
loadSyncStatus();
