import { describe, it, expect } from 'vitest';
import {
    mdInline,
    renderInsight,
    periodRangeLabel,
} from '../../src/static/insights.js';

const DATA = {
    period_start: '2026-06-08',
    period_end: '2026-06-14',
    insight: {
        metrics: [
            { key: 'time_in_range', value: '58', unit: '%', change_pct: null, trend: 'stable' },
        ],
    },
    texts: {
        hobby: { body: 'Hallo Welt', generator: 'llm', model_id: 'llama3.1:8b' },
        pro: { body: 'Sachlich', generator: 'fallback_template', model_id: null },
    },
};

describe('renderInsight', () => {
    it('renders body + German label + arrow + KI badge', () => {
        const html = renderInsight(DATA, 'hobby');
        expect(html).toContain('Hallo Welt');
        expect(html).toContain('Zeit im Zielbereich'); // German label, not raw key
        expect(html).not.toContain('time_in_range');
        expect(html).toContain('→'); // stable arrow, not "stable"
        expect(html).toContain('KI-generiert');
        expect(html).toContain('llama3.1:8b');
    });

    it('shows the fallback badge for a fallback segment', () => {
        expect(renderInsight(DATA, 'pro')).toContain('Standardtext');
    });

    it('escapes hostile content', () => {
        const evil = {
            insight: { metrics: [] },
            texts: { hobby: { body: '<script>x</script>', generator: 'llm' } },
        };
        expect(renderInsight(evil, 'hobby')).not.toContain('<script>x</script>');
    });

    it('returns empty string for null data', () => {
        expect(renderInsight(null, 'hobby')).toBe('');
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
