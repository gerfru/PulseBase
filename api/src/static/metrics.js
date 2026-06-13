import './chart-utils.js';
import { esc } from './dashboard-utils.js';
import { GARMIN_METRICS } from './metrics-garmin.js';
import { ENERGY_METRICS } from './metrics-energy.js';
import { ML_METRICS } from './metrics-ml.js';
import { SLEEP_METRICS } from './metrics-sleep.js';
import { ACTIVITY_METRICS } from './metrics-activity.js';
import { READINESS_METRICS } from './metrics-readiness.js';

const METRICS = {
    ...GARMIN_METRICS,
    ...ENERGY_METRICS,
    ...ML_METRICS,
    ...SLEEP_METRICS,
    ...ACTIVITY_METRICS,
    ...READINESS_METRICS,
};

// ── Verwandte Metriken (Phase 3) — Vernetzung der Detailseiten ───────────────
// Mapping je (aufgelöster) Metrik-Name → 2-3 thematisch verwandte Metriken.
// Statische, eigene Daten → Render via esc(), kein Inline-Handler, kein DOMPurify nötig.
const RELATED = {
    readiness: [
        { name: 'hrv-status-custom', title: 'HRV Status', icon: '🔬' },
        { name: 'hrv-recovery', title: 'HRV Recovery', icon: '⬆️' },
        { name: 'sleep-score-custom', title: 'Schlafqualität', icon: '✨' },
    ],
    'hrv-status-custom': [
        { name: 'autonomic', title: 'Autonome Energie', icon: '💚' },
        { name: 'hrv-recovery', title: 'HRV Recovery', icon: '⬆️' },
        { name: 'stress-score-custom', title: 'Autonomer Stressindex', icon: '🧘' },
    ],
    'hrv-recovery': [
        { name: 'hrv-status-custom', title: 'HRV Status', icon: '🔬' },
        { name: 'autonomic', title: 'Autonome Energie', icon: '💚' },
    ],
    'body-battery-custom': [
        { name: 'battery-pattern', title: 'Body Battery Muster', icon: '🔮' },
        { name: 'readiness', title: 'Erholung', icon: '🔄' },
        { name: 'hr-zscore', title: 'Ruhepuls Z-Score', icon: '❤️' },
    ],
    'battery-pattern': [
        { name: 'body-battery-custom', title: 'Body Battery', icon: '🔋' },
        { name: 'readiness', title: 'Erholung', icon: '🔄' },
    ],
    'sleep-score-custom': [
        { name: 'sleep-consistency', title: 'Schlaf-Konsistenz', icon: '🌙' },
        { name: 'cognitive', title: 'Kognitive Energie', icon: '🧠' },
        { name: 'hrv-status-custom', title: 'HRV Status', icon: '🔬' },
    ],
    'sleep-consistency': [
        { name: 'sleep-score-custom', title: 'Schlafqualität', icon: '✨' },
        { name: 'cognitive', title: 'Kognitive Energie', icon: '🧠' },
    ],
    'stress-score-custom': [
        { name: 'hrv-status-custom', title: 'HRV Status', icon: '🔬' },
        { name: 'readiness', title: 'Erholung', icon: '🔄' },
    ],
    'hr-zscore': [
        { name: 'battery-pattern', title: 'Body Battery Muster', icon: '🔮' },
        { name: 'readiness', title: 'Erholung', icon: '🔄' },
    ],
    'intensity-minutes': [
        { name: 'training-monotony', title: 'Training Monotony', icon: '🔁' },
        { name: 'training-effect', title: 'Training Effect', icon: '📈' },
        { name: 'physical', title: 'Physische Energie', icon: '⚡' },
    ],
    'training-monotony': [
        { name: 'intensity-minutes', title: 'Intensitätsminuten', icon: '⏱️' },
        { name: 'physical', title: 'Physische Energie', icon: '⚡' },
    ],
    'running-economy': [
        { name: 'intensity-minutes', title: 'Intensitätsminuten', icon: '⏱️' },
        { name: 'physical', title: 'Physische Energie', icon: '⚡' },
    ],
    correlations: [
        { name: 'hrv-status-custom', title: 'HRV Status', icon: '🔬' },
        { name: 'sleep-score-custom', title: 'Schlafqualität', icon: '✨' },
    ],
    vo2max: [
        { name: 'training-effect', title: 'Training Effect', icon: '📈' },
        { name: 'intensity-minutes', title: 'Intensitätsminuten', icon: '⏱️' },
    ],
};

async function load() {
    const _redirects = { physical: 'readiness', autonomic: 'readiness', cognitive: 'readiness' };
    const rawName = location.pathname.split('/').filter(Boolean).at(-1);
    const name = _redirects[rawName] ?? rawName;
    if (_redirects[rawName]) history.replaceState(null, '', '/metrics/readiness');
    const def = METRICS[name];
    if (!def) {
        location.href = '/dashboard';
        return;
    }

    document.getElementById('metric-section').textContent = def.section;
    document.getElementById('metric-title').textContent = def.title;
    document.title = `PulseBase — ${def.title}`;

    try {
        const data = await def.fetch();
        const result = def.render(data);

        document.getElementById('metric-value').innerHTML = DOMPurify.sanitize(result.value);
        if (result.sub) document.getElementById('metric-sub').innerHTML = DOMPurify.sanitize(result.sub);

        // Inline summary (1-2 sentences from eli5)
        const summaryEl = document.getElementById('metric-summary');
        if (summaryEl && result.summary) {
            summaryEl.textContent = result.summary;
            summaryEl.classList.remove('hidden');
        }

        // Recommendation block
        const recEl = document.getElementById('metric-recommendation');
        if (recEl && result.recommendation) {
            recEl.textContent = result.recommendation;
            recEl.classList.remove('hidden');
        }

        // Deep-link to help article
        const helpLink = document.getElementById('metric-help-link');
        if (helpLink) helpLink.href = `/help#${name}`;

        if (result.customHtml) {
            document.getElementById('custom-html-block').innerHTML = DOMPurify.sanitize(result.customHtml);
        }

        if (result.kpis?.length) {
            document.getElementById('metrics-kpis').innerHTML = result.kpis
                .map((k) => {
                    const d = k.delta;
                    const deltaHtml =
                        d != null && d !== 0
                            ? `<div class="kpi-delta ${d > 0 ? 'kpi-delta-up' : 'kpi-delta-down'}">${d > 0 ? '↑ +' : '↓ '}${esc(String(d))}</div>`
                            : '';
                    return `<div class="metrics-kpi-tile card">
                    <div class="metrics-kpi-label">${esc(k.label)}</div>
                    <div class="metrics-kpi-value">${esc(k.value)}</div>
                    ${deltaHtml}
                </div>`;
                })
                .join('');
        }

        // Verwandte-Metriken-Block (Phase 3) — nur wenn Mapping existiert
        const related = RELATED[name];
        const relNav = document.getElementById('related-metrics');
        if (relNav && related?.length) {
            document.getElementById('related-grid').innerHTML = related
                .map(
                    (r) => `<a href="/metrics/${esc(r.name)}" class="related-tile card">
                    <span class="related-tile-icon">${esc(r.icon)}</span>
                    <span class="related-tile-title">${esc(r.title)}</span>
                </a>`,
                )
                .join('');
            relNav.hidden = false;
        }

        if (result.charts?.length) {
            result.charts.forEach((chart, idx) => {
                const chartId = `metrics-chart-${idx}`;
                const titleId = `chart-title-${idx}`;
                const cardId = `chart-card-${idx}`;

                let chartCard = document.getElementById(cardId);
                if (!chartCard) {
                    chartCard = document.createElement('div');
                    chartCard.className = 'chart-card card';
                    chartCard.id = cardId;
                    chartCard.innerHTML = `
                        <h3 id="${titleId}" class="chart-title"></h3>
                        <div style="position: relative; height: 300px;">
                            <canvas id="${chartId}"></canvas>
                        </div>
                    `;
                    document
                        .getElementById('chart-card')
                        ?.parentNode?.insertBefore(chartCard, document.getElementById('chart-card')?.nextSibling);
                }
                chartCard.classList.remove('hidden');
                document.getElementById(titleId).textContent = chart.title;
                const baseScalesM =
                    chart.scales ||
                    (chart.type === 'bar' ? { y: { beginAtZero: true } } : { y: { beginAtZero: false } });
                const canvasM = document.getElementById(chartId);
                canvasM.setAttribute('role', 'img');
                canvasM.setAttribute('aria-label', `Diagramm: ${chart.title}`);
                new Chart(canvasM, {
                    type: chart.type,
                    data: { labels: chart.labels, datasets: chart.datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        plugins: { legend: { display: (chart.datasets?.length ?? 0) > 1 } },
                        scales: {
                            ...baseScalesM,
                            x: {
                                ...(baseScalesM.x || {}),
                                ticks: { maxTicksLimit: 7, autoSkip: true, ...(baseScalesM.x?.ticks || {}) },
                            },
                        },
                    },
                });
            });
        } else if (result.chart) {
            document.getElementById('chart-card').classList.remove('hidden');
            document.getElementById('chart-title').textContent = result.chart.title;
            const baseScalesS =
                result.chart.scales ||
                (result.chart.type === 'bar' ? { y: { beginAtZero: true } } : { y: { beginAtZero: false } });
            const canvasS = document.getElementById('metrics-chart');
            canvasS.setAttribute('role', 'img');
            canvasS.setAttribute('aria-label', `Diagramm: ${result.chart.title}`);
            new Chart(canvasS, {
                type: result.chart.type,
                data: { labels: result.chart.labels, datasets: result.chart.datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    plugins: { legend: { display: (result.chart.datasets?.length ?? 0) > 1 } },
                    scales: {
                        ...baseScalesS,
                        x: {
                            ...(baseScalesS.x || {}),
                            ticks: { maxTicksLimit: 7, autoSkip: true, ...(baseScalesS.x?.ticks || {}) },
                        },
                    },
                },
            });
        }

        // eli5, formula, sources are now in the /help section — see /help#<metric-name>
    } catch (err) {
        document.getElementById('metric-value').textContent = 'Fehler beim Laden';
        console.error('metrics load error:', err);
    }
}

const _backTab = new URLSearchParams(location.search).get('back');
if (_backTab) {
    const el = document.querySelector('a[href="/dashboard"]');
    if (el) el.href = `/dashboard#${_backTab}`;
}

load();
