import { beforeAll, describe, expect, it } from 'vitest';
import { ML_METRICS } from '../../src/static/metrics-ml.js';

// Chart branches reference the global palette `C` (set by colors.js at page load).
beforeAll(() => {
    globalThis.C = {
        red: '#ef4444',
        indigo: '#818cf8',
        green: '#22c55e',
        amber: '#f59e0b',
        blue: '#60a5fa',
        muted: '#94a3b8',
    };
});

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
        expect(out.recommendation).toBeNull();
    });

    it('classifies score tiers (good ≥75, moderate ≥50, low) and builds the history chart', () => {
        const meta = { n_rows: 90, trained_at: '2026-05-01' };
        const hist = { readiness_rf: [1, 2, 3, 4].map((n) => ({ date: `2026-05-0${n}`, value: 70 })) };
        const good = render([{ readiness_rf: { value: 82 }, model_meta_rf: meta }, hist]);
        expect(good.sub).toContain('Gut');
        expect(good.chart).toBeTruthy();
        expect(good.recommendation).toContain('gute Erholung');
        expect(render([{ readiness_rf: { value: 60 } }, {}]).recommendation).toContain('moderate');
        expect(render([{ readiness_rf: { value: 30 } }, {}]).recommendation).toContain('leicht');
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
        expect(out.recommendation).toContain('Normalbereich');
    });

    it('builds the RHR chart + delta and warns on a high anomaly (z>2)', () => {
        const daily = [
            { date: '2026-05-01', resting_hr: 48 },
            { date: '2026-05-02', resting_hr: 55 },
        ];
        const out = render([{ anomaly_hr: { z_score: 2.4, is_anomaly: true, baseline_mean: 49.6 } }, daily]);
        expect(out.chart).toBeTruthy();
        const rhr = out.kpis.find((k) => k.label === 'Ruhepuls heute');
        expect(rhr.delta).toBe(7);
        expect(out.recommendation).toContain('ungewöhnlich hoch');
    });

    it('handles no ML data (null anomaly) with a fallback recommendation and no chart', () => {
        const out = render([{}, []]);
        expect(out.chart).toBeNull();
        expect(out.recommendation).toContain('Noch keine ML-Auswertung');
        expect(out.sub).toBe('zu wenig Daten');
    });

    it('uses the soft "Mögliche Auffälligkeit" wording for a flagged but not-high z-score', () => {
        const out = render([{ anomaly_hr: { z_score: 1.6, is_anomaly: true } }, []]);
        expect(out.recommendation).toBe('Mögliche Auffälligkeit — auf körperliche Signale achten.');
    });
});

describe('metric fetch() methods', () => {
    it('each metric fetches its API endpoint(s) and parses JSON', async () => {
        const calls = [];
        globalThis.fetch = (url) => {
            calls.push(url);
            return Promise.resolve({ json: () => Promise.resolve({}) });
        };
        for (const key of Object.keys(ML_METRICS)) {
            await ML_METRICS[key].fetch();
        }
        expect(calls.length).toBeGreaterThanOrEqual(Object.keys(ML_METRICS).length);
        expect(calls.some((u) => u.includes('/api/ml-insights'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/hrv/trend'))).toBe(true);
        expect(calls.some((u) => u.includes('/api/training-status'))).toBe(true);
    });
});

describe('hrv-status render', () => {
    const render = ML_METRICS['hrv-status'].render;

    it('maps balanced/unbalanced/low keys to labels + recommendations', () => {
        expect(render([{ hrv_status: 'BALANCED', hrv_last_night: 80 }]).recommendation).toContain('ausgeglichen');
        expect(render([{ hrv_status: 'UNBALANCED' }]).recommendation).toContain('Moderate');
        expect(render([{ hrv_status: 'LOW' }]).recommendation).toContain('regenerieren');
    });

    it('builds the chart when nightly HRV exists and counts balanced days', () => {
        const data = [
            { date: '2026-05-01', hrv_status: 'balanced', hrv_last_night: 70 },
            { date: '2026-05-02', hrv_status: 'unbalanced', hrv_last_night: 60 },
        ];
        const out = render(data);
        expect(out.chart).toBeTruthy();
        const bal = out.kpis.find((k) => k.label.startsWith('Ausgeglichen'));
        expect(bal.value).toBe('1 / 2 Tage');
    });

    it('returns — and null recommendation for empty/unknown status', () => {
        const out = render([]);
        expect(out.value).toBe('—');
        expect(out.recommendation).toBeNull();
    });
});

describe('training-status render', () => {
    const render = ML_METRICS['training-status'].render;

    it('maps every known status to a label + recommendation', () => {
        for (const [status, needle] of [
            ['PRODUCTIVE', 'aufbauend'],
            ['MAINTAINING', 'gehalten'],
            ['RECOVERY', 'Erholungsphase'],
            ['OVERREACHING', 'Übertraining'],
            ['DETRAINING', 'nimmt ab'],
        ]) {
            expect(render([{ training_status: status }, {}]).recommendation).toContain(needle);
        }
    });

    it('builds the TSB chart from physical-energy history', () => {
        const hist = { energy_physical: [1, 2, 3, 4].map((n) => ({ date: `2026-05-0${n}`, tsb: 5 })) };
        const out = render([{ training_status: 'PRODUCTIVE', date: '2026-05-04' }, hist]);
        expect(out.chart).toBeTruthy();
        expect(out.sub).toContain('Stand');
    });

    it('handles unknown status (no badge, null recommendation, no chart)', () => {
        const out = render([{ training_status: 'WEIRD' }, {}]);
        expect(out.value).toBe('—');
        expect(out.recommendation).toBeNull();
        expect(out.chart).toBeNull();
    });
});

describe('battery-pattern render', () => {
    const render = ML_METRICS['battery-pattern'].render;

    it('returns an early "zu wenig Daten" object when no pattern', () => {
        const out = render({ battery_pattern: null });
        expect(out.value).toBe('—');
        expect(out.recommendation).toContain('Noch keine ML-Auswertung');
        expect(out.kpis).toBeUndefined();
    });

    it('renders each pattern with icon, features and recommendation', () => {
        const feat = { morning_avg: 70.4, evening_avg: 30.1, daily_range: 55.2, auc: 48.9, n_dips: 3 };
        const hi = render({ battery_pattern: { pattern: 'stabil_hoch', cluster: 1, features: feat } });
        expect(hi.recommendation).toContain('Stabiles');
        expect(hi.kpis.find((k) => k.label === 'Morgen (06–09h)').value).toBe('70.4');
        expect(render({ battery_pattern: { pattern: 'erholung' } }).recommendation).toContain('Erholungsmuster');
        expect(render({ battery_pattern: { pattern: 'erschoepft' } }).recommendation).toContain('Erschöpftes');
    });
});

describe('correlations render', () => {
    const render = ML_METRICS.correlations.render;

    it('renders positive/negative correlations with strength + direction-match flags', () => {
        const out = render({
            correlation_sleep_hrv: { r: 0.72, n: 40 },
            correlation_sleep_rhr: { r: -0.45, n: 35 },
            correlation_bb_rhr: { r: 0.1, n: 30 },
        });
        expect(out.kpis).toHaveLength(3);
        expect(out.value).toBe('r = 0.72');
        expect(out.customHtml).toContain('erwartete Richtung'); // sleep→hrv positive matches
        expect(out.customHtml).toContain('unerwartete Richtung'); // bb→rhr positive ≠ expected negative
    });

    it('skips correlations with null r and falls back when none qualify', () => {
        const out = render({ correlation_sleep_hrv: { r: null } });
        expect(out.kpis).toHaveLength(0);
        expect(out.value).toBe('—');
        expect(out.recommendation).toContain('zu wenig Daten');
    });
});

describe('metrics-ml branch coverage — null-data charts + key fallbacks', () => {
    it('hr-zscore: chart tolerates a null resting_hr + z_score ?? 0 guard', () => {
        const render = ML_METRICS['hr-zscore'].render;
        const daily = [
            { date: '2026-05-01', resting_hr: 48 },
            { date: '2026-05-02', resting_hr: null }, // d.resting_hr ?? null
        ];
        expect(render([{ anomaly_hr: { z_score: 2.4, is_anomaly: true, baseline_mean: 49 } }, daily]).chart).toBeTruthy();
        // is_anomaly true but z_score null → (null ?? 0) > 2 is false → soft wording
        const soft = render([{ anomaly_hr: { z_score: null, is_anomaly: true } }, []]);
        expect(soft.recommendation).toContain('Mögliche Auffälligkeit');
    });

    it('readiness-rf: history chart tolerates a null value', () => {
        const render = ML_METRICS['readiness-rf'].render;
        const hist = {
            readiness_rf: [
                { date: '2026-05-01', value: 70 },
                { date: '2026-05-02', value: null }, // d.value ?? null
                { date: '2026-05-03', value: 72 },
                { date: '2026-05-04', value: 71 },
            ],
        };
        expect(render([{ readiness_rf: { value: 70 } }, hist]).chart).toBeTruthy();
    });

    it('hrv-status: tolerates null hrv_status (|| "") and null nightly HRV in chart', () => {
        const render = ML_METRICS['hrv-status'].render;
        const out = render([
            { date: '2026-05-01', hrv_status: 'balanced', hrv_last_night: 70 },
            { date: '2026-05-02', hrv_status: null, hrv_last_night: null }, // || '' and ?? null
        ]);
        expect(out.chart).toBeTruthy();
        expect(out.kpis.find((k) => k.label.startsWith('Ausgeglichen')).value).toBe('1 / 2 Tage');
    });

    it('training-status: empty-key fallback when status missing + TSB chart tolerates null tsb', () => {
        const render = ML_METRICS['training-status'].render;
        // (undefined || '').toUpperCase() === '' → tsMap[''] || fallback, data?.training_status ?? '—'
        expect(render([{}, {}]).value).toBe('—');
        const hist = {
            energy_physical: [
                { date: '2026-05-01', tsb: 5 },
                { date: '2026-05-02', tsb: null }, // d.tsb ?? null
                { date: '2026-05-03', tsb: 3 },
                { date: '2026-05-04', tsb: 4 },
            ],
        };
        expect(render([{ training_status: 'PRODUCTIVE', date: '2026-05-04' }, hist]).chart).toBeTruthy();
    });

    it('battery-pattern: unknown pattern uses •/raw-key fallbacks', () => {
        const render = ML_METRICS['battery-pattern'].render;
        const out = render({ battery_pattern: { pattern: 'mystery', cluster: 2, features: {} } });
        expect(out.sub).toBe('mystery'); // BP_LABELS[...] ?? bp.pattern
        expect(out.value).toContain('•'); // BP_ICONS[...] ?? '•'
    });
});
