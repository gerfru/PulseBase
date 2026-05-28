import { makeGradient, fmtDate } from './chart-utils.js';

export const SLEEP_METRICS = {
    'sleep-score-custom': {
        title: 'Schlafqualität (Custom)',
        section: 'Schlaf',
        async fetch() {
            return fetch('/api/ml-insights').then((r) => r.json());
        },
        render(data) {
            const d = data.sleep_score_custom;
            if (!d || d.score == null) return { value: '—', sub: 'Keine Schlafdaten', kpis: [] };
            const sc = Math.round(d.score);
            const cls = sc >= 75 ? 'badge-balanced' : sc >= 50 ? 'badge-unbalanced' : 'badge-poor';
            const lbl = sc >= 75 ? 'Gut' : sc >= 50 ? 'Okay' : 'Schlecht';
            return {
                value: `<span class="badge ${cls}" style="font-size:3rem;padding:.2rem .8rem">${sc}</span>`,
                sub: `${lbl} · 0–100`,
                kpis: [
                    { label: 'Schlafdauer', value: d.total_h != null ? `${d.total_h} h` : '—' },
                    { label: 'Tiefschlaf', value: d.deep_pct != null ? `${d.deep_pct} %` : '—' },
                    { label: 'REM-Schlaf', value: d.rem_pct != null ? `${d.rem_pct} %` : '—' },
                    { label: 'Wachzeit', value: d.wake_pct != null ? `${d.wake_pct} %` : '—' },
                ],
                formula: [
                    ['Tiefschlaf-Score (35%)', 'min(100, Tiefschlaf% / 20% × 100) — Optimum 20% Tiefschlaf'],
                    ['REM-Score (25%)', 'min(100, REM% / 22% × 100) — Optimum 22% REM'],
                    ['Dauer-Score (25%)', 'min(100, Stunden / 8 × 100) — Optimum 8h'],
                    ['Wach-Penalty (15%)', 'max(0, 100 − Wach% × 500) — Optimum < 0.2% Wachzeit'],
                    ['Fehlende Phasen', 'Verbleibende Gewichte werden proportional normiert'],
                ],
                science:
                    'Der Custom-Schlaf-Score gewichtet Schlafphasen nach physiologischer Relevanz. Tiefschlaf (SWS) ist für körperliche Erholung und Gedächtniskonsolidierung kritisch (Empfehlung NSF: 20%). REM-Schlaf reguliert emotionale Verarbeitung und Kreativität (Empfehlung NSF: 22%). Schlafdauer bildet die Grundlage; Wachphasen über dem Minimum wirken als Penalty.',
                sources: [
                    {
                        label: 'Walker (2017): Why We Sleep — Penguin Books',
                        url: 'https://www.amazon.de/Why-We-Sleep-Science-Dreams/dp/0141983760',
                    },
                    {
                        label: 'National Sleep Foundation: Sleep Architecture Recommendations',
                        url: 'https://www.thensf.org/sleep-faqs/what-are-sleep-stages/',
                    },
                ],
                eli5: 'Statt einfach zu sagen wie lange du geschlafen hast, schaut dieser Score auch ob du genug Tiefschlaf (körperliche Erholung) und REM-Schlaf (Träume, emotionale Verarbeitung) hattest. Ein guter Score bedeutet: die richtige Menge und die richtigen Phasen — nicht nur lange im Bett.',
            };
        },
    },

    'hrv-status-custom': {
        title: 'HRV Status (Custom)',
        section: 'Autonomic',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/ml-history?days=30').then((r) => r.json()),
            ]);
            return { insights, history };
        },
        render({ insights, history }) {
            const d = insights.hrv_status_custom;
            if (!d || d.status == null) return { value: '—', sub: 'Zu wenig HRV-Daten (min. 7 Tage)', kpis: [] };
            const cls =
                d.status === 'BALANCED' ? 'badge-balanced' : d.status === 'POOR' ? 'badge-poor' : 'badge-unbalanced';
            const devStr = d.deviation != null ? `${d.deviation >= 0 ? '+' : ''}${d.deviation.toFixed(2)}σ` : '';

            const hist = (history.hrv_status_custom || []).slice(-30);
            const statusToScore = { BALANCED: 100, UNBALANCED: 50, LOW: 25, POOR: 0 };

            return {
                value: `<span class="badge ${cls}" style="font-size:2.5rem;padding:.3rem 1rem">${d.status}</span>`,
                sub: devStr + (d.baseline_mean != null ? ` · Baseline ${d.baseline_mean.toFixed(1)} ln(ms)` : ''),
                kpis: [
                    { label: 'σ-Abweichung', value: devStr || '—' },
                    { label: 'Baseline Mean', value: d.baseline_mean != null ? d.baseline_mean.toFixed(1) : '—' },
                    { label: 'Baseline Std', value: d.baseline_std != null ? d.baseline_std.toFixed(2) : '—' },
                    { label: 'HRV 7T-Mittel (ln)', value: d.hrv_7d_mean != null ? d.hrv_7d_mean.toFixed(1) : '—' },
                ],
                chart:
                    hist.length > 3
                        ? {
                              title: 'HRV Status Verlauf (30 Tage)',
                              type: 'line',
                              labels: hist.map((h) => fmtDate(h.date)),
                              datasets: [
                                  {
                                      label: 'Status-Score',
                                      data: hist.map((h) =>
                                          h.status != null ? (statusToScore[h.status] ?? null) : null,
                                      ),
                                      borderColor: C.indigo,
                                      backgroundColor: 'transparent',
                                      tension: 0.3,
                                      pointRadius: 0,
                                  },
                              ],
                              scales: {
                                  y: {
                                      min: 0,
                                      max: 100,
                                      ticks: {
                                          callback: (v) =>
                                              ({ 100: 'BALANCED', 50: 'UNBALANCED', 25: 'LOW', 0: 'POOR' })[v] ?? '',
                                      },
                                  },
                              },
                          }
                        : null,
                formula: [
                    [
                        'Log-Transformation',
                        'ln(RMSSD) × 20 — normalisiert rechtschiefe HRV-Verteilung (Ithlete/Elite HRV)',
                    ],
                    ['Baseline', 'Rollierendes 90-Tage-Fenster: Mittelwert + Standardabweichung'],
                    ['Deviation', '(heute − baseline_mean) / baseline_std'],
                    ['BALANCED', 'Deviation ≥ −0.5σ'],
                    ['UNBALANCED', '−1.5σ ≤ Deviation < −0.5σ'],
                    ['LOW', '−2.0σ ≤ Deviation < −1.5σ'],
                    ['POOR', 'Deviation < −2.0σ'],
                ],
                science:
                    'Im Gegensatz zu Garmins proprietärem HRV-Status (Firstbeat-Algorithmus, Black Box) verwendet dieser Score eine persönliche σ-Baseline: Der heutige ln(RMSSD)-Wert wird gegen dein eigenes 90-Tage-Fenster normiert. Dadurch sind Schwellenwerte individuell statt absolut — ein HRV von 35ms kann für Person A BALANCED und für Person B LOW sein.',
                sources: [
                    {
                        label: 'Plews et al. (2013): HRV and Training Monitoring — IJSPP',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/',
                    },
                    {
                        label: 'Altini & Plews (2021): Making Sense of HRV — Frontiers',
                        url: 'https://www.frontiersin.org/articles/10.3389/fphys.2021.615561',
                    },
                    {
                        label: 'Elite HRV Score Methodology',
                        url: 'https://help.elitehrv.com/article/57-the-1-10-relative-balance-score',
                    },
                ],
                eli5: 'Garmin vergleicht deine HRV mit einer anonymen Referenzpopulation — wir vergleichen sie mit DIR. Wenn du normalerweise eine HRV von 60ms hast und heute 55ms misst, ist das für dich anders als für jemanden dessen Normal bei 40ms liegt. Dein persönlicher Normalwert ist der einzig sinnvolle Vergleichsmaßstab.',
            };
        },
    },

    'sleep-consistency': {
        title: 'Sleep Consistency Score',
        section: 'Schlaf',
        async fetch() {
            const [insights, sleep] = await Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/sleep?days=90').then((r) => r.json()),
            ]);
            return { insights, sleep };
        },
        render(data) {
            const d = data.insights.sleep_consistency;
            if (!d || d.score == null) return { value: '—', sub: 'Zu wenig Schlaf-Daten', kpis: [] };
            const quality =
                d.score >= 80
                    ? '✓ Ausgezeichnet'
                    : d.score >= 70
                      ? '✓ Gut'
                      : d.score >= 60
                        ? '⚠️ Akzeptabel'
                        : '⚠️ Schlecht';

            const sorted = [...(data.sleep || [])].reverse();
            const bedtimes = [];
            const waketimes = [];
            sorted.forEach((d) => {
                if (!d.start_time || !d.end_time) return;
                const bedDate = new Date(d.start_time);
                bedtimes.push(bedDate.getHours() + bedDate.getMinutes() / 60);
                const wakeDate = new Date(d.end_time);
                waketimes.push(wakeDate.getHours() + wakeDate.getMinutes() / 60);
            });

            return {
                value: d.score.toFixed(0),
                sub: quality,
                kpis: [
                    { label: 'σ Aufwachzeit', value: `${d.std_wake_h.toFixed(2)} h` },
                    { label: 'σ Einschlafzeit', value: `${d.std_sleep_h.toFixed(2)} h` },
                    { label: 'Nächte gemessen', value: d.n_nights },
                    { label: 'Ziel-Varianz', value: '< 30 min = Score ~90' },
                ],
                chart:
                    bedtimes.length >= 7
                        ? {
                              title: 'Schlaf-Rhythmus: Ein- & Aufwachzeiten (90 Tage)',
                              type: 'line',
                              labels: sorted.map((d) => fmtDate(d.date)),
                              datasets: [
                                  {
                                      label: 'Einschlafzeit',
                                      data: bedtimes,
                                      borderColor: C.blue,
                                      backgroundColor: makeGradient(C.blue),
                                      fill: true,
                                      tension: 0.3,
                                      pointRadius: 0,
                                      borderWidth: 2.5,
                                  },
                                  {
                                      label: 'Aufwachzeit',
                                      data: waketimes,
                                      borderColor: C.amber,
                                      backgroundColor: 'transparent',
                                      tension: 0.3,
                                      pointRadius: 0,
                                      borderWidth: 2.5,
                                  },
                              ],
                              scales: {
                                  y: {
                                      min: 0,
                                      max: 24,
                                      ticks: {
                                          stepSize: 4,
                                          callback: (v) => `${String(Math.floor(v)).padStart(2, '0')}:00`,
                                          font: { size: 12 },
                                      },
                                  },
                              },
                              options: {
                                  plugins: {
                                      legend: {
                                          display: true,
                                          position: 'top',
                                          labels: { usePointStyle: false, borderWidth: 2, padding: 15 },
                                      },
                                  },
                              },
                          }
                        : null,
                formula: [
                    ['Sleep Consistency', 'Score = 100 − (σ_wake × 15 + σ_sleep × 10)'],
                    ['σ_wake', 'Standardabw. von Aufwachzeiten (zirkulär, in Stunden)'],
                    ['σ_sleep', 'Standardabw. von Einschlafzeiten (zirkulär, in Stunden)'],
                    ['Zirkuläre Stat.', 'Berücksichtigt Wrap-around Mitternacht (23:45 ≠ 00:15)'],
                    ['Optimal', '< 30 min Varianz in beiden = Score 90+'],
                ],
                science:
                    'Phillips et al. (2017) zeigten in 500+ College-Studierenden: Individuen mit hoher Varianz in Sleep-Onset und Wake-Time hatten signifikant schlechtere akademische Leistungen und mehr psychische Symptome — unabhängig von durchschnittlicher Schlafdauer. Dies ist das „Social Jet Lag"-Phänomen (Wittmann et al., Chronobiology Int.). Der Effekt ist wahrscheinlich circadian dysregulation: dein Körper kann seine Rhythmen nicht stabil halten, was Melatonin, Cortisol und Metabolismus durcheinander bringt.',
                sources: [
                    {
                        label: 'Phillips AJ et al. (2017): Irregular Sleep Patterns and Academic Performance — Sci Rep 7:3216',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/28596593/',
                    },
                    {
                        label: 'Wittmann M et al. (2006): Social Jetlag and Obesity — Curr Biol 16(6):R187–188',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/16616641/',
                    },
                    {
                        label: 'West AC et al. (2019): Circadian Timing of Sleep — Nat Commun 10:5381',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/31772184/',
                    },
                ],
                eli5: 'Wenn du eine Nacht um 22 Uhr schlafen gehst, die nächste um 00:30, und dann wieder um 23:15, „weiß" dein Körper nicht, was los ist. Dein Hirn versucht, zirkadianen Rhythmus stabil zu halten — ständiger Jet Lag verwirrt dein Melatonin und deine Fitness-Anpassungen. Regelmäßig schlafen gehen und aufstehen (auch am Wochenende) ist einer der stärksten Hebel für Schlafqualität und Gesundheit.',
            };
        },
    },
};
