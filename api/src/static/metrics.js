import './chart-utils.js';
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

        document.getElementById('metric-value').innerHTML = result.value;
        if (result.sub) document.getElementById('metric-sub').textContent = result.sub;

        if (result.customHtml) {
            document.getElementById('custom-html-block').innerHTML = result.customHtml;
        }

        if (result.kpis?.length) {
            document.getElementById('metrics-kpis').innerHTML = result.kpis
                .map((k) => {
                    const d = k.delta;
                    const deltaHtml =
                        d != null && d !== 0
                            ? `<div class="kpi-delta ${d > 0 ? 'kpi-delta-up' : 'kpi-delta-down'}">${d > 0 ? '↑ +' : '↓ '}${d}</div>`
                            : '';
                    return `<div class="metrics-kpi-tile card">
                    <div class="metrics-kpi-label">${k.label}</div>
                    <div class="metrics-kpi-value">${k.value}</div>
                    ${deltaHtml}
                </div>`;
                })
                .join('');
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
                chartCard.style.display = '';
                document.getElementById(titleId).textContent = chart.title;
                const baseScalesM =
                    chart.scales ||
                    (chart.type === 'bar' ? { y: { beginAtZero: true } } : { y: { beginAtZero: false } });
                new Chart(document.getElementById(chartId), {
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
            document.getElementById('chart-card').style.display = '';
            document.getElementById('chart-title').textContent = result.chart.title;
            const baseScalesS =
                result.chart.scales ||
                (result.chart.type === 'bar' ? { y: { beginAtZero: true } } : { y: { beginAtZero: false } });
            new Chart(document.getElementById('metrics-chart'), {
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

        if (result.eli5) {
            document.getElementById('eli5-card').style.display = '';
            document.getElementById('eli5-text').textContent = result.eli5;
        }

        if (result.formula?.length || result.science) {
            document.getElementById('formula-card').style.display = '';
            if (result.science) {
                const sciEl = document.getElementById('science-text');
                sciEl.textContent = result.science;
                sciEl.style.display = '';
            }
            if (result.formula?.length) {
                document.getElementById('formula-content').innerHTML = `<div class="formula-table">${result.formula
                    .map(([k, v]) => `<div class="formula-row"><strong>${k}</strong><span>${v}</span></div>`)
                    .join('')}</div>`;
            }
        }

        if (result.sources?.length) {
            document.getElementById('sources-card').style.display = '';
            document.getElementById('sources-list').innerHTML = result.sources
                .map((s) => `<li><a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.label}</a></li>`)
                .join('');
        }
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
