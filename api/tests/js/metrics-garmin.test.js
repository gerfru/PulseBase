import { beforeAll, describe, expect, it } from 'vitest';
import { GARMIN_METRICS } from '../../src/static/metrics-garmin.js';

beforeAll(() => {
    globalThis.C = {
        red: '#ef4444',
        indigo: '#818cf8',
        green: '#22c55e',
        amber: '#f59e0b',
        blue: '#60a5fa',
        violet: '#a78bfa',
        orange: '#fb923c',
        muted: '#94a3b8',
    };
});

describe('steps render', () => {
    const render = GARMIN_METRICS.steps.render;

    it('renders KPIs/chart and all step tiers', () => {
        expect(render([{ date: '2026-05-01', steps: 12000 }]).recommendation).toContain('Aktivitätsziel erreicht');
        expect(render([{ date: '2026-05-01', steps: 8000 }]).recommendation).toContain('Grundaktivität');
        const low = render([{ date: '2026-05-01', steps: 3000 }]);
        expect(low.recommendation).toContain('unter 7.000');
        expect(low.chart).toBeTruthy();
        // toLocaleString separator is ICU/Node-dependent — just assert it's populated
        expect(low.kpis.find((k) => k.label === 'Maximum').value).toMatch(/3/);
    });

    it('falls back on empty data and tolerates a zero-step day in the chart', () => {
        const out = render([]);
        expect(out.value).toBe('—');
        expect(out.recommendation).toBeNull();
        // a day with no steps exercises the `d.steps || 0` chart-data branch
        const withZero = render([{ date: '2026-05-01', steps: 0 }]);
        expect(withZero.chart.datasets[0].data[0]).toBe(0);
    });
});

describe('sleep render', () => {
    const render = GARMIN_METRICS.sleep.render;
    const rhythmNights = (score) =>
        Array.from({ length: 8 }, (_, i) => ({
            date: `2026-05-0${i + 1}`,
            sleep_score: score,
            total_sleep_seconds: 27000,
            deep_sleep_seconds: 5400,
            start_time: `2026-05-0${i + 1}T23:00:00`,
            end_time: `2026-05-0${i + 2}T07:00:00`,
        }));

    it('renders rhythm chart (>=7 nights) + KPIs and all score tiers', () => {
        const out = render(rhythmNights(85));
        expect(out.chart.title).toContain('Rhythmus');
        expect(out.kpis.find((k) => k.label === 'Ø Einschlafzeit')).toBeTruthy();
        const tick = out.chart.scales.y.ticks.callback; // axis label formatter
        expect(tick(0)).toBe('00:00');
        expect(tick(24)).toBe('00:00');
        expect(tick(6)).toBe('06:00');
        expect(out.recommendation).toContain('ausgezeichnet');
        expect(render(rhythmNights(70)).recommendation).toContain('gut');
        expect(render(rhythmNights(50)).recommendation).toContain('ausreichend');
        expect(render(rhythmNights(30)).recommendation).toContain('niedrig');
    });

    it('uses the score-chart fallback without rhythm data', () => {
        const out = render([
            { date: '2026-05-01', sleep_score: 70 },
            { date: '2026-05-02', sleep_score: 72 },
        ]);
        expect(out.chart.title).toContain('Schlaf-Score Verlauf');
    });

    it('falls back to — with no score', () => {
        expect(render([{ date: '2026-05-01' }]).value).toBe('—');
    });
});

describe('hrv render', () => {
    const render = GARMIN_METRICS.hrv.render;
    const series = (weekly) => [
        { date: '2026-05-01', hrv_weekly_avg: 50, hrv_last_night: 50, hrv_status: 'BALANCED' },
        { date: '2026-05-02', hrv_weekly_avg: weekly, hrv_last_night: weekly, hrv_status: 'BALANCED' },
    ];

    it('renders KPIs/chart and all delta tiers', () => {
        expect(render(series(60)).recommendation).toContain('über deinem');
        expect(render(series(50)).recommendation).toContain('Normalbereich');
        expect(render(series(40)).recommendation).toContain('unter deinem');
    });

    it('falls back when no weekly HRV', () => {
        expect(render([{ date: '2026-05-01' }]).recommendation).toBeNull();
    });
});

describe('body-battery render', () => {
    const render = GARMIN_METRICS['body-battery'].render;
    const series = (high) => [
        { date: '2026-05-01', body_battery_high: 50, body_battery_low: 20 },
        { date: '2026-05-02', body_battery_high: high, body_battery_low: 20 },
    ];

    it('renders KPIs/chart and all tiers', () => {
        expect(render(series(80)).recommendation).toContain('gute Energie');
        expect(render(series(50)).recommendation).toContain('moderate Energie');
        const low = render(series(30));
        expect(low.recommendation).toContain('niedrig');
        expect(low.chart).toBeTruthy();
    });

    it('falls back when no battery data', () => {
        expect(render([{ date: '2026-05-01' }]).recommendation).toBeNull();
    });
});

describe('spo2-trend render (regression: recommendation must not crash)', () => {
    const render = GARMIN_METRICS['spo2-trend'].render;
    const data = (mean, opts = {}) => ({
        insights: {
            spo2_trend: {
                mean_spo2: mean,
                min_spo2_7d: 92,
                slope: opts.slope ?? 0.1,
                apnea_nights: opts.apnea_nights ?? 0,
                n_days: 7,
                trend: opts.trend ?? 'stable',
                apnea_flag: opts.apnea_flag ?? false,
            },
        },
        daily: [],
    });

    it('renders KPIs and all SpO2 recommendation tiers without throwing', () => {
        expect(render(data(97)).recommendation).toContain('normaler Bereich');
        expect(render(data(92)).recommendation).toContain('Aufmerksamkeit');
        expect(render(data(88)).recommendation).toContain('Arzt');
    });

    it('shows the apnea disclaimer + falling/rising trend icons', () => {
        const flagged = render(data(89, { apnea_flag: true, apnea_nights: 3, trend: 'falling', slope: -0.3 }));
        expect(flagged.sub).toContain('Flag aktiv');
        expect(flagged.science).toContain('Disclaimer');
        expect(render(data(96, { trend: 'rising' })).sub).toContain('rising');
    });

    it('falls back when no SpO2 data', () => {
        const out = render({ insights: { spo2_trend: null }, daily: [] });
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
        for (const key of Object.keys(GARMIN_METRICS)) {
            await GARMIN_METRICS[key].fetch();
        }
        expect(calls.some((u) => u.includes('/api/daily'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/sleep'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/hrv/trend'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/ml-insights'))).toBe(true);
    });
});
