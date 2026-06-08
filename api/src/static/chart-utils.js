// Aktives Theme (von theme-init.js gesetzt) statt reiner System-Präferenz —
// so stimmen Achsen/Grid-Farben mit der manuellen Theme-Wahl (Toggle) überein.
export const isDark = document.documentElement.classList.contains('dark');

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

// Accessibility: versteckte Datentabelle je Diagramm (WCAG 1.1.1).
// Das aria-label des Canvas fasst nur zusammen — diese sr-only-<table> macht
// jeden Einzel-Messpunkt fuer Screenreader zugaenglich. Canvas verweist via
// aria-describedby auf die Tabelle. Idempotent: ersetzt bei Re-Render.
// createElement statt innerHTML (kein XSS mit dynamischen Werten).
export function buildChartDataTable(canvas, labels, datasets, captionText = '') {
    if (!canvas?.id) return;
    const tableId = `${canvas.id}-table`;
    document.getElementById(tableId)?.remove();

    const table = document.createElement('table');
    table.id = tableId;
    table.className = 'sr-only';

    if (captionText) {
        const caption = document.createElement('caption');
        caption.textContent = captionText;
        table.appendChild(caption);
    }

    const thead = document.createElement('thead');
    const headRow = document.createElement('tr');
    headRow.appendChild(document.createElement('th')); // Eck-Zelle (X-Achse)
    datasets.forEach((d, i) => {
        const th = document.createElement('th');
        th.scope = 'col';
        th.textContent = d.label || `Serie ${i + 1}`;
        headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    labels.forEach((label, rowIdx) => {
        const tr = document.createElement('tr');
        const rowHead = document.createElement('th');
        rowHead.scope = 'row';
        rowHead.textContent = label != null ? String(label) : '';
        tr.appendChild(rowHead);
        datasets.forEach((d) => {
            const td = document.createElement('td');
            const v = (d.data || [])[rowIdx];
            td.textContent = v != null ? String(v) : '—';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    canvas.insertAdjacentElement('afterend', table);
    canvas.setAttribute('aria-describedby', tableId);
}
