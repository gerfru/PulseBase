import { describe, it, expect } from 'vitest';
import {
    mdInline,
    renderInsight,
    periodRangeLabel,
    visibleReport,
    statusMessage,
    shouldRefreshAtFive,
} from '../../src/static/insights.js';

const DATA = {
    period_start: '2026-06-08',
    period_end: '2026-06-14',
    insight: {
        metrics: [
            { key: 'time_in_range', value: '58', unit: '%', change_pct: null, trend: 'stable' },
        ],
    },
    text: {
        body: 'Zusammenfassung\nHallo Welt.\n\nKennzahlen\n- Zeit im Zielbereich: 58 % (stabil).\n\nEinordnung\nDie Daten zeigen eine Entwicklung.\n\nHinweis\nKein medizinischer Rat.',
        generator: 'llm',
        model_id: 'llama3.1:8b',
    },
};

describe('renderInsight', () => {
    it('renders four semantic sections without repeating the metrics', () => {
        const html = renderInsight(DATA);
        expect(html).toContain('Hallo Welt');
        expect(html).toContain('<h2 class="text-sm font-semibold mb-2">Kennzahlen</h2>');
        expect(html).toContain('<li>Zeit im Zielbereich: 58 % (stabil).</li>');
        expect((html.match(/58/g) || []).length).toBe(1);
        expect(html).not.toContain('time_in_range');
        expect(html).toContain('KI-generiert');
        expect(html).toContain('llama3.1:8b');
    });

    it('shows the fallback badge for the single mode', () => {
        const fallback = {
            ...DATA,
            text: { body: 'Standardauswertung', generator: 'fallback_template', model_id: null },
        };
        expect(renderInsight(fallback)).toContain('Standardtext');
    });

    it('escapes hostile content', () => {
        const evil = {
            insight: { metrics: [] },
            text: {
                body: 'Zusammenfassung\n<script>x</script>\n\nKennzahlen\n- <img src=x onerror=alert(1)>\n\nEinordnung\nText.\n\nHinweis\nRat.',
                generator: 'llm',
            },
        };
        const html = renderInsight(evil);
        expect(html).not.toContain('<script>');
        expect(html).not.toContain('<img');
        expect(html).toContain('&lt;script&gt;');
    });

    it('returns empty string for null data', () => {
        expect(renderInsight(null)).toBe('');
    });
});

describe('periodRangeLabel', () => {
    it('formats the rolling window as dd.mm.–dd.mm.', () => {
        expect(periodRangeLabel('2026-06-08', '2026-06-14')).toBe('08.06.–14.06.');
    });

    it('falls back to the raw input for malformed dates', () => {
        expect(periodRangeLabel('garbage', '2026-06-14')).toBe('garbage–14.06.');
    });
});

describe('mdInline', () => {
    it('renders **bold** as <strong>', () => {
        expect(mdInline('Heute **gut** erholt')).toBe('Heute <strong>gut</strong> erholt');
    });

    it('escapes before bolding (XSS-safe)', () => {
        expect(mdInline('**<script>x</script>**')).not.toContain('<script>');
    });
});

describe('daily report states', () => {
    const waiting = {
        status: 'pending',
        period_start: '2026-06-09',
        period_end: '2026-06-15',
        report: DATA,
    };

    it('keeps the previous report and its actual period while waiting', () => {
        expect(visibleReport(waiting).period_end).toBe('2026-06-14');
        expect(statusMessage(waiting)).toContain('09.06.–15.06.');
        expect(visibleReport({ ...waiting, status: 'stale' })).toBe(DATA);
        expect(visibleReport({ ...waiting, status: 'failed' })).toBe(DATA);
    });

    it('shows empty and ready states without inventing a report', () => {
        expect(visibleReport({ ...waiting, report: null })).toBeNull();
        expect(statusMessage({ ...waiting, report: null })).not.toContain('letzte fertige Bericht');
        expect(statusMessage({ ...waiting, status: 'stale', report: null })).toContain('geplant');
        expect(visibleReport({ ...DATA, status: 'ready' })).toMatchObject(DATA);
        expect(statusMessage({ ...DATA, status: 'ready' })).toBe('');
    });

    it('refreshes at Vienna 05:00 across both DST transitions', () => {
        expect(shouldRefreshAtFive('2026-03-28', new Date('2026-03-29T02:59:00Z'))).toBe(false);
        expect(shouldRefreshAtFive('2026-03-28', new Date('2026-03-29T03:00:00Z'))).toBe(true);
        expect(shouldRefreshAtFive('2026-10-24', new Date('2026-10-25T03:59:00Z'))).toBe(false);
        expect(shouldRefreshAtFive('2026-10-24', new Date('2026-10-25T04:00:00Z'))).toBe(true);
        expect(shouldRefreshAtFive('2026-10-25', new Date('2026-10-25T04:00:00Z'))).toBe(false);
    });
});
