import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
    scoreLabel,
    scoreColor,
    fmtDuration,
    fmtDist,
    secToH,
    esc,
    sparklineSvg,
    sportLabel,
    makeChart,
    showEmpty,
    hideEmpty,
    openFormulaDialog,
} from '../../src/static/dashboard-utils.js';

describe('scoreLabel', () => {
    it('returns empty string for null/undefined', () => {
        expect(scoreLabel(null)).toBe('');
        expect(scoreLabel(undefined)).toBe('');
    });

    it('returns Gut at and above upper threshold', () => {
        expect(scoreLabel(75)).toBe('Gut');
        expect(scoreLabel(100)).toBe('Gut');
    });

    it('returns Ok between thresholds', () => {
        expect(scoreLabel(74)).toBe('Ok');
        expect(scoreLabel(45)).toBe('Ok');
    });

    it('returns Niedrig below lower threshold', () => {
        expect(scoreLabel(44)).toBe('Niedrig');
        expect(scoreLabel(0)).toBe('Niedrig');
    });

    it('respects custom thresholds', () => {
        expect(scoreLabel(85, [90, 60])).toBe('Ok');
        expect(scoreLabel(91, [90, 60])).toBe('Gut');
        expect(scoreLabel(50, [90, 60])).toBe('Niedrig');
    });
});

describe('scoreColor', () => {
    it('returns muted for null', () => {
        expect(scoreColor(null)).toBe('var(--muted)');
        expect(scoreColor(undefined)).toBe('var(--muted)');
    });

    it('returns green at and above 75', () => {
        expect(scoreColor(75)).toBe('var(--green)');
        expect(scoreColor(100)).toBe('var(--green)');
    });

    it('returns amber between 50 and 74', () => {
        expect(scoreColor(50)).toBe('var(--amber)');
        expect(scoreColor(74)).toBe('var(--amber)');
    });

    it('returns red below 50', () => {
        expect(scoreColor(49)).toBe('var(--red)');
        expect(scoreColor(0)).toBe('var(--red)');
    });
});

describe('fmtDuration', () => {
    it('returns — for falsy values', () => {
        expect(fmtDuration(0)).toBe('—');
        expect(fmtDuration(null)).toBe('—');
    });

    it('formats minutes only for less than 1 hour', () => {
        expect(fmtDuration(60)).toBe('1m');
        expect(fmtDuration(90)).toBe('1m');
        expect(fmtDuration(3540)).toBe('59m');
    });

    it('formats hours and minutes', () => {
        expect(fmtDuration(3600)).toBe('1h 0m');
        expect(fmtDuration(3661)).toBe('1h 1m');
        expect(fmtDuration(7200)).toBe('2h 0m');
    });
});

describe('fmtDist', () => {
    it('returns — for falsy values', () => {
        expect(fmtDist(0)).toBe('—');
        expect(fmtDist(null)).toBe('—');
    });

    it('converts meters to km with 1 decimal', () => {
        expect(fmtDist(1000)).toBe('1.0 km');
        expect(fmtDist(5500)).toBe('5.5 km');
        expect(fmtDist(10000)).toBe('10.0 km');
    });
});

describe('secToH', () => {
    it('returns null for falsy values', () => {
        expect(secToH(0)).toBeNull();
        expect(secToH(null)).toBeNull();
    });

    it('converts seconds to hours with 1 decimal', () => {
        expect(secToH(3600)).toBe(1);
        expect(secToH(5400)).toBe(1.5);
        expect(secToH(7200)).toBe(2);
        expect(secToH(1800)).toBe(0.5);
    });
});

describe('esc', () => {
    it('returns empty string for null/undefined', () => {
        expect(esc(null)).toBe('');
        expect(esc(undefined)).toBe('');
    });

    it('passes through safe strings unchanged', () => {
        expect(esc('hello world')).toBe('hello world');
        expect(esc('123')).toBe('123');
    });

    it('escapes HTML characters', () => {
        expect(esc('<script>')).toBe('&lt;script&gt;');
        expect(esc('"quoted"')).toBe('&quot;quoted&quot;');
        expect(esc('a & b')).toBe('a &amp; b');
    });

    it('escapes XSS payload', () => {
        const xss = '<img src=x onerror="alert(1)">';
        const result = esc(xss);
        expect(result).not.toContain('<');
        expect(result).not.toContain('>');
        expect(result).not.toContain('"');
    });
});

describe('sparklineSvg', () => {
    it('returns empty string for fewer than 3 non-null values', () => {
        expect(sparklineSvg([])).toBe('');
        expect(sparklineSvg([1, 2])).toBe('');
        expect(sparklineSvg([null, null, 1, null])).toBe('');
    });

    it('returns SVG string for 3+ values', () => {
        const result = sparklineSvg([1, 2, 3]);
        expect(result).toContain('<svg');
        expect(result).toContain('<polyline');
        expect(result).toContain('</svg>');
    });

    it('handles null gaps within a valid series', () => {
        const result = sparklineSvg([1, null, 2, null, 3]);
        expect(result).toContain('<svg');
    });

    it('uses provided color', () => {
        const result = sparklineSvg([1, 2, 3], '#ff0000');
        expect(result).toContain('#ff0000');
    });
});

describe('sportLabel', () => {
    it('returns emoji and german label for known sport', () => {
        expect(sportLabel('running')).toBe('🏃 Laufen');
        expect(sportLabel('cycling')).toBe('🚴 Radfahren');
    });

    it('returns default emoji and formatted type for unknown sport', () => {
        const result = sportLabel('unknown_sport');
        expect(result).toContain('⚡');
        expect(result).toContain('unknown sport');
    });

    it('returns default label for null/undefined', () => {
        expect(sportLabel(null)).toContain('Sonstige');
        expect(sportLabel(undefined)).toContain('Sonstige');
    });
});

describe('makeChart', () => {
    beforeEach(() => {
        document.body.innerHTML = '<canvas id="test-chart"></canvas>';
        vi.clearAllMocks();
    });

    it('creates a new Chart instance on the canvas', () => {
        makeChart('test-chart', 'line', ['A', 'B'], [{ data: [1, 2] }]);
        expect(global.Chart).toHaveBeenCalledOnce();
        const [canvas, config] = global.Chart.mock.calls[0];
        expect(canvas).toBe(document.getElementById('test-chart'));
        expect(config.type).toBe('line');
        expect(config.data.labels).toEqual(['A', 'B']);
    });

    it('destroys an existing chart before creating a new one', () => {
        makeChart('test-chart', 'bar', [], [{ data: [] }]);
        const firstInstance = global.Chart.mock.results[0].value;
        makeChart('test-chart', 'line', [], [{ data: [] }]);
        expect(firstInstance.destroy).toHaveBeenCalledOnce();
        expect(global.Chart).toHaveBeenCalledTimes(2);
    });

    it('sets beginAtZero true for bar charts', () => {
        makeChart('test-chart', 'bar', [], [{ data: [] }]);
        const config = global.Chart.mock.calls[0][1];
        expect(config.options.scales.y.beginAtZero).toBe(true);
    });

    it('passes custom scales from extra', () => {
        const customScales = { y: { min: 0, max: 100 } };
        makeChart('test-chart', 'line', [], [{ data: [] }], { scales: customScales });
        const config = global.Chart.mock.calls[0][1];
        expect(config.options.scales.y.min).toBe(0);
    });

    it('hides legend when only one dataset', () => {
        makeChart('test-chart', 'line', [], [{ data: [] }]);
        const config = global.Chart.mock.calls[0][1];
        expect(config.options.plugins.legend.display).toBe(false);
    });

    it('shows legend when multiple datasets', () => {
        makeChart('test-chart', 'line', [], [{ data: [] }, { data: [] }]);
        const config = global.Chart.mock.calls[0][1];
        expect(config.options.plugins.legend.display).toBe(true);
    });
});

describe('showEmpty / hideEmpty', () => {
    beforeEach(() => {
        document.body.innerHTML =
            '<canvas id="act-chart"></canvas>' +
            '<div id="act-empty" style="display:none"></div>';
    });

    it('showEmpty hides canvas and shows empty placeholder', () => {
        showEmpty('act');
        expect(document.getElementById('act-chart').style.display).toBe('none');
        expect(document.getElementById('act-empty').style.display).toBe('block');
    });

    it('hideEmpty shows canvas and hides empty placeholder', () => {
        showEmpty('act');
        hideEmpty('act');
        expect(document.getElementById('act-chart').style.display).toBe('');
        expect(document.getElementById('act-empty').style.display).toBe('none');
    });

    it('showEmpty does not throw when elements are absent', () => {
        expect(() => showEmpty('missing')).not.toThrow();
    });

    it('hideEmpty does not throw when elements are absent', () => {
        expect(() => hideEmpty('missing')).not.toThrow();
    });
});

describe('openFormulaDialog', () => {
    beforeEach(() => {
        const dialog = document.createElement('dialog');
        dialog.id = 'formula-dialog';
        dialog.showModal = vi.fn();
        document.body.innerHTML = '';
        document.body.appendChild(dialog);
        dialog.insertAdjacentHTML(
            'beforeend',
            '<span id="formula-dialog-title"></span>' +
            '<div id="formula-dialog-body"></div>' +
            '<a id="formula-dialog-link"></a>',
        );
    });

    it('sets title, body html and link href, then calls showModal', () => {
        openFormulaDialog('HRV', '<p>Formel</p>', '/help#hrv');
        expect(document.getElementById('formula-dialog-title').textContent).toBe('HRV');
        expect(document.getElementById('formula-dialog-body').innerHTML).toBe('<p>Formel</p>');
        expect(document.getElementById('formula-dialog-link').href).toContain('/help#hrv');
        expect(document.getElementById('formula-dialog').showModal).toHaveBeenCalledOnce();
    });
});
