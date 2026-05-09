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

function metricTile({ label, value, sub = '', info, sectionLabel = '' }) {
    const infoAttr = info
        ? ` data-info="${encodeURIComponent(JSON.stringify({ ...info, sectionLabel }))}"` : '';
    return `<div class="metric-tile"${infoAttr}>
        <div class="metric-tile-label">${label}</div>
        <div class="metric-tile-value">${value}</div>
        <div class="metric-tile-sub">${sub}</div>
        ${info ? '<div class="metric-tile-hint">Tippen für Details</div>' : ''}
    </div>`;
}

// ─── Modal ─────────────────────────────────────────────────────────────────
function openMetricModal(info) {
    document.getElementById('modal-section-label').textContent = info.sectionLabel || '';
    document.getElementById('modal-title').textContent = info.title;
    const inputsEl = document.getElementById('modal-inputs');
    inputsEl.innerHTML = info.inputs.map(i =>
        `<li><strong>${i.name}</strong>${i.weight ? `<span class="weight"> ${i.weight}</span>` : ''} — ${i.desc}</li>`
    ).join('');
    const eli5El   = document.getElementById('modal-eli5');
    const eli5LblEl = document.getElementById('modal-eli5-label');
    if (info.eli5) {
        eli5El.textContent = info.eli5;
        eli5El.style.display = '';
        eli5LblEl.style.display = '';
    } else {
        eli5El.style.display = 'none';
        eli5LblEl.style.display = 'none';
    }
    document.getElementById('metric-modal').removeAttribute('hidden');
    document.getElementById('modal-close').focus();
}

function closeMetricModal() {
    document.getElementById('metric-modal').setAttribute('hidden', '');
}

function buildMetricsHero() {
    const el = document.getElementById('metrics-hero');
    if (!el) return;

    const r        = _heroData.readiness;
    const daily    = _heroData.daily || [];
    const sleep    = _heroData.sleep || [];
    const hrv      = _heroData.hrv;
    const ts       = _heroData.trainingStatus;
    const energy   = _heroData.energy || {};
    const ml       = _heroData.ml || {};

    const last = daily[daily.length - 1];

    // ── Readiness Header ────────────────────────────────────────────────
    let readinessBlock = '';
    if (!r || r.score === null) {
        readinessBlock = `
            <div class="metric-section-label">Readiness</div>
            <p class="empty">Noch keine Readiness-Daten — Sync läuft täglich um 6 Uhr.</p>`;
    } else {
        const scoreColors = {
            'badge-balanced':   { color: '#22c55e' },
            'badge-unbalanced': { color: '#f59e0b' },
            'badge-poor':       { color: '#ef4444' },
        };
        const { color } = scoreColors[r.cls] || scoreColors['badge-poor'];
        readinessBlock = `
            <div class="metric-section-label">Readiness</div>
            <div class="readiness-header" style="margin-bottom:var(--sp-3)">
                <div style="display:flex;align-items:baseline;gap:var(--sp-4);flex-wrap:wrap">
                    <div class="readiness-score" style="color:${color}">${r.score}</div>
                    <span class="badge ${r.cls}" style="margin-bottom:var(--sp-2)">${r.label}</span>
                </div>
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
            </div>`;
    }

    // ── Garmin-Daten Tiles ──────────────────────────────────────────────
    const garminTiles = [
        metricTile({
            label: 'Schritte',
            value: last?.steps?.toLocaleString('de-AT') ?? '—',
            sectionLabel: 'Garmin-Daten',
            info: {
                title: 'Schritte',
                inputs: [
                    { name: 'daily_summary.steps', desc: 'Tagesschritte vom Garmin-Gerät' },
                ],
                eli5: 'Dein Garmin zählt jeden Schritt mit dem eingebauten Beschleunigungsmesser — wie ein mechanischer Schrittzähler, nur viel genauer.',
            },
        }),
        metricTile({
            label: 'Schlaf-Score',
            value: sleep[0]?.sleep_score ?? '—',
            sectionLabel: 'Garmin-Daten',
            info: {
                title: 'Schlaf-Score (Garmin)',
                inputs: [
                    { name: 'sleep_sessions.sleep_score', desc: 'Garmin-Algorithmus (0–100)' },
                    { name: 'Schlafphasen', desc: 'Tief, REM, Leicht, Wach' },
                ],
                eli5: 'Garmin schaut, wie lange du geschlafen hast, wie viel Tiefschlaf und REM dabei war, und gibt dir eine Note von 0–100.',
            },
        }),
        metricTile({
            label: 'HRV Wochenø',
            value: hrv?.hrv_weekly_avg ? hrv.hrv_weekly_avg + ' ms' : '—',
            sectionLabel: 'Garmin-Daten',
            info: {
                title: 'Herzratenvariabilität (HRV)',
                inputs: [
                    { name: 'hrv_daily.hrv_weekly_avg', desc: 'Durchschnitt RMSSD letzte 7 Nächte (ms)' },
                ],
                eli5: 'Dein Herz schlägt nicht gleichmäßig — zwischen je zwei Schlägen gibt es kleine Unterschiede. Je größer diese Unterschiede, desto erholter bist du. Der Wert hier ist der Durchschnitt der letzten 7 Nächte.',
            },
        }),
        metricTile({
            label: 'Body Battery',
            value: last?.body_battery_high ?? '—',
            sectionLabel: 'Garmin-Daten',
            info: {
                title: 'Body Battery (Garmin Firstbeat)',
                inputs: [
                    { name: 'daily_summary.body_battery_high', desc: 'Tages-Maximum (0–100)' },
                ],
                eli5: 'Stell dir einen Akku vor: Sport verbraucht Energie, Schlaf und Erholung laden ihn wieder auf. Garmin berechnet das mit deinem HRV und Stresslevel.',
            },
        }),
    ];

    const garminBlock = `
        <div class="metric-section-label">Garmin-Daten</div>
        <div class="metric-grid">${garminTiles.join('')}</div>`;

    // ── Energie Tiles ───────────────────────────────────────────────────
    const phys  = energy.energy_physical;
    const auton = energy.energy_autonomic;
    const cog   = energy.energy_cognitive;
    const energyTiles = [];

    if (phys?.score != null) {
        const tsb = phys.tsb != null
            ? (phys.tsb >= 0 ? `TSB +${phys.tsb.toFixed(1)}` : `TSB ${phys.tsb.toFixed(1)}`)
            : '';
        energyTiles.push(metricTile({
            label: 'Physisch',
            value: Math.round(phys.score),
            sub: tsb,
            sectionLabel: 'Energie',
            info: {
                title: 'Physische Energie (TSB)',
                inputs: [
                    { name: 'Aktivitäten 50 Tage', desc: 'avg_hr + duration_seconds → Edwards TRIMP' },
                    { name: 'ATL', weight: 'τ=7d',  desc: 'Acute Training Load (kurzfristige Erschöpfung)' },
                    { name: 'CTL', weight: 'τ=42d', desc: 'Chronic Training Load (Fitness-Basis)' },
                    { name: 'TSB', desc: 'CTL − ATL = Erholungsbalance' },
                ],
                eli5: 'Denk an ein Sparkonto: Jedes Training hebt Geld ab (Erschöpfung), jeder Ruhetag zahlt Zinsen ein (Erholung). TSB = Kontostand. Positiv = du bist ausgeruht.',
            },
        }));
    } else {
        energyTiles.push(metricTile({ label: 'Physisch', value: '—', sub: 'noch keine Daten' }));
    }

    if (auton?.score != null) {
        const dev = auton.deviation != null
            ? `${auton.deviation >= 0 ? '+' : ''}${auton.deviation.toFixed(1)}σ`
            : '';
        energyTiles.push(metricTile({
            label: 'Autonom',
            value: Math.round(auton.score),
            sub: dev,
            sectionLabel: 'Energie',
            info: {
                title: 'Autonome Energie (HRV-Baseline)',
                inputs: [
                    { name: 'hrv_daily.hrv_last_night', desc: 'Letzte 90 Tage' },
                    { name: 'ln-Normierung', desc: 'logarithmische Glättung' },
                    { name: 'σ-Abweichung', desc: 'aktueller Wert vs. eigene Baseline' },
                ],
                eli5: 'Wir vergleichen dein heutiges HRV nur mit deinem eigenen Normalwert der letzten 90 Tage. Score 50 = genau dein Durchschnitt, >70 = du bist besser erholt als üblich.',
            },
        }));
    } else {
        energyTiles.push(metricTile({ label: 'Autonom', value: '—', sub: 'noch keine Daten' }));
    }

    if (cog?.score != null) {
        const debt = cog.debt_hours != null ? `${cog.debt_hours.toFixed(1)}h Schulden` : '';
        energyTiles.push(metricTile({
            label: 'Kognitiv',
            value: Math.round(cog.score),
            sub: debt,
            sectionLabel: 'Energie',
            info: {
                title: 'Kognitive Energie (Schlafschuld)',
                inputs: [
                    { name: 'sleep_sessions.total_sleep_seconds', desc: 'Letzte 7 Nächte' },
                    { name: 'Optimal', weight: '8h', desc: 'Soll-Schlafdauer pro Nacht' },
                    { name: 'Debt', desc: 'Summe der Differenzen zu Optimal' },
                ],
                eli5: 'Jede Nacht mit zu wenig Schlaf packt dir etwas in einen unsichtbaren Rucksack. Score 100 = leerer Rucksack, niedriger Score = du trägst Schlafschuld mit dir.',
            },
        }));
    } else {
        energyTiles.push(metricTile({ label: 'Kognitiv', value: '—', sub: 'noch keine Daten' }));
    }

    const energyBlock = `
        <div class="metric-section-label">Energie</div>
        <div class="metric-grid">${energyTiles.join('')}</div>`;

    // ── ML Tiles + HRV-Status + Trainingszustand ────────────────────────
    const anomaly = ml.anomaly_hr;
    const rf      = ml.readiness_rf;
    const mlTiles = [];

    if (anomaly && anomaly.z_score !== null && anomaly.z_score !== undefined) {
        mlTiles.push(metricTile({
            label: 'Ruhepuls Z-Score',
            value: anomaly.z_score.toFixed(2),
            sub: anomaly.is_anomaly ? '⚠ Anomalie' : `✓ Normal (Ø ${Math.round(anomaly.baseline_mean)} bpm)`,
            sectionLabel: 'ML & Status',
            info: {
                title: 'Anomalie-Erkennung (Z-Score)',
                inputs: [
                    { name: 'daily_summary.resting_hr', desc: '30-Tage-Rolling-Baseline (min. 7 Punkte)' },
                    { name: 'Z = (x − μ) / σ', desc: 'wie viele Standardabweichungen vom Mittelwert' },
                ],
                eli5: 'Wir schauen, ob dein heutiger Ruhepuls ungewöhnlich hoch oder niedrig ist — verglichen mit deinem eigenen Normalwert der letzten 30 Tage. 0 = normal, >2 = Anomalie.',
            },
        }));
    } else {
        mlTiles.push(metricTile({ label: 'Ruhepuls Z-Score', value: '—', sub: 'zu wenig Daten' }));
    }

    if (rf && rf.value !== null && rf.value !== undefined) {
        const score = Math.round(rf.value);
        const cls   = score >= 80 ? 'badge-balanced' : score >= 50 ? 'badge-unbalanced' : 'badge-poor';
        const rfLabel = score >= 80 ? 'Gut' : score >= 50 ? 'Moderat' : 'Niedrig';
        mlTiles.push(metricTile({
            label: 'Prognose morgen',
            value: `<span class="badge ${cls}" style="font-size:1.4rem;padding:.1rem .5rem">${score}</span>`,
            sub: `${rfLabel} · Readiness (0–100)`,
            sectionLabel: 'ML & Status',
            info: {
                title: 'Readiness-Prognose (Random Forest)',
                inputs: [
                    { name: 'hrv_last_night', desc: 'HRV letzte Nacht' },
                    { name: 'sleep_score', desc: 'Schlaf-Score' },
                    { name: 'resting_hr', desc: 'Ruhepuls' },
                ],
                eli5: 'Ein Computerprogramm hat aus deinen vergangenen Daten gelernt, wie sich dein Körper verhält. Es sagt vorher, wie fit du morgen sein wirst — basierend auf HRV, Schlaf und Ruhepuls.',
            },
        }));
    } else {
        mlTiles.push(metricTile({ label: 'Prognose morgen', value: '—', sub: 'Modell trainiert sonntags' }));
    }

    const hrvStatusLabels = { balanced: 'Ausgeglichen', unbalanced: 'Unausgeglichen', low: 'Niedrig', poor: 'Niedrig' };
    const hrvStatusKey = (hrv?.hrv_status || '').toLowerCase();
    const hrvStatusVal = hrvStatusLabels[hrvStatusKey] ?? (hrv?.hrv_status ?? '—');
    const hrvStatusBadgeCls = hrvStatusKey === 'balanced' ? 'badge-balanced'
        : hrvStatusKey === 'unbalanced' ? 'badge-unbalanced'
        : (hrvStatusKey === 'low' || hrvStatusKey === 'poor') ? 'badge-poor' : '';
    mlTiles.push(metricTile({
        label: 'HRV-Status',
        value: hrvStatusBadgeCls
            ? `<span class="badge ${hrvStatusBadgeCls}" style="font-size:1rem;padding:.1rem .5rem">${hrvStatusVal}</span>`
            : '—',
        sub: hrv?.hrv_last_night ? `${hrv.hrv_last_night} ms letzte Nacht` : '',
        sectionLabel: 'ML & Status',
        info: {
            title: 'HRV-Status (Garmin)',
            inputs: [
                { name: 'hrv_daily.hrv_status', desc: 'Garmin-Klassifikation: BALANCED / UNBALANCED / LOW / POOR' },
            ],
            eli5: 'Garmin vergleicht dein heutiges HRV mit deinen letzten 3 Wochen und gibt dir ein Label: Ausgeglichen (gut), Unausgeglichen (mittel), Niedrig (schlecht).',
        },
    }));

    const tsMap = {
        PRODUCTIVE:   { label: 'Aufbauend',       cls: 'badge-balanced'   },
        MAINTAINING:  { label: 'Erhalt',          cls: 'badge-balanced'   },
        RECOVERY:     { label: 'Erholung',        cls: 'badge-unbalanced' },
        UNPRODUCTIVE: { label: 'Nicht produktiv', cls: 'badge-unbalanced' },
        OVERREACHING: { label: 'Übertraining',    cls: 'badge-poor'       },
        DETRAINING:   { label: 'Abfall',          cls: 'badge-poor'       },
    };
    if (ts && ts.training_status) {
        const key   = (ts.training_status || '').toUpperCase();
        const entry = tsMap[key] || { label: ts.training_status, cls: 'badge-unbalanced' };
        const dStr  = ts.date
            ? new Date(ts.date).toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit' })
            : '';
        mlTiles.push(metricTile({
            label: 'Trainingszustand',
            value: `<span class="badge ${entry.cls}" style="font-size:1rem;padding:.1rem .5rem">${entry.label}</span>`,
            sub: dStr ? `Stand ${dStr}` : '',
            sectionLabel: 'ML & Status',
            info: {
                title: 'Trainingszustand (Garmin Firstbeat)',
                inputs: [
                    { name: 'daily_summary.training_status', desc: 'Garmin-Algorithmus aus Trainingsbelastung der letzten Wochen' },
                ],
                eli5: 'Garmin schaut auf deine Trainingsbelastung der letzten Wochen und sagt dir, ob du dich gerade aufbaust, erhältst oder überlastest.',
            },
        }));
    } else {
        mlTiles.push(metricTile({
            label: 'Trainingszustand',
            value: '—',
            sub: 'wird nach Sync befüllt',
        }));
    }

    const mlBlock = `
        <div class="metric-section-label">ML &amp; Status</div>
        <div class="metric-grid">${mlTiles.join('')}</div>`;

    el.innerHTML = readinessBlock + garminBlock + energyBlock + mlBlock;
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
    buildMetricsHero();

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
}

async function loadReadiness() {
    const r = await fetch('/api/readiness').then(res => res.json());
    _heroData.readiness = r;
    buildMetricsHero();
}

async function loadMlInsights() {
    const d = await fetch('/api/ml-insights').then(r => r.json());
    _heroData.ml = d;
    buildMetricsHero();
}

async function loadEnergyMetrics() {
    const d = await fetch('/api/energy').then(r => r.json());
    _heroData.energy = d;
    buildMetricsHero();
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

// Tile click → Modal
document.getElementById('metrics-hero').addEventListener('click', e => {
    const tile = e.target.closest('.metric-tile[data-info]');
    if (!tile) return;
    try {
        const info = JSON.parse(decodeURIComponent(tile.dataset.info));
        openMetricModal(info);
    } catch { /* ignore */ }
});

// Modal schließen
document.getElementById('modal-close').addEventListener('click', closeMetricModal);
document.getElementById('modal-backdrop').addEventListener('click', closeMetricModal);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMetricModal(); });

// ── Init ───────────────────────────────────────────────────────────────────
load(currentDays).catch(() => showToast('Dashboard konnte nicht geladen werden', 'error'));
loadWeekly().catch(() => showToast('Wochendaten konnten nicht geladen werden', 'error'));
loadReadiness().catch(() => showToast('Readiness-Score konnte nicht geladen werden', 'error'));
loadMlInsights().catch(() => {});
loadEnergyMetrics().catch(() => {});
loadSyncStatus();
loadMlStatus();
