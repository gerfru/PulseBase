const SPORT_EMOJI = {
    running: '🏃', cycling: '🚴', swimming: '🏊', walking: '🚶',
    hiking: '🥾', strength_training: '🏋️', yoga: '🧘',
    indoor_cycling: '🚴', trail_running: '🏔️', open_water_swimming: '🌊',
    cardio: '💪', elliptical: '🔄', fitness_equipment: '🏋️', default: '⚡'
};
const TS_LABELS = {
    PRODUCTIVE: { label: 'Aufbauend', cls: 'badge-balanced' },
    MAINTAINING: { label: 'Erhalt', cls: 'badge-balanced' },
    RECOVERY: { label: 'Erholung', cls: 'badge-unbalanced' },
    UNPRODUCTIVE: { label: 'Nicht produktiv', cls: 'badge-unbalanced' },
    OVERREACHING: { label: 'Übertraining', cls: 'badge-poor' },
    DETRAINING: { label: 'Abfall', cls: 'badge-poor' },
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
function fmtDist(m) { return m ? (m / 1000).toFixed(2) + ' km' : '—'; }
function fmtPace(secPerKm) {
    if (!secPerKm) return '—';
    const m = Math.floor(secPerKm / 60), s = Math.round(secPerKm % 60);
    return `${m}:${s.toString().padStart(2, '0')} /km`;
}
function fmtSpeed(kmh) { return kmh ? kmh.toFixed(1) + ' km/h' : '—'; }
function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('de-AT', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' });
}
function fmtTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
}

const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
Chart.defaults.borderColor = isDark ? 'rgba(51,65,85,.6)' : 'rgba(226,232,240,.8)';

function makeChart(id, type, labels, datasets, scales = {}) {
    return new Chart(document.getElementById(id), {
        type,
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { display: false } },
            scales,
        }
    });
}

function statTile(label, value) {
    return `<div class="stat-tile"><div class="stat-label">${label}</div><div class="stat-value" style="font-size:1.2rem">${value}</div></div>`;
}

async function load() {
    const id = location.pathname.split('/').pop();
    const a = await fetch(`/api/activities/${id}`).then(r => r.json());

    // Header
    const emoji = SPORT_EMOJI[a.sport_type] || SPORT_EMOJI.default;
    const sportName = (a.sport_type || 'Aktivität').replace(/_/g, ' ');
    document.getElementById('act-title').textContent = `${emoji} ${sportName.charAt(0).toUpperCase() + sportName.slice(1)}`;
    document.getElementById('act-meta').textContent = `${fmtDate(a.started_at)} · ${fmtTime(a.started_at)}`;
    document.title = `PulseBase — ${sportName}`;

    // Stat Grid
    const isRunning = a.sport_type === 'running' || a.sport_type === 'hiking' || a.sport_type === 'walking';
    const isCycling = a.sport_type === 'cycling';
    const stats = [
        ['Distanz',    fmtDist(a.distance_meters)],
        ['Dauer',      fmtDuration(a.duration_seconds)],
        ['Kalorien',   a.calories ? a.calories + ' kcal' : '—'],
        [isRunning ? 'Ø Pace' : 'Ø Speed', isRunning ? fmtPace(a.avg_pace_sec_per_km) : fmtSpeed(a.avg_speed_kmh)],
        ['Ø HR',       a.avg_hr ? a.avg_hr + ' bpm' : '—'],
        ['Höhenmeter', a.elevation_gain ? '+' + Math.round(a.elevation_gain) + ' m' : '—'],
    ];
    document.getElementById('stat-grid').innerHTML = stats.map(([l, v]) => statTile(l, v)).join('');

    // Training Effect
    if (a.aerobic_effect || a.anaerobic_effect) {
        document.getElementById('effect-card').style.display = '';
        if (a.aerobic_effect) {
            document.getElementById('fill-aerobic').style.width = (a.aerobic_effect / 5 * 100) + '%';
            document.getElementById('val-aerobic').textContent = a.aerobic_effect.toFixed(1);
        }
        if (a.anaerobic_effect) {
            document.getElementById('fill-anaerobic').style.width = (a.anaerobic_effect / 5 * 100) + '%';
            document.getElementById('val-anaerobic').textContent = a.anaerobic_effect.toFixed(1);
        }
    }
    if (a.training_status) {
        const ts = TS_LABELS[(a.training_status || '').toUpperCase()] || { label: a.training_status, cls: 'badge-unbalanced' };
        document.getElementById('training-status-row').style.display = '';
        document.getElementById('training-status-badge').innerHTML = `<span class="badge ${ts.cls}">${ts.label}</span>`;
    }

    const records = a.records || [];
    if (!records.length) return;

    // Time axis: minutes from start
    const t0 = new Date(records[0].time).getTime();
    const xLabels = records.map(r => {
        const min = (new Date(r.time) - t0) / 60000;
        return min.toFixed(0) + "'";
    });

    // GPS Map
    const gpsPoints = records.filter(r => r.lat && r.lng).map(r => [r.lat, r.lng]);
    if (gpsPoints.length > 1) {
        document.getElementById('map-card').style.display = '';
        const map = L.map('map');
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 18,
        }).addTo(map);
        const track = L.polyline(gpsPoints, { color: '#6366f1', weight: 3, opacity: .85 }).addTo(map);
        map.fitBounds(track.getBounds().pad(0.12));
        L.circleMarker(gpsPoints[0], { radius: 7, color: '#22c55e', fillColor: '#22c55e', fillOpacity: 1, weight: 2 }).addTo(map);
        L.circleMarker(gpsPoints[gpsPoints.length - 1], { radius: 7, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 1, weight: 2 }).addTo(map);
    }

    // HR Chart
    if (records.some(r => r.heart_rate)) {
        document.getElementById('hr-card').style.display = '';
        makeChart('hr-chart', 'line', xLabels,
            [{ data: records.map(r => r.heart_rate), borderColor: '#ef4444', backgroundColor: 'transparent', pointRadius: 0, tension: 0.3 }],
            { y: { beginAtZero: false } }
        );
    }

    // Pace or Speed Chart
    if (isRunning && records.some(r => r.pace_sec_per_km)) {
        document.getElementById('pace-card').style.display = '';
        document.getElementById('pace-title').textContent = 'Pace';
        makeChart('pace-chart', 'line', xLabels,
            [{ data: records.map(r => r.pace_sec_per_km ? +(r.pace_sec_per_km / 60).toFixed(2) : null),
               borderColor: '#6366f1', backgroundColor: 'transparent', pointRadius: 0, tension: 0.3 }],
            { y: { reverse: true, title: { display: true, text: 'min/km' } } }
        );
    } else if (isCycling && records.some(r => r.pace_sec_per_km)) {
        document.getElementById('pace-card').style.display = '';
        document.getElementById('pace-title').textContent = 'Geschwindigkeit';
        makeChart('pace-chart', 'line', xLabels,
            [{ data: records.map(r => r.pace_sec_per_km ? +(1000 / r.pace_sec_per_km * 3.6).toFixed(1) : null),
               borderColor: '#6366f1', backgroundColor: 'transparent', pointRadius: 0, tension: 0.3 }],
            { y: { title: { display: true, text: 'km/h' } } }
        );
    }

    // Elevation Chart
    if (records.some(r => r.elevation)) {
        document.getElementById('elev-card').style.display = '';
        makeChart('elev-chart', 'line', xLabels,
            [{ data: records.map(r => r.elevation ? +r.elevation.toFixed(1) : null),
               borderColor: '#f59e0b', backgroundColor: isDark ? 'rgba(245,158,11,.1)' : 'rgba(245,158,11,.08)',
               fill: true, pointRadius: 0, tension: 0.3 }],
            { y: { title: { display: true, text: 'm' } } }
        );
    }

    // Cadence Chart
    if (records.some(r => r.cadence)) {
        document.getElementById('cadence-card').style.display = '';
        makeChart('cadence-chart', 'line', xLabels,
            [{ data: records.map(r => r.cadence),
               borderColor: '#22c55e', backgroundColor: 'transparent', pointRadius: 0, tension: 0.3 }],
            { y: { beginAtZero: false } }
        );
    }
}

load().catch(err => console.error('Activity load error:', err));
