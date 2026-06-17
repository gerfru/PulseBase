import { describe, it, expect } from 'vitest';
import {
    mdInline,
    renderInsight,
    shiftWeek,
} from '../../src/static/insights.js';

const DATA = {
    iso_year: 2026,
    iso_week: 24,
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

describe('mdInline', () => {
    it('renders **bold** as <strong>', () => {
        expect(mdInline('Heute **gut** erholt')).toBe('Heute <strong>gut</strong> erholt');
    });

    it('escapes before bolding (XSS-safe)', () => {
        expect(mdInline('**<script>x</script>**')).not.toContain('<script>');
    });
});

describe('shiftWeek', () => {
    it('moves back across the year boundary', () => {
        expect(shiftWeek(2026, 1, -1)).toEqual([2025, 52]);
    });

    it('round-trips forward and back', () => {
        const [y, w] = shiftWeek(2026, 24, -3);
        expect(shiftWeek(y, w, 3)).toEqual([2026, 24]);
    });
});
