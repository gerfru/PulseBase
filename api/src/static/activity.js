import { buildChartDataTable, isDark } from './chart-utils.js';
import { SPORT_EMOJI, SPORT_LABEL, fmtDuration, fmtDist, esc } from './dashboard-utils.js';
const TS_LABELS = {
    PRODUCTIVE: { label: 'Aufbauend', cls: 'badge-balanced' },
    MAINTAINING: { label: 'Erhalt', cls: 'badge-balanced' },
    RECOVERY: { label: 'Erholung', cls: 'badge-unbalanced' },
    UNPRODUCTIVE: { label: 'Nicht produktiv', cls: 'badge-unbalanced' },
    OVERREACHING: { label: 'Übertraining', cls: 'badge-poor' },
    DETRAINING: { label: 'Abfall', cls: 'badge-poor' },
};

function fmtPace(secPerKm) {
    if (!secPerKm) return '—';
    const m = Math.floor(secPerKm / 60),
        s = Math.round(secPerKm % 60);
    return `${m}:${s.toString().padStart(2, '0')} /km`;
}
function fmtSpeed(kmh) {
    return kmh ? `${kmh.toFixed(1)} km/h` : '—';
}
function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('de-AT', {
        weekday: 'long',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
    });
}
function fmtTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
}

// RPE color scale: green (easy) → red (max effort), Foster et al. (2001)
const RPE_COLORS = [
    '#22c55e',
    '#4ade80',
    '#a3e635',
    '#facc15',
    '#f59e0b',
    '#fb923c',
    '#f97316',
    '#ef4444',
    '#dc2626',
    '#991b1b',
];
const RPE_LABELS = [
    'Sehr leicht',
    'Leicht',
    'Moderat',
    'Etwas anstrengend',
    'Anstrengend',
    'Sehr anstrengend',
    'Sehr anstrengend',
    'Extrem anstrengend',
    'Extrem anstrengend',
    'Maximale Anstrengung',
];

function renderRpe(activityId, initialRpe, avgHr, durationSeconds) {
    const container = document.getElementById('rpe-chips');
    const hintEl = document.getElementById('rpe-hint');
    let current = initialRpe || null;

    function updateStats(rpe) {
        const statsEl = document.getElementById('rpe-stats');
        if (!rpe) {
            statsEl.style.display = 'none';
            return;
        }
        statsEl.style.display = '';
        const durationMin = (durationSeconds || 0) / 60;
        document.getElementById('rpe-session-load').textContent = `${Math.round(rpe * durationMin)} AU`;
        document.getElementById('rpe-hr-ratio').textContent = avgHr ? `${(avgHr / rpe).toFixed(1)} bpm/RPE` : '—';
    }

    function renderChips(activeRpe) {
        container.innerHTML = RPE_COLORS.map((color, i) => {
            const n = i + 1;
            return `<button class="rpe-chip${n === activeRpe ? ' active' : ''}"
                        style="--rpe-color:${color}"
                        data-rpe="${n}"
                        aria-label="RPE ${n}: ${RPE_LABELS[i]}"
                        title="${RPE_LABELS[i]}">${n}</button>`;
        }).join('');
        hintEl.textContent = activeRpe ? RPE_LABELS[activeRpe - 1] : 'Bewerte deine Anstrengung (1–10)';
        updateStats(activeRpe);
    }

    renderChips(current);

    container.addEventListener('click', async (e) => {
        const btn = e.target.closest('.rpe-chip');
        if (!btn) return;
        const rpe = parseInt(btn.dataset.rpe, 10);
        current = rpe;
        renderChips(current);
        try {
            const res = await fetch(`/api/activities/${activityId}/rpe`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rpe }),
            });
            if (!res.ok) throw new Error();
        } catch {
            hintEl.textContent = 'Speichern fehlgeschlagen — bitte nochmal versuchen';
        }
    });
}

// Chart.defaults werden zentral in chart-utils.js gesetzt (beim Import oben).

function makeChart(id, type, labels, datasets, scales = {}, ariaLabel = '') {
    const canvas = document.getElementById(id);
    // Accessibility: Textalternative + Datentabelle fuer Screenreader (WCAG 1.1.1).
    const label = ariaLabel || `Liniendiagramm mit ${labels.length} Messpunkten`;
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', label);
    buildChartDataTable(canvas, labels, datasets, label);
    return new Chart(canvas, {
        type,
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { display: false } },
            scales,
        },
    });
}

function statTile(label, value) {
    return `<div class="stat-tile"><div class="stat-label">${esc(label)}</div><div class="stat-value" style="font-size:1.2rem">${esc(value)}</div></div>`;
}

function econColor(val, lo, hi) {
    if (val == null) return null;
    if (val <= lo) return 'var(--green)';
    if (val <= hi) return 'var(--amber)';
    return 'var(--red)';
}

function econRow(label, val, sub, color) {
    return `<div class="kv-row">
        <span class="kv-label">${esc(label)}${sub ? `<small class="kv-sub">${esc(sub)}</small>` : ''}</span>
        <span class="kv-value"${color ? ` style="color:${color}"` : ''}>${esc(String(val ?? '—'))}</span>
    </div>`;
}

function renderEconomy(a) {
    if (a.sport_type !== 'running' && a.sport_type !== 'trail_running') return;
    const hasData =
        a.avg_ground_contact_time ||
        a.avg_vertical_oscillation ||
        a.avg_stride_length ||
        a.avg_vertical_ratio ||
        a.avg_running_power;
    if (!hasData) return;

    const rows = [];
    if (a.avg_ground_contact_time)
        rows.push(
            econRow(
                'Bodenkontaktzeit',
                `${a.avg_ground_contact_time} ms`,
                '< 240 ms optimal',
                econColor(a.avg_ground_contact_time, 240, 270),
            ),
        );
    if (a.avg_vertical_oscillation)
        rows.push(
            econRow(
                'Vertikale Oszillation',
                `${a.avg_vertical_oscillation.toFixed(1)} cm`,
                '< 8 cm optimal',
                econColor(a.avg_vertical_oscillation, 8, 10),
            ),
        );
    if (a.avg_stride_length)
        rows.push(econRow('Schrittlänge', `${(a.avg_stride_length / 100).toFixed(2)} m`, '', null));
    if (a.avg_vertical_ratio)
        rows.push(
            econRow(
                'Vertikales Verhältnis',
                `${a.avg_vertical_ratio.toFixed(1)} %`,
                '< 8 % optimal',
                econColor(a.avg_vertical_ratio, 8, 10),
            ),
        );
    if (a.avg_running_power) rows.push(econRow('Laufleistung', `${a.avg_running_power} W`, '', null));

    document.getElementById('economy-rows').innerHTML = rows.join('');
    document.getElementById('economy-card').style.display = '';
}

async function load() {
    const id = location.pathname.split('/').pop();
    const a = await fetch(`/api/activities/${id}`).then((r) => r.json());

    // Header
    const emoji = SPORT_EMOJI[a.sport_type] || SPORT_EMOJI.default;
    const sportName = SPORT_LABEL[a.sport_type] || esc((a.sport_type || 'Sonstige').replace(/_/g, ' '));
    document.getElementById('act-title').textContent = `${emoji} ${sportName}`;
    document.getElementById('act-meta').textContent = `${fmtDate(a.started_at)} · ${fmtTime(a.started_at)}`;
    document.title = `PulseBase — ${sportName}`;

    // Stat Grid
    const isRunning = a.sport_type === 'running' || a.sport_type === 'hiking' || a.sport_type === 'walking';
    const isCycling = a.sport_type === 'cycling';
    const stats = [
        ['Distanz', fmtDist(a.distance_meters)],
        ['Dauer', fmtDuration(a.duration_seconds)],
        ['Kalorien', a.calories ? `${a.calories} kcal` : '—'],
        [isRunning ? 'Ø Pace' : 'Ø Speed', isRunning ? fmtPace(a.avg_pace_sec_per_km) : fmtSpeed(a.avg_speed_kmh)],
        ['Ø HR', a.avg_hr ? `${a.avg_hr} bpm` : '—'],
        ['Höhenmeter', a.elevation_gain ? `+${Math.round(a.elevation_gain)} m` : '—'],
    ];
    document.getElementById('stat-grid').innerHTML = stats.map(([l, v]) => statTile(l, v)).join('');

    // RPE — Session-RPE (Foster et al. 2001): subjektive Anstrengung 1–10
    renderRpe(id, a.user_rpe, a.avg_hr, a.duration_seconds);
    renderEconomy(a);

    // Training Effect
    if (a.aerobic_effect || a.anaerobic_effect) {
        document.getElementById('effect-card').style.display = '';
        if (a.aerobic_effect) {
            document.getElementById('fill-aerobic').style.width = `${(a.aerobic_effect / 5) * 100}%`;
            document.getElementById('val-aerobic').textContent = a.aerobic_effect.toFixed(1);
        }
        if (a.anaerobic_effect) {
            document.getElementById('fill-anaerobic').style.width = `${(a.anaerobic_effect / 5) * 100}%`;
            document.getElementById('val-anaerobic').textContent = a.anaerobic_effect.toFixed(1);
        }
    }
    if (a.training_status) {
        const ts = TS_LABELS[(a.training_status || '').toUpperCase()] || {
            label: a.training_status,
            cls: 'badge-unbalanced',
        };
        document.getElementById('training-status-row').style.display = '';
        const span = document.createElement('span');
        span.className = `badge ${ts.cls}`;
        span.textContent = ts.label;
        const badge = document.getElementById('training-status-badge');
        badge.textContent = '';
        badge.appendChild(span);
    }

    const records = a.records || [];
    if (!records.length) return;

    // Time axis: minutes from start
    const t0 = new Date(records[0].time).getTime();
    const xLabels = records.map((r) => {
        const min = (new Date(r.time) - t0) / 60000;
        return `${min.toFixed(0)}'`;
    });

    // GPS Map
    const gpsPoints = records.filter((r) => r.lat && r.lng).map((r) => [r.lat, r.lng]);
    if (gpsPoints.length > 1) {
        document.getElementById('map-card').style.display = '';
        // Accessibility (WCAG 1.1.1 / 2.1.1): Die Routen-Textzusammenfassung in
        // #map-summary traegt den Inhalt fuer Screenreader. Auf dem #map-Div KEIN
        // role="img" (das wuerde die interaktive Karte als statisches Bild
        // maskieren und die Tastatur-Bedienung verstecken). Stattdessen ein
        // aria-label als zugaenglicher Name; Leaflets keyboard-Handler (Default an)
        // macht den Container fokussierbar (Pfeiltasten = verschieben, +/- = Zoom).
        const mapEl = document.getElementById('map');
        const routeSummary = `Streckenkarte: ${sportName} über ${fmtDist(a.distance_meters)}, Dauer ${fmtDuration(a.duration_seconds)}.`;
        mapEl.setAttribute('aria-label', routeSummary);
        const mapSummaryEl = document.getElementById('map-summary');
        if (mapSummaryEl) mapSummaryEl.textContent = routeSummary;
        const map = L.map('map', { keyboard: true });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 18,
        }).addTo(map);
        const track = L.polyline(gpsPoints, { color: C.indigo, weight: 3, opacity: 0.85 }).addTo(map);
        map.fitBounds(track.getBounds().pad(0.12));
        L.circleMarker(gpsPoints[0], {
            radius: 7,
            color: C.green,
            fillColor: C.green,
            fillOpacity: 1,
            weight: 2,
        }).addTo(map);
        L.circleMarker(gpsPoints[gpsPoints.length - 1], {
            radius: 7,
            color: C.red,
            fillColor: C.red,
            fillOpacity: 1,
            weight: 2,
        }).addTo(map);
    }

    // HR Chart
    if (records.some((r) => r.heart_rate)) {
        document.getElementById('hr-card').style.display = '';
        makeChart(
            'hr-chart',
            'line',
            xLabels,
            [
                {
                    data: records.map((r) => r.heart_rate),
                    borderColor: C.red,
                    backgroundColor: 'transparent',
                    pointRadius: 0,
                    tension: 0.3,
                },
            ],
            { y: { beginAtZero: false } },
            'Herzfrequenz-Verlauf der Aktivität',
        );
    }

    // Pace or Speed Chart
    if (isRunning && records.some((r) => r.pace_sec_per_km)) {
        document.getElementById('pace-card').style.display = '';
        document.getElementById('pace-title').textContent = 'Pace';
        makeChart(
            'pace-chart',
            'line',
            xLabels,
            [
                {
                    data: records.map((r) => (r.pace_sec_per_km ? +(r.pace_sec_per_km / 60).toFixed(2) : null)),
                    borderColor: C.indigo,
                    backgroundColor: 'transparent',
                    pointRadius: 0,
                    tension: 0.3,
                },
            ],
            { y: { reverse: true, title: { display: true, text: 'min/km' } } },
            'Pace-Verlauf in Minuten pro Kilometer',
        );
    } else if (isCycling && records.some((r) => r.pace_sec_per_km)) {
        document.getElementById('pace-card').style.display = '';
        document.getElementById('pace-title').textContent = 'Geschwindigkeit';
        makeChart(
            'pace-chart',
            'line',
            xLabels,
            [
                {
                    data: records.map((r) =>
                        r.pace_sec_per_km ? +((1000 / r.pace_sec_per_km) * 3.6).toFixed(1) : null,
                    ),
                    borderColor: C.indigo,
                    backgroundColor: 'transparent',
                    pointRadius: 0,
                    tension: 0.3,
                },
            ],
            { y: { title: { display: true, text: 'km/h' } } },
            'Geschwindigkeits-Verlauf in Kilometern pro Stunde',
        );
    }

    // Elevation Chart
    if (records.some((r) => r.elevation)) {
        document.getElementById('elev-card').style.display = '';
        makeChart(
            'elev-chart',
            'line',
            xLabels,
            [
                {
                    data: records.map((r) => (r.elevation ? +r.elevation.toFixed(1) : null)),
                    borderColor: C.amber,
                    backgroundColor: isDark ? 'rgba(245,158,11,.1)' : 'rgba(245,158,11,.08)',
                    fill: true,
                    pointRadius: 0,
                    tension: 0.3,
                },
            ],
            { y: { title: { display: true, text: 'm' } } },
            'Höhenprofil der Aktivität in Metern',
        );
    }

    // Cadence Chart
    if (records.some((r) => r.cadence)) {
        document.getElementById('cadence-card').style.display = '';
        makeChart(
            'cadence-chart',
            'line',
            xLabels,
            [
                {
                    data: records.map((r) => r.cadence),
                    borderColor: C.green,
                    backgroundColor: 'transparent',
                    pointRadius: 0,
                    tension: 0.3,
                },
            ],
            { y: { beginAtZero: false } },
            'Trittfrequenz-Verlauf der Aktivität',
        );
    }
}

load().catch((err) => console.error('Activity load error:', err));
