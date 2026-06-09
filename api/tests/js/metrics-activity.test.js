import { beforeAll, describe, expect, it } from 'vitest';
import { ACTIVITY_METRICS } from '../../src/static/metrics-activity.js';

beforeAll(() => {
    globalThis.C = {
        red: '#ef4444',
        indigo: '#818cf8',
        green: '#22c55e',
        amber: '#f59e0b',
        blue: '#60a5fa',
        violet: '#a78bfa',
        muted: '#94a3b8',
    };
});

describe('intensity-minutes render', () => {
    const render = ACTIVITY_METRICS['intensity-minutes'].render;
    const ins = (mod, vig) => ({ intensity_minutes_custom: { moderate_minutes: mod, vigorous_minutes: vig, hrmax_used: 185 } });

    it('renders totals and all recommendation tiers', () => {
        expect(render(ins(40, 10)).recommendation).toContain('Wochenziel'); // total 60 >= 30
        expect(render(ins(10, 0)).recommendation).toContain('einplanen'); // total 10 > 0
        expect(render(ins(0, 0)).recommendation).toContain('keine Intensitätsminuten');
    });

    it('falls back without data', () => {
        const out = render({ intensity_minutes_custom: null });
        expect(out.value).toBe('—');
        expect(out.kpis).toHaveLength(0);
    });

    it('renders — for a missing HRmax', () => {
        const out = render({ intensity_minutes_custom: { moderate_minutes: 20, vigorous_minutes: 5, hrmax_used: null } });
        expect(out.kpis.find((k) => k.label.startsWith('HRmax')).value).toBe('—');
    });
});

describe('training-effect render', () => {
    const render = ACTIVITY_METRICS['training-effect'].render;
    const ins = (effect) => ({
        training_effect_custom: { effect, trimp_today: 90, ctl: 60, vo2max: 52 },
    });

    it('renders badge + all effect tiers (label + recommendation)', () => {
        expect(render(ins(4.2)).recommendation).toContain('sehr intensiv');
        expect(render(ins(4.2)).sub).toContain('Überbelastend');
        expect(render(ins(3.0)).recommendation).toContain('guter Trainingsreiz');
        expect(render(ins(3.0)).sub).toContain('Stark');
        expect(render(ins(2.2)).sub).toContain('Moderat');
        expect(render(ins(1.5)).recommendation).toContain('leichter Reiz');
        expect(render(ins(1.5)).sub).toContain('Leicht');
        expect(render(ins(0.5)).recommendation).toContain('minimaler Reiz');
        expect(render(ins(0.5)).sub).toContain('Minimal');
    });

    it('falls back without profile data', () => {
        expect(render({ training_effect_custom: null }).value).toBe('—');
    });

    it('renders — for missing trimp/ctl/vo2max', () => {
        const out = render({ training_effect_custom: { effect: 3.0 } });
        expect(out.kpis.find((k) => k.label === 'TRIMP heute').value).toBe('—');
        expect(out.kpis.find((k) => k.label.startsWith('VO₂max')).value).toBe('—');
    });
});

describe('training-monotony render', () => {
    const render = ACTIVITY_METRICS['training-monotony'].render;
    const data = (mono) => ({
        insights: { training_monotony: { monotony: mono, strain: 1200, trimp_7d_mean: 80, trimp_7d_std: 40 } },
        history: {},
    });

    it('renders KPIs and all risk/recommendation tiers', () => {
        const good = render(data(1.2));
        expect(good.sub).toContain('Gute Variation');
        expect(good.recommendation).toContain('gute Variation');
        expect(render(data(1.7)).sub).toContain('Moderat');
        expect(render(data(1.7)).recommendation).toContain('leicht erhöht');
        expect(render(data(2.5)).sub).toContain('Zu monoton');
        expect(render(data(2.5)).recommendation).toContain('kritisch hoch');
    });

    it('falls back without training data', () => {
        const out = render({ insights: { training_monotony: null }, history: {} });
        expect(out.value).toBe('—');
        expect(out.kpis).toHaveLength(0);
    });
});

describe('running-economy render', () => {
    const render = ACTIVITY_METRICS['running-economy'].render;
    const data = (score) => ({
        insights: {
            running_economy: { score, avg_gct_ms: 230, avg_vo_mm: 70.5, avg_vr_pct: 7.2, n_activities: 6 },
        },
        history: { running_economy: [{ date: '2026-05-01', value: score }] },
    });

    it('renders KPIs + chart and all quality/recommendation tiers', () => {
        const top = render(data(85));
        expect(top.sub).toContain('Ausgezeichnet');
        expect(top.chart).toBeTruthy();
        expect(top.recommendation).toContain('effizienter Laufstil');
        expect(render(data(65)).sub).toContain('Gut');
        expect(render(data(65)).recommendation).toContain('durchschnittlich');
        expect(render(data(45)).sub).toContain('Verbesserbar');
        expect(render(data(30)).sub).toContain('Suboptimal');
        expect(render(data(30)).recommendation).toContain('Verbesserungspotenzial');
    });

    it('falls back without running data', () => {
        const out = render({ insights: { running_economy: null }, history: {} });
        expect(out.value).toBe('—');
        expect(out.kpis).toHaveLength(0);
    });
});

describe('metric fetch() methods', () => {
    it('each metric fetches its endpoints and parses JSON', async () => {
        const calls = [];
        globalThis.fetch = (url) => {
            calls.push(url);
            return Promise.resolve({ json: () => Promise.resolve({}) });
        };
        for (const key of Object.keys(ACTIVITY_METRICS)) {
            await ACTIVITY_METRICS[key].fetch();
        }
        expect(calls.some((u) => u.includes('/api/ml-insights'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/ml-history'))).toBe(true);
    });
});
