/* metrics-overview.js — Metriken-Übersicht (extrahiert aus metrics_overview.html für CSP) */
/* C (Farb-Palette) wird als Global aus colors.js bereitgestellt (base.html) */

/* global C */

const METRIC_GROUPS = [
    {
        label: 'Erholung',
        items: [
            {
                name: 'readiness',
                title: 'Erholung',
                icon: '🔄',
                fetch: '/api/readiness',
                evKey: 'energy_autonomic',
                val: (d) => d.score,
                unit: '',
                color: 'var(--green)',
            },
            {
                name: 'autonomic',
                title: 'Autonome Energie',
                icon: '💚',
                fetch: '/api/energy',
                evKey: 'energy_autonomic',
                val: (d) => (d.energy_autonomic?.score != null ? Math.round(d.energy_autonomic.score) : null),
                unit: '',
                color: 'var(--green)',
            },
            {
                name: 'cognitive',
                title: 'Kognitive Energie',
                icon: '🧠',
                fetch: '/api/energy',
                evKey: 'energy_cognitive',
                val: (d) => (d.energy_cognitive?.score != null ? Math.round(d.energy_cognitive.score) : null),
                unit: '',
                color: 'var(--violet)',
            },
        ],
    },
    {
        label: 'Training',
        items: [
            {
                name: 'physical',
                title: 'Physische Energie',
                icon: '⚡',
                fetch: '/api/energy',
                evKey: 'energy_physical',
                val: (d) => (d.energy_physical?.score != null ? Math.round(d.energy_physical.score) : null),
                unit: '',
                color: 'var(--indigo)',
            },
            {
                name: 'training-status',
                title: 'Trainingszustand',
                icon: '🏋️',
                fetch: '/api/training-status',
                evKey: null,
                val: (d) => d.training_status ?? null,
                unit: '',
                color: 'var(--muted)',
            },
            {
                name: 'readiness-rf',
                title: 'ML Readiness',
                icon: '🤖',
                fetch: '/api/ml-insights',
                evKey: 'readiness_rf',
                val: (d) => (d.readiness_rf?.value != null ? Math.round(d.readiness_rf.value) : null),
                unit: '',
                color: 'var(--indigo)',
            },
        ],
    },
    {
        label: 'Garmin-Daten',
        items: [
            {
                name: 'hrv',
                title: 'HRV Wochenø',
                icon: '💓',
                fetch: '/api/hrv',
                evKey: 'energy_autonomic',
                val: (d) => d.hrv_weekly_avg,
                unit: ' ms',
                color: 'var(--green)',
            },
            {
                name: 'sleep',
                title: 'Schlaf-Score',
                icon: '😴',
                fetch: '/api/sleep?days=2',
                evKey: 'sleep_score_custom',
                val: (d) => d[0]?.sleep_score,
                unit: '',
                color: 'var(--violet)',
            },
            {
                name: 'body-battery',
                title: 'Body Battery',
                icon: '🔋',
                fetch: '/api/daily?days=2',
                evKey: 'body_battery_custom',
                val: (d) => d.at(-1)?.body_battery_high,
                unit: '',
                color: 'var(--green)',
            },
            {
                name: 'steps',
                title: 'Schritte',
                icon: '👟',
                fetch: '/api/daily?days=2',
                evKey: 'anomaly_steps',
                val: (d) => d.at(-1)?.steps?.toLocaleString('de-AT'),
                unit: '',
                color: 'var(--blue)',
            },
            {
                name: 'hr-zscore',
                title: 'Ruhepuls Z-Score',
                icon: '❤️',
                fetch: '/api/ml-insights',
                evKey: 'anomaly_hr',
                val: (d) => d.anomaly_hr?.z_score?.toFixed(2),
                unit: '',
                color: 'var(--red)',
            },
        ],
    },
    {
        label: 'Schlaf',
        items: [
            {
                name: 'sleep-consistency',
                title: 'Schlaf-Konsistenz',
                icon: '🌙',
                fetch: '/api/ml-insights',
                evKey: 'sleep_consistency',
                val: (d) => d.sleep_consistency?.score?.toFixed(0),
                unit: '',
                color: 'var(--violet)',
            },
            {
                name: 'sleep-score-custom',
                title: 'Schlafqualität',
                icon: '✨',
                fetch: '/api/ml-insights',
                evKey: 'sleep_score_custom',
                val: (d) => (d.sleep_score_custom?.score != null ? Math.round(d.sleep_score_custom.score) : null),
                unit: '',
                color: 'var(--violet)',
            },
        ],
    },
    {
        label: 'Aktivität',
        items: [
            {
                name: 'intensity-minutes',
                title: 'Intensitätsminuten',
                icon: '⏱️',
                fetch: '/api/ml-insights',
                evKey: 'intensity_minutes_custom',
                val: (d) => {
                    const im = d.intensity_minutes_custom;
                    return im ? im.moderate_minutes + im.vigorous_minutes * 2 : null;
                },
                unit: ' min',
                color: 'var(--amber)',
            },
            {
                name: 'training-effect',
                title: 'Training Effect',
                icon: '📈',
                fetch: '/api/ml-insights',
                evKey: 'training_effect_custom',
                val: (d) => d.training_effect_custom?.effect?.toFixed(1),
                unit: '',
                color: 'var(--indigo)',
            },
            {
                name: 'training-monotony',
                title: 'Training Monotony',
                icon: '🔁',
                fetch: '/api/ml-insights',
                evKey: 'training_monotony',
                val: (d) => d.training_monotony?.monotony?.toFixed(2),
                unit: '',
                color: 'var(--amber)',
            },
            {
                name: 'running-economy',
                title: 'Running Economy',
                icon: '🏃',
                fetch: '/api/ml-insights',
                evKey: 'running_economy',
                val: (d) => d.running_economy?.score?.toFixed(0),
                unit: '',
                color: 'var(--blue)',
            },
        ],
    },
    {
        label: 'HRV & Autonomes System',
        items: [
            {
                name: 'hrv-status',
                title: 'HRV Status (Garmin)',
                icon: '💚',
                fetch: '/api/hrv',
                evKey: null,
                val: (d) => d.hrv_status,
                unit: '',
                color: 'var(--green)',
            },
            {
                name: 'hrv-status-custom',
                title: 'HRV Status (Custom)',
                icon: '🔬',
                fetch: '/api/ml-insights',
                evKey: 'energy_autonomic',
                val: (d) => d.hrv_status_custom?.status,
                unit: '',
                color: 'var(--green)',
            },
            {
                name: 'hrv-recovery',
                title: 'HRV Recovery Speed',
                icon: '⬆️',
                fetch: '/api/ml-insights',
                evKey: 'hrv_recovery',
                val: (d) => d.hrv_recovery?.recovery_speed?.toFixed(1),
                unit: ' HRV/d',
                color: 'var(--green)',
            },
            {
                name: 'spo2-trend',
                title: 'SpO₂ Trend',
                icon: '🩸',
                fetch: '/api/ml-insights',
                evKey: 'spo2_trend',
                val: (d) => d.spo2_trend?.mean_spo2?.toFixed(1),
                unit: ' %',
                color: 'var(--blue)',
            },
            {
                name: 'stress-score-custom',
                title: 'Stress Score',
                icon: '🧘',
                fetch: '/api/ml-insights',
                evKey: 'stress_score_custom',
                val: (d) => d.stress_score_custom?.score?.toFixed(0),
                unit: '',
                color: 'var(--red)',
            },
        ],
    },
    {
        label: 'ML & Muster',
        items: [
            {
                name: 'battery-pattern',
                title: 'Body Battery Muster',
                icon: '🔮',
                fetch: '/api/ml-insights',
                evKey: 'battery_pattern',
                val: (d) => d.battery_pattern?.pattern ?? null,
                unit: '',
                color: 'var(--indigo)',
            },
            {
                name: 'correlations',
                title: 'Korrelationen',
                icon: '🔗',
                fetch: '/api/ml-insights',
                evKey: 'correlation_sleep_hrv',
                val: (d) => (d.correlation_sleep_hrv?.r != null ? `r=${d.correlation_sleep_hrv.r.toFixed(2)}` : null),
                unit: '',
                color: 'var(--blue)',
            },
        ],
    },
];

// Mirrors scoreColor() in dashboard-utils.js (classic-script context, cannot import)
function scoreColor(val) {
    if (val == null) return 'var(--muted)';
    const n = parseFloat(val);
    if (Number.isNaN(n)) return 'var(--muted)';
    return n >= 75 ? 'var(--green)' : n >= 45 ? 'var(--amber)' : 'var(--red)';
}

// Mirrors EV_LEVEL_SHORT/EV_LEVEL_CLS in dashboard-utils.js (classic-script context)
const EV_LEVEL_SHORT = { meta: 'M', replicated: 'R', model: 'E' };
const EV_LEVEL_CLS = { meta: 'ev-meta', replicated: 'ev-rep', model: 'ev-model' };

function evBadgeHtml(evEntry) {
    if (!evEntry) return '';
    const short = EV_LEVEL_SHORT[evEntry.level] ?? '?';
    const cls = EV_LEVEL_CLS[evEntry.level] ?? 'ev-model';
    const label = evEntry.label ?? evEntry.level;
    return `<span class="ev-badge ${cls}" title="${label}: ${evEntry.name ?? ''}">${short}</span>`;
}

async function buildGrid() {
    const fetchMap = {};
    for (const g of METRIC_GROUPS) {
        for (const item of g.items) {
            if (!fetchMap[item.fetch]) fetchMap[item.fetch] = fetch(item.fetch).then((r) => r.json());
        }
    }
    if (!fetchMap['/api/evidence']) fetchMap['/api/evidence'] = fetch('/api/evidence').then((r) => r.json());

    const cache = {};
    await Promise.all(
        Object.entries(fetchMap).map(async ([url, p]) => {
            try {
                cache[url] = await p;
            } catch {
                cache[url] = null;
            }
        }),
    );

    const evidence = cache['/api/evidence'] ?? {};

    const grid = document.getElementById('metrics-grid');
    grid.innerHTML = METRIC_GROUPS.map((group) => {
        const tiles = group.items
            .map((item) => {
                const data = cache[item.fetch];
                let valStr = '—';
                try {
                    const v = data != null ? item.val(data) : null;
                    valStr = v != null ? String(v) + item.unit : '—';
                } catch {}
                const color = valStr !== '—' ? scoreColor(valStr) : 'var(--muted)';
                const evEntry = item.evKey ? evidence[item.evKey] : null;
                const badge = evBadgeHtml(evEntry);
                const horizon = evEntry?.time_horizon
                    ? `<span class="metric-horizon">${evEntry.time_horizon}</span>`
                    : '';
                return `<a href="/metrics/${item.name}" class="metric-overview-tile card">
                <div style="display:flex;align-items:center;justify-content:space-between">
                    <span class="metric-overview-icon">${item.icon}</span>
                    ${badge}
                </div>
                <span class="metric-overview-title">${item.title}</span>
                <span class="metric-overview-val" style="color:${color}">${valStr}</span>
                ${horizon}
            </a>`;
            })
            .join('');
        return `<section>
            <h2 class="metrics-section-heading">${group.label}</h2>
            <div class="metrics-overview-grid">${tiles}</div>
        </section>`;
    }).join('');
}

buildGrid().catch((e) => {
    document.getElementById('metrics-grid').innerHTML = '<p class="empty">Fehler beim Laden</p>';
    console.error(e);
});
