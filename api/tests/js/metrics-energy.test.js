import { beforeAll, describe, expect, it } from 'vitest';
import { ENERGY_METRICS } from '../../src/static/metrics-energy.js';

// Chart branches reference the global palette `C` (set by colors.js at page load).
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

// history with >3 entries triggers the chart branch in physical/autonomic/cognitive
const histN = (key, extra = {}) => ({
    [key]: [1, 2, 3, 4].map((n) => ({ date: `2026-05-0${n}`, value: 70, ...extra })),
});

describe('physical render', () => {
    const render = ENERGY_METRICS.physical.render;

    it('renders score/ATL/CTL/TSB + chart and the frisch recommendation', () => {
        const energy = { energy_physical: { score: 80, atl: 50.2, ctl: 60.7, tsb: 10.5 } };
        const out = render([energy, histN('energy_physical', { ctl: 60, atl: 50, tsb: 10 })]);
        expect(out.value).toBe(80);
        expect(out.sub).toBe('TSB +10.5');
        expect(out.chart).toBeTruthy();
        expect(out.recommendation).toContain('frisch');
        expect(out.kpis.find((k) => k.label === 'TSB — Balance').value).toBe('+10.5');
    });

    it('covers all TSB recommendation tiers + negative TSB formatting', () => {
        const r = (tsb) => render([{ energy_physical: { score: 70, tsb } }, {}]);
        expect(r(-5).recommendation).toContain('ausgeglichen');
        expect(r(-20).recommendation).toContain('Trainingsphase');
        expect(r(-40).recommendation).toContain('sehr negativ');
        expect(r(-40).kpis.find((k) => k.label === 'TSB — Balance').value).toBe('-40.0');
    });

    it('falls back when no physical data', () => {
        const out = render([{}, {}]);
        expect(out.value).toBe('—');
        expect(out.sub).toBe('noch keine Daten');
        expect(out.chart).toBeNull();
        expect(out.recommendation).toBeNull();
    });
});

describe('autonomic render', () => {
    const render = ENERGY_METRICS.autonomic.render;

    it('renders deviation/baseline + chart and tiers', () => {
        const energy = { energy_autonomic: { score: 75, deviation: 0.8, baseline_ln_mean: Math.log(60) } };
        const out = render([energy, histN('energy_autonomic')]);
        expect(out.value).toBe(75);
        expect(out.sub).toContain('σ vom Baseline');
        expect(out.chart).toBeTruthy();
        expect(out.kpis.find((k) => k.label.startsWith('Persönlicher')).value).toBe('60 ms');
        expect(out.recommendation).toContain('über Baseline');
    });

    it('covers all deviation tiers', () => {
        const r = (z) => render([{ energy_autonomic: { score: 60, deviation: z } }, {}]);
        expect(r(0).recommendation).toContain('Normalbereich');
        expect(r(-1).recommendation).toContain('leicht unter');
        expect(r(-2).recommendation).toContain('deutlich unter');
    });

    it('falls back when no autonomic data', () => {
        const out = render([{}, {}]);
        expect(out.value).toBe('—');
        expect(out.sub).toBe('noch keine Daten');
        expect(out.recommendation).toBeNull();
    });
});

describe('cognitive render', () => {
    const render = ENERGY_METRICS.cognitive.render;

    it('renders sleep debt + chart and all debt tiers', () => {
        const out = render([{ energy_cognitive: { score: 90, debt_hours: 0.5 } }, histN('energy_cognitive')]);
        expect(out.value).toBe(90);
        expect(out.sub).toContain('Schlafschuld');
        expect(out.chart).toBeTruthy();
        expect(out.recommendation).toContain('Kein wesentliches');
        expect(render([{ energy_cognitive: { score: 70, debt_hours: 2.5 } }, {}]).recommendation).toContain('Priorität');
        expect(render([{ energy_cognitive: { score: 40, debt_hours: 6 } }, {}]).recommendation).toContain('deutliches Defizit');
    });

    it('falls back when no cognitive data', () => {
        const out = render([{}, {}]);
        expect(out.value).toBe('—');
        expect(out.sub).toBe('noch keine Daten');
        expect(out.recommendation).toBeNull();
    });
});

describe('body-battery-custom render', () => {
    const render = ENERGY_METRICS['body-battery-custom'].render;
    const full = (score) => ({
        insights: {
            body_battery_custom: {
                score,
                sleep_quality: 0.8,
                hrv_factor: 0.9,
                sleep_h: 7.2,
                deep_h: 1.5,
                rem_h: 1.8,
                activity_drain: 12,
                stress_drain: 0,
                prev_score: 70,
            },
        },
        history: { body_battery_custom: [{ date: '2026-05-01', value: 70 }] },
        daily: [{ date: '2026-05-01', body_battery_high: 80 }],
    });

    it('renders KPIs + chart and all score tiers', () => {
        const out = render(full(82));
        expect(out.value).toBe(82);
        expect(out.sub).toContain('Gute Energie');
        expect(out.chart).toBeTruthy();
        expect(out.recommendation).toContain('Gute Energie');
        expect(render(full(50)).sub).toContain('Ausreichend');
        expect(render(full(50)).recommendation).toContain('Moderate');
        expect(render(full(20)).sub).toContain('Erschöpft');
        expect(render(full(20)).recommendation).toContain('Niedrige Energie');
    });

    it('falls back when score missing', () => {
        const out = render({ insights: { body_battery_custom: null }, history: {}, daily: [] });
        expect(out.value).toBe('—');
        expect(out.sub).toBe('Zu wenig Daten');
        expect(out.kpis).toHaveLength(0);
    });

    it('renders — for missing optional fields (drain null, no sleep metrics)', () => {
        const out = render({
            insights: { body_battery_custom: { score: 60, activity_drain: null, stress_drain: null } },
            history: { body_battery_custom: [] },
            daily: [],
        });
        expect(out.kpis.find((k) => k.label === 'Schlafqualität').value).toBe('—');
        expect(out.kpis.find((k) => k.label === 'Aktivitäts-Drain').value).toBe('—');
        expect(out.kpis.find((k) => k.label === 'Vortag').value).toBe('—');
    });
});

describe('stress-score-custom render', () => {
    const render = ENERGY_METRICS['stress-score-custom'].render;
    const full = (score) => ({
        insights: {
            stress_score_custom: {
                score,
                hrv_component: score,
                garmin_stress: 30,
                hrv_deviation: -0.5,
                n_hrv: 40,
            },
        },
        history: { stress_score_custom: [{ date: '2026-05-01', value: score }] },
        // one row with avg_stress (true branch) + one without (false branch of the forEach)
        daily: [
            { date: '2026-05-01', avg_stress: 28 },
            { date: '2026-05-02', avg_stress: null },
        ],
    });

    it('renders KPIs + chart and all level tiers', () => {
        const lo = render(full(20));
        expect(lo.sub).toContain('Niedrig');
        expect(lo.chart).toBeTruthy();
        expect(lo.recommendation).toContain('Niedriger Stress');
        expect(render(full(45)).sub).toContain('Mittel');
        expect(render(full(45)).recommendation).toContain('Moderater');
        expect(render(full(80)).sub).toContain('Hoch');
        expect(render(full(80)).recommendation).toContain('Hoher Stress');
    });

    it('falls back when score missing', () => {
        const out = render({ insights: { stress_score_custom: null }, history: {}, daily: [] });
        expect(out.value).toBe('—');
        expect(out.sub).toBe('HRV-Daten fehlen');
        expect(out.kpis).toHaveLength(0);
    });

    it('renders — for null garmin_stress and tolerates missing daily array', () => {
        const out = render({
            insights: {
                stress_score_custom: { score: 40, hrv_component: 40, garmin_stress: null, hrv_deviation: 0.1, n_hrv: 30 },
            },
            history: { stress_score_custom: [{ date: '2026-05-01', value: 40 }] },
            // daily intentionally omitted → exercises the `data.daily || []` guard
        });
        expect(out.kpis.find((k) => k.label === 'Garmin avg_stress').value).toBe('—');
    });
});

describe('branch coverage — empty sub, null-history charts, || [] fallbacks', () => {
    it('physical: empty sub when score present but no TSB + chart tolerates null CTL/ATL/TSB', () => {
        const render = ENERGY_METRICS.physical.render;
        // tsb === '—' but phys != null → the '' sub branch
        expect(render([{ energy_physical: { score: 70 } }, {}]).sub).toBe('');
        // history rows without ctl/atl/tsb → `d.ctl ?? null` etc. take the null side
        expect(render([{ energy_physical: { score: 80, tsb: 10 } }, histN('energy_physical')]).chart).toBeTruthy();
    });

    it('autonomic: empty sub without deviation + chart tolerates null values', () => {
        const render = ENERGY_METRICS.autonomic.render;
        expect(render([{ energy_autonomic: { score: 70 } }, {}]).sub).toBe('');
        expect(render([{ energy_autonomic: { score: 70 } }, histN('energy_autonomic', { value: null })]).chart).toBeTruthy();
    });

    it('cognitive: empty sub without debt + chart tolerates null values', () => {
        const render = ENERGY_METRICS.cognitive.render;
        expect(render([{ energy_cognitive: { score: 70 } }, {}]).sub).toBe('');
        expect(render([{ energy_cognitive: { score: 70 } }, histN('energy_cognitive', { value: null })]).chart).toBeTruthy();
    });

    it('body-battery + stress: history || [] fallback when the history key is missing', () => {
        const bb = ENERGY_METRICS['body-battery-custom'].render({
            insights: {
                body_battery_custom: {
                    score: 60,
                    sleep_quality: 0.8,
                    hrv_factor: 0.9,
                    sleep_h: 7,
                    deep_h: 1.5,
                    rem_h: 1.8,
                    activity_drain: 10,
                    stress_drain: 0,
                    prev_score: 70,
                },
            },
            history: {},
            daily: [],
        });
        expect(bb.value).toBe(60);
        const st = ENERGY_METRICS['stress-score-custom'].render({
            insights: {
                stress_score_custom: { score: 40, hrv_component: 40, garmin_stress: 30, hrv_deviation: 0.1, n_hrv: 30 },
            },
            history: {},
            daily: [],
        });
        expect(st.value).toBe('40');
    });
});

describe('metric fetch() methods', () => {
    it('each metric fetches its endpoints and parses JSON', async () => {
        const calls = [];
        globalThis.fetch = (url) => {
            calls.push(url);
            return Promise.resolve({ json: () => Promise.resolve({}) });
        };
        for (const key of Object.keys(ENERGY_METRICS)) {
            await ENERGY_METRICS[key].fetch();
        }
        expect(calls.some((u) => u.includes('/api/energy'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/ml-history'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/ml-insights'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/daily'))).toBe(true);
    });
});
