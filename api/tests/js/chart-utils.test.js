import { describe, it, expect, beforeEach, vi } from 'vitest';
import { buildChartDataTable, fmtDate, fmtHours, makeGradient } from '../../src/static/chart-utils.js';

describe('fmtDate', () => {
    it('returns — for falsy values', () => {
        expect(fmtDate(null)).toBe('—');
        expect(fmtDate(undefined)).toBe('—');
        expect(fmtDate('')).toBe('—');
    });

    it('formats a mid-month date', () => {
        // Uses local date constructor (no timezone offset) so output is deterministic
        const result = fmtDate('2024-06-15');
        expect(result).toMatch(/15/);
        expect(result).toMatch(/06/);
    });

    it('formats year boundaries', () => {
        expect(fmtDate('2024-01-01')).toMatch(/01/);
        expect(fmtDate('2024-12-31')).toMatch(/12/);
    });

    it('handles numeric date-like strings', () => {
        const result = fmtDate('2024-03-05');
        expect(result).toMatch(/03|3/); // month 03
        expect(result).toMatch(/05|5/); // day 05
    });
});

describe('makeGradient', () => {
    const mockCtx = (hasChartArea = true) => ({
        chart: {
            ctx: {
                createLinearGradient: () => ({
                    addColorStop: () => {},
                }),
            },
            chartArea: hasChartArea ? { top: 0, bottom: 100 } : undefined,
        },
    });

    it('returns a function', () => {
        expect(typeof makeGradient('#ff0000')).toBe('function');
    });

    it('returns fallback color string when chartArea is missing', () => {
        const fn = makeGradient('#ff0000');
        const result = fn(mockCtx(false));
        expect(result).toBe('#ff000055');
    });

    it('returns a gradient object when chartArea is present', () => {
        const fn = makeGradient('#3b82f6');
        const result = fn(mockCtx(true));
        expect(result).toBeTruthy();
        expect(typeof result).toBe('object');
    });
});

describe('buildChartDataTable', () => {
    let canvas;
    beforeEach(() => {
        document.body.innerHTML = '<canvas id="c1"></canvas>';
        canvas = document.getElementById('c1');
    });

    it('creates an sr-only table after the canvas with one row per label', () => {
        buildChartDataTable(canvas, ['Mo', 'Di', 'Mi'], [{ label: 'Puls', data: [60, 62, 58] }], 'Ruhepuls');
        const table = document.getElementById('c1-table');
        expect(table).toBeTruthy();
        expect(table.tagName).toBe('TABLE');
        expect(table.classList.contains('sr-only')).toBe(true);
        // table sits directly after the canvas
        expect(canvas.nextElementSibling).toBe(table);
        // one tbody row per label
        expect(table.querySelectorAll('tbody tr')).toHaveLength(3);
    });

    it('links the canvas to the table via aria-describedby', () => {
        buildChartDataTable(canvas, ['Mo'], [{ label: 'Puls', data: [60] }], 'Ruhepuls');
        expect(canvas.getAttribute('aria-describedby')).toBe('c1-table');
    });

    it('renders a caption, column headers per dataset and row headers per label', () => {
        buildChartDataTable(
            canvas,
            ['Mo', 'Di'],
            [
                { label: 'Puls', data: [60, 62] },
                { label: 'HRV', data: [40, 45] },
            ],
            'Verlauf',
        );
        const table = document.getElementById('c1-table');
        expect(table.querySelector('caption').textContent).toBe('Verlauf');
        const colHeaders = [...table.querySelectorAll('thead th[scope="col"]')].map((th) => th.textContent);
        expect(colHeaders).toEqual(['Puls', 'HRV']);
        const rowHeaders = [...table.querySelectorAll('tbody th[scope="row"]')].map((th) => th.textContent);
        expect(rowHeaders).toEqual(['Mo', 'Di']);
    });

    it('renders missing values as an em dash', () => {
        buildChartDataTable(canvas, ['Mo', 'Di'], [{ label: 'Puls', data: [60, null] }], '');
        const cells = [...document.querySelectorAll('#c1-table tbody td')].map((td) => td.textContent);
        expect(cells).toEqual(['60', '—']);
    });

    it('falls back to a series name when the dataset has no label', () => {
        buildChartDataTable(canvas, ['Mo'], [{ data: [60] }], '');
        expect(document.querySelector('#c1-table thead th[scope="col"]').textContent).toBe('Serie 1');
    });

    it('is idempotent — re-render replaces the table instead of duplicating', () => {
        buildChartDataTable(canvas, ['Mo', 'Di'], [{ label: 'Puls', data: [60, 62] }], '');
        buildChartDataTable(canvas, ['Mo'], [{ label: 'Puls', data: [61] }], '');
        expect(document.querySelectorAll('#c1-table').length).toBe(1);
        expect(document.querySelectorAll('table').length).toBe(1);
        expect(document.querySelectorAll('#c1-table tbody tr')).toHaveLength(1);
    });

    it('omits the caption element when no caption text is given', () => {
        buildChartDataTable(canvas, ['Mo'], [{ label: 'Puls', data: [60] }], '');
        expect(document.querySelector('#c1-table caption')).toBeNull();
    });

    it('is a no-op when the canvas is missing or has no id', () => {
        expect(() => buildChartDataTable(null, ['Mo'], [{ data: [1] }], '')).not.toThrow();
        const orphan = document.createElement('canvas');
        buildChartDataTable(orphan, ['Mo'], [{ data: [1] }], '');
        expect(orphan.getAttribute('aria-describedby')).toBeNull();
    });
});

describe('fmtHours', () => {
    it('returns — for falsy values', () => {
        expect(fmtHours(0)).toBe('—');
        expect(fmtHours(null)).toBe('—');
        expect(fmtHours(undefined)).toBe('—');
    });

    it('formats minutes only when less than 1 hour', () => {
        expect(fmtHours(60)).toBe('1m');
        expect(fmtHours(90)).toBe('1m');
        expect(fmtHours(3540)).toBe('59m');
    });

    it('formats hours and minutes', () => {
        expect(fmtHours(3600)).toBe('1h 0m');
        expect(fmtHours(3661)).toBe('1h 1m');
        expect(fmtHours(7200)).toBe('2h 0m');
        expect(fmtHours(7384)).toBe('2h 3m');
    });
});

describe('buildChartDataTable — Edge-Cases (Coverage)', () => {
    let canvas;
    beforeEach(() => {
        document.body.innerHTML = '<canvas id="c1"></canvas>';
        canvas = document.getElementById('c1');
    });

    it('renders an empty row header when a label is null', () => {
        buildChartDataTable(canvas, [null, 'Di'], [{ label: 'P', data: [1, 2] }], '');
        const rowHeads = [...document.querySelectorAll('#c1-table tbody th')].map((t) => t.textContent);
        expect(rowHeads).toEqual(['', 'Di']);
    });

    it('treats a dataset without a data array as em dashes', () => {
        buildChartDataTable(canvas, ['Mo'], [{ label: 'P' }], '');
        expect(document.querySelector('#c1-table tbody td').textContent).toBe('—');
    });
});

describe('chart-utils module init (theme defaults)', () => {
    it('reports isDark=true when the dark theme class is set', async () => {
        vi.resetModules();
        document.documentElement.classList.add('dark');
        const mod = await import('../../src/static/chart-utils.js');
        expect(mod.isDark).toBe(true);
        document.documentElement.classList.remove('dark');
        vi.resetModules();
    });

    it('reports isDark=false when the dark theme class is absent', async () => {
        vi.resetModules();
        document.documentElement.classList.remove('dark');
        const mod = await import('../../src/static/chart-utils.js');
        expect(mod.isDark).toBe(false);
        vi.resetModules();
    });
});
