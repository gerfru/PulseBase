import { beforeAll, describe, expect, it } from 'vitest';
import { READINESS_METRICS } from '../../src/static/metrics-readiness.js';

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

const dates4 = (v) => [1, 2, 3, 4].map((n) => ({ date: `2026-05-0${n}`, value: v }));

describe('readiness render', () => {
    const render = READINESS_METRICS.readiness.render;

    it('builds value/customHtml/charts and the good recommendation', () => {
        const today = { score: 80, label: 'Gut erholt' };
        const energy = {
            energy_autonomic: { score: 78, deviation: 0.5 },
            energy_cognitive: { score: 65, debt_hours: 2 },
        };
        const history = { energy_autonomic: dates4(78), energy_cognitive: dates4(65) };
        const out = render([today, energy, history]);
        expect(out.value).toContain('80');
        expect(out.sub).toBe('Gut erholt');
        expect(out.customHtml).toContain('Autonom');
        expect(out.customHtml).toContain('Kognitiv');
        expect(out.customHtml).toContain('svg'); // sparkline rendered (4 values)
        expect(out.charts).toHaveLength(1);
        expect(out.recommendation).toContain('Gut erholt');
    });

    it('covers score recommendation tiers + low-component colors + missing-data details', () => {
        const r = (score, energy = {}) => render([{ score }, energy, {}]);
        expect(r(60).recommendation).toContain('in Ordnung');
        expect(r(40).recommendation).toContain('eingeschränkt');
        expect(r(20).recommendation).toContain('Erhebliches Defizit');
        // low autonomic (<45 → red tile), cognitive missing → "keine Daten" detail
        const low = render([{ score: 30 }, { energy_autonomic: { score: 30, deviation: -1 } }, {}]);
        expect(low.customHtml).toContain('keine Daten');
    });

    it('falls back to — with null score and no recommendation', () => {
        const out = render([{}, {}, {}]);
        expect(out.value).toBe('—');
        expect(out.charts).toEqual([]);
        expect(out.recommendation).toBeNull();
    });
});

describe('hrv-recovery render', () => {
    const render = READINESS_METRICS['hrv-recovery'].render;
    const full = (speed) => ({
        insights: {
            hrv_recovery: { recovery_speed: speed, n_events: 5, hrv_baseline: 58, trimp_threshold: 120 },
        },
        history: {},
    });

    it('renders speed tiers + KPIs', () => {
        const fast = render(full(2.5));
        expect(fast.sub).toContain('Schnell');
        expect(fast.value).toContain('+2.5');
        expect(fast.recommendation).toContain('Schnelle');
        expect(render(full(1)).sub).toContain('Normal');
        expect(render(full(1)).recommendation).toContain('Normale');
        expect(render(full(-1)).sub).toContain('Verzögert');
        expect(render(full(-1)).recommendation).toContain('Verzögerte');
    });

    it('falls back when recovery_speed missing', () => {
        const out = render({ insights: { hrv_recovery: null }, history: {} });
        expect(out.value).toBe('—');
        expect(out.kpis).toHaveLength(0);
    });
});

describe('recovery render', () => {
    const render = READINESS_METRICS.recovery.render;

    it('renders KPIs, two charts, correlation and a combined recommendation', () => {
        // ascending weekly so the latest (70) is clearly above the 90d mean → "HRV über Ø"
        const hrv = [55, 60, 65, 70].map((w, i) => ({
            date: `2026-05-0${i + 1}`,
            hrv_last_night: w,
            hrv_weekly_avg: w,
        }));
        const sleep = [1, 2, 3, 4].map((n) => ({
            date: `2026-05-0${n}`,
            sleep_score: 80,
            total_sleep_seconds: 27000,
            deep_sleep_seconds: 5400,
        }));
        const insights = { correlation_sleep_hrv: { r: 0.7, interpretation: 'stark', n: 30, p_value: 0.01 } };
        const out = render({ hrv, sleep, insights });
        expect(out.charts).toHaveLength(2);
        expect(out.kpis.find((k) => k.label === 'Schlaf → HRV').value).toContain('r = 0.70');
        expect(out.kpis.find((k) => k.label === 'p-Wert')).toBeTruthy();
        expect(out.recommendation).toContain('HRV über Ø');
        expect(out.recommendation).toContain('Schlaf-Score gut');
    });

    it('covers low-HRV / low-sleep recommendation branches', () => {
        // descending weekly so the latest (35) is clearly below the 90d mean → "HRV unter Ø"
        const hrv = [50, 45, 40, 35].map((w, i) => ({ date: `2026-05-0${i + 1}`, hrv_last_night: w, hrv_weekly_avg: w }));
        const sleep = [1, 2, 3, 4].map((n) => ({ date: `2026-05-0${n}`, sleep_score: 45, total_sleep_seconds: 18000 }));
        const out = render({ hrv, sleep, insights: { correlation_sleep_hrv: { r: null } } });
        expect(out.recommendation).toContain('HRV unter Ø');
        expect(out.recommendation).toContain('Schlafhygiene');
        expect(out.kpis.find((k) => k.label === 'Schlaf → HRV').value).toBe('Zu wenig Daten');
    });

    it('falls back to — when no nightly data', () => {
        const out = render({ hrv: [], sleep: [], insights: {} });
        expect(out.value).toBe('—');
        expect(out.recommendation).toBeNull();
    });
});

describe('metric fetch() methods', () => {
    it('each metric fetches its endpoints and parses JSON', async () => {
        const calls = [];
        globalThis.fetch = (url) => {
            calls.push(url);
            return Promise.resolve({ json: () => Promise.resolve({}) });
        };
        for (const key of Object.keys(READINESS_METRICS)) {
            await READINESS_METRICS[key].fetch();
        }
        expect(calls.some((u) => u.includes('/api/readiness'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/ml-insights'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/hrv/trend'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/sleep'))).toBe(true);
    });
});
