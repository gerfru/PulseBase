import { buildChartDataTable } from './chart-utils.js';

export function scoreLabel(score, thresholds = [75, 45]) {
    if (score == null) return '';
    if (score >= thresholds[0]) return 'Gut';
    if (score >= thresholds[1]) return 'Ok';
    return 'Niedrig';
}

export function sparklineSvg(dataPoints, color = 'currentColor', W = 60, H = 22) {
    const vals = dataPoints.filter((v) => v != null);
    if (vals.length < 3) return '';
    const min = Math.min(...vals);
    const range = Math.max(...vals) - min || 1;
    const pts = dataPoints
        .map((v, i) => {
            if (v == null) return null;
            const x = (i / Math.max(dataPoints.length - 1, 1)) * W;
            const y = H - ((v - min) / range) * (H - 4) - 2;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .filter(Boolean)
        .join(' ');
    return `<svg class="sparkline-inline" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true">
        <polyline points="${pts}" fill="none" stroke="${color}"
            stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
}

export const SPORT_EMOJI = {
    running: '🏃',
    cycling: '🚴',
    swimming: '🏊',
    walking: '🚶',
    hiking: '🥾',
    strength_training: '🏋️',
    yoga: '🧘',
    indoor_cycling: '🚴',
    trail_running: '🏔️',
    open_water_swimming: '🌊',
    cardio: '💪',
    cardio_training: '💪',
    elliptical: '🔄',
    fitness_equipment: '🏋️',
    other: '⚡',
    default: '⚡',
};

export const SPORT_LABEL = {
    running: 'Laufen',
    cycling: 'Radfahren',
    swimming: 'Schwimmen',
    walking: 'Gehen',
    hiking: 'Wandern',
    strength_training: 'Krafttraining',
    yoga: 'Yoga',
    indoor_cycling: 'Indoor Cycling',
    trail_running: 'Trailrunning',
    open_water_swimming: 'Freiwasserschwimmen',
    cardio: 'Cardio',
    cardio_training: 'Cardio',
    elliptical: 'Ellipsentrainer',
    fitness_equipment: 'Fitnessgerät',
    other: 'Sonstige',
};

export function sportLabel(type) {
    const emoji = SPORT_EMOJI[type] || SPORT_EMOJI.default;
    const name = SPORT_LABEL[type] || esc(type || 'Sonstige').replace(/_/g, ' ');
    return `${emoji} ${name}`;
}

export function fmtDuration(s) {
    if (!s) return '—';
    const h = Math.floor(s / 3600),
        m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function fmtDist(m) {
    return m ? `${(m / 1000).toFixed(1)} km` : '—';
}

export function secToH(s) {
    return s ? +(s / 3600).toFixed(1) : null;
}

export const charts = {};

export function makeChart(id, type, labels, datasets, extra = {}) {
    if (charts[id]) charts[id].destroy();
    const canvas = document.getElementById(id);

    const baseScales = extra.scales || {
        y: { beginAtZero: type === 'bar', stacked: extra.stacked || false },
    };
    const scaleDefaults = {
        ...baseScales,
        x: {
            ...(baseScales.x || {}),
            ticks: { maxTicksLimit: 7, autoSkip: true, ...(baseScales.x?.ticks || {}) },
        },
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
        },
    });

    // Accessibility: Textalternative fuer Screenreader (WCAG 1.1.1).
    // ariaSummary uebersteuert; sonst wird aus Typ, Serien-Labels und letztem
    // Wert automatisch eine sinnvolle Beschreibung erzeugt.
    if (canvas) {
        const summary = extra.ariaSummary || chartAriaLabel(type, datasets);
        canvas.setAttribute('role', 'img');
        canvas.setAttribute('aria-label', summary);
        buildChartDataTable(canvas, labels, datasets, summary);
    }
}

function chartAriaLabel(type, datasets) {
    const typeWord = type === 'bar' ? 'Balkendiagramm' : type === 'line' ? 'Liniendiagramm' : 'Diagramm';
    const series = datasets.map((d) => d.label).filter(Boolean);
    let label = series.length ? `${typeWord}: ${series.join(', ')}` : typeWord;
    if (datasets.length === 1) {
        const vals = (datasets[0].data || []).filter((v) => v != null);
        if (vals.length) label += `. Aktueller Wert ${vals[vals.length - 1]}, ${vals.length} Datenpunkte`;
    }
    return label;
}

export function showEmpty(id) {
    const canvas = document.getElementById(`${id}-chart`);
    if (canvas) canvas.style.display = 'none';
    const empty = document.getElementById(`${id}-empty`);
    if (empty) empty.style.display = 'block';
}

export function hideEmpty(id) {
    const canvas = document.getElementById(`${id}-chart`);
    if (canvas) canvas.style.display = '';
    const empty = document.getElementById(`${id}-empty`);
    if (empty) empty.style.display = 'none';
}

export function esc(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

export function openFormulaDialog(title, bodyHtml, href) {
    document.getElementById('formula-dialog-title').textContent = title;
    document.getElementById('formula-dialog-body').innerHTML = DOMPurify.sanitize(bodyHtml);
    document.getElementById('formula-dialog-link').href = href;
    document.getElementById('formula-dialog').showModal();
}

export function scoreColor(score) {
    if (score == null) return 'var(--muted)';
    const n = parseFloat(score);
    if (Number.isNaN(n)) return 'var(--muted)';
    return n >= 75 ? 'var(--green)' : n >= 45 ? 'var(--amber)' : 'var(--red)';
}

export const EV_LEVEL_SHORT = { meta: 'M', replicated: 'R', model: 'E' };
export const EV_LEVEL_CLS = { meta: 'ev-meta', replicated: 'ev-rep', model: 'ev-model' };

export function evBadgeHtml(evEntry, key = '') {
    if (!evEntry) return '';
    const short = EV_LEVEL_SHORT[evEntry.level] ?? '?';
    const cls = EV_LEVEL_CLS[evEntry.level] ?? 'ev-model';
    const label = esc(evEntry.label ?? '');
    const name = esc(evEntry.name ?? '');
    return `<span class="ev-badge ${cls}"${key ? ` data-ev-badge="${esc(key)}"` : ''} title="${label}: ${name}">${short}</span>`;
}
