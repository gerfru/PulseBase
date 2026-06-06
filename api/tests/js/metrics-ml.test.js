import { describe, it, expect } from 'vitest';
import { ML_METRICS } from '../../src/static/metrics-ml.js';

describe('readiness-rf render (B-1 confidence interval)', () => {
    const render = ML_METRICS['readiness-rf'].render;

    it('shows the confidence range KPI when bounds are present', () => {
        const out = render([{ readiness_rf: { value: 67, confidence_low: 58, confidence_high: 74 } }, {}]);
        const ci = out.kpis.find((k) => k.label.startsWith('Konfidenz'));
        expect(ci).toBeTruthy();
        expect(ci.value).toBe('58–74');
    });

    it('falls back to — when confidence bounds are missing', () => {
        const out = render([{ readiness_rf: { value: 67 } }, {}]);
        const ci = out.kpis.find((k) => k.label.startsWith('Konfidenz'));
        expect(ci.value).toBe('—');
    });

    it('handles no prediction without producing NaN ranges', () => {
        const out = render([{}, {}]);
        const ci = out.kpis.find((k) => k.label.startsWith('Konfidenz'));
        expect(ci.value).toBe('—');
    });
});

describe('hr-zscore render (B-4 softened anomaly wording)', () => {
    const render = ML_METRICS['hr-zscore'].render;

    it('uses "Mögliche Auffälligkeit" instead of a factual "Anomalie" claim', () => {
        const out = render([{ anomaly_hr: { z_score: 2.5, is_anomaly: true } }, []]);
        expect(out.sub).toContain('Mögliche Auffälligkeit');
        const status = out.kpis.find((k) => k.label === 'Status');
        expect(status.value).toContain('Mögliche Auffälligkeit');
        expect(out.sub).not.toContain('Anomalie erkannt');
    });

    it('shows Normal when not flagged', () => {
        const out = render([{ anomaly_hr: { z_score: 0.3, is_anomaly: false } }, []]);
        expect(out.sub).toContain('Normal');
    });
});
