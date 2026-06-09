import { beforeAll, describe, expect, it } from 'vitest';
import { SLEEP_METRICS } from '../../src/static/metrics-sleep.js';

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

describe('sleep-score-custom render', () => {
    const render = SLEEP_METRICS['sleep-score-custom'].render;
    const ins = (score) => ({
        sleep_score_custom: { score, total_h: 7.5, deep_pct: 19, rem_pct: 22, wake_pct: 3 },
    });

    it('renders badge + KPIs and all quality tiers', () => {
        const good = render(ins(82));
        expect(good.sub).toContain('Gut');
        expect(good.recommendation).toContain('ausgezeichnet');
        expect(good.kpis.find((k) => k.label === 'Tiefschlaf').value).toBe('19 %');
        expect(render(ins(60)).sub).toContain('Okay');
        expect(render(ins(60)).recommendation).toContain('okay');
        expect(render(ins(40)).sub).toContain('Schlecht');
        expect(render(ins(40)).recommendation).toContain('niedrig');
    });

    it('falls back when no sleep score', () => {
        const out = render({ sleep_score_custom: null });
        expect(out.value).toBe('—');
        expect(out.sub).toBe('Keine Schlafdaten');
        expect(out.kpis).toHaveLength(0);
    });

    it('renders — KPIs when phase fields are missing', () => {
        const out = render({ sleep_score_custom: { score: 70 } });
        expect(out.kpis.find((k) => k.label === 'Schlafdauer').value).toBe('—');
        expect(out.kpis.find((k) => k.label === 'Tiefschlaf').value).toBe('—');
    });
});

describe('hrv-status-custom render', () => {
    const render = SLEEP_METRICS['hrv-status-custom'].render;
    const data = (status, withHist = false) => ({
        insights: {
            hrv_status_custom: {
                status,
                deviation: -0.3,
                baseline_mean: 3.9,
                baseline_std: 0.2,
                hrv_7d_mean: 3.8,
            },
        },
        history: withHist
            ? {
                  hrv_status_custom: [
                      { date: '2026-05-01', status: 'BALANCED' },
                      { date: '2026-05-02', status: 'WEIRD' }, // unknown → statusToScore ?? null
                      { date: '2026-05-03', status: null }, // null → : null branch
                      { date: '2026-05-04', status: 'LOW' },
                  ],
              }
            : {},
    });

    it('renders badge + chart and maps every status to a recommendation', () => {
        const bal = render(data('BALANCED', true));
        expect(bal.value).toContain('BALANCED');
        expect(bal.chart).toBeTruthy();
        // axis tick callback maps the status-score back to labels (real render logic)
        const tick = bal.chart.scales.y.ticks.callback;
        expect(tick(100)).toBe('BALANCED');
        expect(tick(0)).toBe('POOR');
        expect(tick(999)).toBe('');
        expect(bal.recommendation).toContain('ausgeglichen');
        expect(render(data('UNBALANCED')).recommendation).toContain('gedämpft');
        expect(render(data('LOW')).recommendation).toContain('Regeneration');
        expect(render(data('POOR')).recommendation).toContain('Regeneration');
    });

    it('falls back when no status', () => {
        const out = render({ insights: { hrv_status_custom: null }, history: {} });
        expect(out.value).toBe('—');
        expect(out.kpis).toHaveLength(0);
    });

    it('handles an unknown status + missing deviation/baseline (null recommendation, — KPIs)', () => {
        const out = render({ insights: { hrv_status_custom: { status: 'WEIRD' } }, history: {} });
        expect(out.recommendation).toBeNull();
        expect(out.kpis.find((k) => k.label === 'σ-Abweichung').value).toBe('—');
        expect(out.kpis.find((k) => k.label === 'Baseline Mean').value).toBe('—');
    });
});

describe('sleep-consistency render', () => {
    const render = SLEEP_METRICS['sleep-consistency'].render;
    const nights = (n) =>
        Array.from({ length: n }, (_, i) => ({
            date: `2026-05-${String(i + 1).padStart(2, '0')}`,
            start_time: `2026-05-${String(i + 1).padStart(2, '0')}T23:00:00`,
            end_time: `2026-05-${String(i + 2).padStart(2, '0')}T07:00:00`,
        }));
    const data = (score, sleepNights = 8) => ({
        insights: { sleep_consistency: { score, std_wake_h: 0.4, std_sleep_h: 0.3, n_nights: sleepNights } },
        sleep: nights(sleepNights),
    });

    it('renders KPIs + chart (>=7 nights) and all quality tiers', () => {
        const out = render(data(85));
        expect(out.sub).toContain('Ausgezeichnet');
        expect(out.chart).toBeTruthy();
        expect(out.chart.scales.y.ticks.callback(8)).toBe('08:00'); // axis label formatter
        expect(out.recommendation).toContain('konsistenter');
        expect(render(data(72)).sub).toContain('Gut');
        expect(render(data(64)).sub).toContain('Akzeptabel');
        expect(render(data(50)).sub).toContain('Schlecht');
        expect(render(data(50)).recommendation).toContain('Unregelmäßiger');
    });

    it('omits chart with fewer than 7 nights', () => {
        const out = render(data(75, 5));
        expect(out.chart).toBeNull();
        expect(out.recommendation).toContain('Mäßig');
    });

    it('skips nights without start/end times when building the rhythm', () => {
        const sleep = [
            ...nights(7),
            { date: '2026-05-30', start_time: null, end_time: null }, // skipped branch
        ];
        const out = render({
            insights: { sleep_consistency: { score: 85, std_wake_h: 0.4, std_sleep_h: 0.3, n_nights: 7 } },
            sleep,
        });
        expect(out.chart).toBeTruthy();
    });

    it('falls back when no consistency score', () => {
        const out = render({ insights: { sleep_consistency: null }, sleep: [] });
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
        for (const key of Object.keys(SLEEP_METRICS)) {
            await SLEEP_METRICS[key].fetch();
        }
        expect(calls.some((u) => u.includes('/api/ml-insights'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/ml-history'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/sleep'))).toBe(true);
    });
});
