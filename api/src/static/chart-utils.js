export const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
Chart.defaults.borderColor = isDark ? 'rgba(51,65,85,.6)' : 'rgba(226,232,240,.8)';
Chart.defaults.interaction = { mode: 'index', intersect: false };
Chart.defaults.elements.point.hoverRadius = 4;

export function makeGradient(hexColor, alphaTop = 0.32, alphaBot = 0.02) {
    return (ctx) => {
        const chart = ctx.chart;
        const { ctx: c, chartArea } = chart;
        if (!chartArea) return `${hexColor}55`;
        const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
        const r = parseInt(hexColor.slice(1, 3), 16);
        const m = parseInt(hexColor.slice(3, 5), 16);
        const b = parseInt(hexColor.slice(5, 7), 16);
        g.addColorStop(0, `rgba(${r},${m},${b},${alphaTop})`);
        g.addColorStop(1, `rgba(${r},${m},${b},${alphaBot})`);
        return g;
    };
}

export function fmtDate(iso) {
    if (!iso) return '—';
    const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit' });
}

export function fmtHours(seconds) {
    if (!seconds) return '—';
    const h = Math.floor(seconds / 3600),
        m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
