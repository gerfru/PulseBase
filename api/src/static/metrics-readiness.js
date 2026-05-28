import { makeGradient, fmtDate, fmtHours } from './chart-utils.js';

export const READINESS_METRICS = {
    readiness: {
        title: 'Erholung',
        section: 'Erholung',
        async fetch() {
            return Promise.all([
                fetch('/api/readiness').then(r => r.json()),
                fetch('/api/energy').then(r => r.json()),
                fetch('/api/ml-history?days=90').then(r => r.json()),
            ]);
        },
        render([today, energy, history]) {
            const score = today?.score ?? null;
            const color = score == null ? '#64748b' : score >= 75 ? C.green : score >= 45 ? C.amber : C.red;

            const auton = energy.energy_autonomic;
            const cog   = energy.energy_cognitive;
            const a = auton?.score != null ? Math.round(auton.score) : null;
            const c = cog?.score   != null ? Math.round(cog.score)   : null;

            const autonHist = history.energy_autonomic || [];
            const cogHist   = history.energy_cognitive || [];
            const autonMap  = Object.fromEntries(autonHist.map(d => [d.date, d.value]));
            const cogMap    = Object.fromEntries(cogHist.map(d => [d.date, d.value]));
            const dates     = [...new Set([...Object.keys(autonMap), ...Object.keys(cogMap)])].sort();
            const compositeScores = dates.map(date => {
                const parts = [[autonMap[date], 0.60], [cogMap[date], 0.40]].filter(([v]) => v != null);
                if (!parts.length) return null;
                const tw = parts.reduce((s, [, w]) => s + w, 0);
                return Math.round(parts.reduce((s, [v, w]) => s + v * w / tw, 0));
            });

            function sparklineSvg(hist) {
                const vals = hist.map(d => d.value).filter(v => v != null);
                if (vals.length < 3) return '';
                const min = Math.min(...vals), range = Math.max(...vals) - min || 1;
                const W = 80, H = 28;
                const pts = hist.map((d, i) => {
                    if (d.value == null) return null;
                    const x = (i / Math.max(hist.length - 1, 1)) * W;
                    const y = H - ((d.value - min) / range) * (H - 4) - 2;
                    return `${x.toFixed(1)},${y.toFixed(1)}`;
                }).filter(Boolean).join(' ');
                return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            }

            function compTile(label, weight, scoreVal, detail, hist, textColor) {
                const sc = scoreVal != null ? scoreVal : '—';
                const col = scoreVal == null ? 'var(--muted)' : scoreVal >= 75 ? 'var(--green)' : scoreVal >= 45 ? 'var(--amber)' : 'var(--red)';
                const sp = sparklineSvg(hist);
                return `<div class="readiness-comp-tile card">
                    <div class="comp-header">
                        <span class="comp-label">${label}</span>
                        <span class="comp-weight">${weight}</span>
                    </div>
                    <div class="comp-score" style="color:${col}">${sc}</div>
                    <div class="comp-detail">${detail}</div>
                    ${sp ? `<div class="comp-sparkline" style="color:${textColor}">${sp}</div>` : ''}
                </div>`;
            }

            const autonDetail = auton?.deviation != null
                ? `${auton.deviation >= 0 ? '+' : ''}${auton.deviation.toFixed(2)} σ`
                : (a != null ? '' : 'keine Daten');
            const cogDetail   = cog?.debt_hours != null
                ? `${cog.debt_hours.toFixed(1)}h Schulden`
                : (c != null ? '' : 'keine Daten');

            const customHtml = `<div class="readiness-comp-grid">
                ${compTile('Autonom',  '60%', a, autonDetail, autonHist, C.green)}
                ${compTile('Kognitiv', '40%', c, cogDetail, cogHist, C.violet)}
            </div>`;

            return {
                value: score != null
                    ? `<span style="color:${color};font-size:4rem;font-weight:800;letter-spacing:-.04em">${score}</span>`
                    : '—',
                sub: today?.label ?? '',
                kpis: [],
                customHtml,
                charts: dates.length > 3 ? [{
                    title: 'Erholung-Verlauf (90 Tage)',
                    type: 'line',
                    labels: dates.map(fmtDate),
                    datasets: [
                        { label: 'Erholung', data: compositeScores, borderColor: C.indigo, backgroundColor: makeGradient(C.indigo), fill: true, tension: 0.3, pointRadius: 0 },
                        { label: 'Autonom',  data: dates.map(d => autonMap[d] ?? null), borderColor: C.amber, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0, borderDash: [4, 2] },
                        { label: 'Kognitiv', data: dates.map(d => cogMap[d]   ?? null), borderColor: C.violet, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0, borderDash: [4, 2] },
                    ],
                    scales: { y: { min: 0, max: 100 } },
                }] : [],
                formula: [
                    ['Autonome Energie (60%)',  'Score = 70 + z × 15  — Anker: z = 0 → 70 (Baseline = gut), ±1σ → 85/55 (SWC)'],
                    ['Kognitive Energie (40%)', 'Score = 100 − Schuld × 6  — Anker: 0h Schuld → 100, 5h Schuld → 70'],
                    ['Fehlende Komponenten',    'Verbleibende Gewichte werden proportional normiert'],
                    ['Composite',               'Gewichtetes Mittel (60/40), geclampt 0–100'],
                    ['TSB (Trainingsbelastung)', 'Separat im Dashboard unter "HEUTE MÖGLICH" — misst akkumulierte Last, nicht overnight-Erholung'],
                ],
                science: 'Der Erholungs-Score misst ausschließlich overnight-Physiologie — analog zu WHOOP Recovery und Garmin Body Battery. TSB (Trainingsbelastung) ist bewusst ausgeschlossen, da er akkumulierte Wochenlast misst, nicht den heutigen Erholungsstatus (Impellizzeri et al. 2020). (1) Autonome Erholungskapazität (60%): ln(RMSSD) z-Score; Score = 70 + z × 15, Konstante aus Altini & Plews (2021) — z = 0 (Baseline) = normaler Erholungsstatus, nicht mittelmäßig; ±1σ = Smallest Worthwhile Change nach Buchheit (2014). HRV ist der stärkste Einzelprädiktor für Erholungsstatus (Saw et al. 2016). (2) Kognitive Kapazität (40%): Borbély Process S, 7h-Ziel; Score = 100 − Schlafschuld × 6. Van Dongen (2003) zeigte lineare kognitive Leistungsdegradation bei chronischer Schlafeinschränkung. Die Gewichtung 60/40 reflektiert die höhere prädiktive Stärke von HRV gegenüber Schlafdauer für Erholungsqualität.',
                sources: [
                    { label: 'Plews et al. (2013): HRV Monitoring in Elite Athletes — IJSPP', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                    { label: 'Altini & Plews (2021): What Is the Correct HRV Baseline Procedure? — Sensors', url: 'https://pubmed.ncbi.nlm.nih.gov/34208059/' },
                    { label: 'Borbély (1982): Two-Process Model of Sleep Regulation — Human Neurobiology', url: 'https://pubmed.ncbi.nlm.nih.gov/7185792/' },
                    { label: 'Saw et al. (2016): Monitoring Athlete Well-Being — Sports Medicine', url: 'https://pubmed.ncbi.nlm.nih.gov/26412149/' },
                ],
                eli5: 'Der Erholungs-Score zeigt wie gut dein Körper sich über Nacht erholt hat — rein physiologisch, ohne Trainingskontext. Autonom (60%): Ist dein Nervensystem (HRV) heute besser oder schlechter als dein persönlicher Normalwert? Kognitiv (40%): Wie viel Schlafschuld hast du angehäuft? TSB (Trainingsbelastung) findest du separat unter "HEUTE MÖGLICH" im Dashboard.',
            };
        },
    },

    'hrv-recovery': {
        title: 'HRV Recovery Trajectory',
        section: 'Erholung',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=60').then(r => r.json()),
            ]);
            return { insights, history };
        },
        render(data) {
            const d = data.insights['hrv_recovery'];
            if (!d || d.recovery_speed == null) return { value: '—', sub: 'Zu wenig Trainingsereignisse', kpis: [] };
            const speed = d.recovery_speed >= 2 ? '✓ Schnell' : d.recovery_speed >= 0 ? '⚠️ Normal' : '❌ Verzögert';
            return {
                value: (d.recovery_speed >= 0 ? '+' : '') + d.recovery_speed.toFixed(1) + ' HRV/d',
                sub: speed,
                kpis: [
                    { label: 'Erholungs-Events', value: d.n_events },
                    { label: 'HRV-Baseline', value: d.hrv_baseline.toFixed(0) + ' ms' },
                    { label: 'TRIMP-Threshold', value: d.trimp_threshold.toFixed(0) },
                    { label: 'Zeitraum', value: '60 Tage' },
                ],
                formula: [
                    ['Recovery-Speed', 'Ø Δ HRV/Tag nach TRIMP-Peak (>1.5× Ø)'],
                    ['Peak-Detection', 'TRIMP > 1.5 × ⟨TRIMP_60d⟩ markiert intensives Training'],
                    ['Messfenster', '7 Tage nach Peak; valide HRV-Werte aggregiert'],
                    ['Δ HRV', 'Durchschnittliche HRV-Abweichung von Baseline in Erholungsphase'],
                    ['─── Parameter', ''],
                    ['Aus Literatur', 'Plews DL et al. (2013) HRV in Elite Athletes · Stanley J et al. (2015) HRV Recovery Speed'],
                    ['Heuristisch', 'Lookback 60d · TRIMP-Threshold ×1.5 · 7-Tage HRV-Fenster'],
                ],
                science: 'Plews et al. (2013) zeigten in 8 Elite-Ausdauersportlern: die HRV-Recovery-Speed nach intensivem Training (TRIMP > 100) ist ein stärkerer Prädiktor für Overtraining-Syndrom als absolute HRV-Werte. Die Hypothese: ein schnell erholter HRV (>+2ms/d in 7d post-training) deutet auf gute parasympathische Plastizität. Ein verzögerter oder negativer Recovery-Slope kann auf zunehmende autonome Maladaptation hindeuten (Stanley et al. 2015). Die TRIMP-Threshold-Strategie (>1.5× Ø) filtert alltägliche Aktivität und identifiziert signifikante Trainings-Reize.',
                sources: [
                    { label: 'Plews DL et al. (2013): HRV Recovery Following Interval Training — IJSPP 8(6)', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                    { label: 'Stanley J et al. (2015): Cardiac Parasympathetic Reactivation — Sports Medicine 45(9)', url: 'https://pubmed.ncbi.nlm.nih.gov/26055047/' },
                    { label: 'Buchheit M et al. (2010): Parasympathetic Reactivation in Team Sports — Int J Sports Physiol', url: 'https://pubmed.ncbi.nlm.nih.gov/21152053/' },
                ],
                eli5: 'Nach einem intensiven Training sollte sich dein Nervensystem erholen. Wenn deine HRV (Herzfrequenzvariabilität) schnell ansteigt (z.B. +2–4 ms pro Tag), bedeutet das: dein Körper aktiviert seinen Erholung-Nerv schnell. Das ist ein positives Zeichen — dein Körper adaptet gut. Wenn die HRV langsam oder gar nicht ansteigt nach schwierigem Training, könnte es sein, dass du übertrainiert bist.',
            };
        },
    },

    recovery: {
        title: 'Erholung — Schlaf & HRV',
        section: 'NACHT',
        async fetch() {
            const [hrv, sleep, insights] = await Promise.all([
                fetch('/api/hrv/trend?days=90').then(r => r.json()),
                fetch('/api/sleep?days=90').then(r => r.json()),
                fetch('/api/ml-insights').then(r => r.json()),
            ]);
            return { hrv, sleep, insights };
        },
        render(data) {
            const latestHrv   = data.hrv.at(-1);
            const sleepSorted = [...(data.sleep || [])].reverse();
            const latestSleep = sleepSorted.at(-1);
            const corr        = data.insights['correlation_sleep_hrv'];

            const hrvWeekly  = latestHrv?.hrv_weekly_avg;
            const hrvNight   = latestHrv?.hrv_last_night;
            const sleepScore = latestSleep?.sleep_score;
            const sleepDur   = latestSleep?.total_sleep_seconds;
            const deepSleep  = latestSleep?.deep_sleep_seconds;

            const validHrv   = data.hrv.filter(d => d.hrv_weekly_avg != null);
            const avg90Hrv   = validHrv.length
                ? Math.round(validHrv.reduce((s, d) => s + d.hrv_weekly_avg, 0) / validHrv.length)
                : null;
            const validSleep = sleepSorted.filter(d => d.sleep_score != null);
            const avg90Sleep = validSleep.length
                ? Math.round(validSleep.reduce((s, d) => s + d.sleep_score, 0) / validSleep.length)
                : null;

            const corrStr = corr?.r != null
                ? `r = ${corr.r.toFixed(2)} (${corr.interpretation}, n=${corr.n})`
                : 'Zu wenig Daten';
            const corrSub = corr?.p_value != null ? `p = ${corr.p_value}` : '';

            const mainParts = [];
            if (hrvWeekly != null) mainParts.push(`HRV ${hrvWeekly} ms`);
            if (sleepScore != null) mainParts.push(`Schlaf ${sleepScore}`);

            return {
                value: mainParts.join(' · ') || '—',
                sub: sleepDur ? fmtHours(sleepDur) + ' letzte Nacht' : '',
                kpis: [
                    { label: 'HRV Wochenø',     value: hrvWeekly  != null ? hrvWeekly + ' ms'    : '—' },
                    { label: 'HRV letzte Nacht', value: hrvNight   != null ? hrvNight  + ' ms'    : '—' },
                    { label: 'Ø HRV (90d)',      value: avg90Hrv   != null ? avg90Hrv  + ' ms'    : '—' },
                    { label: 'Schlaf-Score',     value: sleepScore != null ? sleepScore           : '—' },
                    { label: 'Tiefschlaf',       value: deepSleep  != null ? fmtHours(deepSleep)  : '—' },
                    { label: 'Ø Score (90d)',     value: avg90Sleep != null ? avg90Sleep           : '—' },
                    { label: 'Schlaf → HRV',     value: corrStr },
                    ...(corrSub ? [{ label: 'p-Wert', value: corrSub }] : []),
                ],
                charts: [
                    {
                        title: 'HRV-Verlauf (90 Tage)',
                        type: 'line',
                        labels: data.hrv.map(d => fmtDate(d.date)),
                        datasets: [
                            { label: 'Letzte Nacht', data: data.hrv.map(d => d.hrv_last_night ?? null), borderColor: C.green, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0, borderWidth: 2 },
                            { label: 'Wochenø',      data: data.hrv.map(d => d.hrv_weekly_avg ?? null), borderColor: '#86efac', backgroundColor: 'transparent', tension: 0.3, borderDash: [4, 4], pointRadius: 0, borderWidth: 1.5 },
                        ],
                    },
                    {
                        title: 'Schlaf-Score Verlauf (90 Tage)',
                        type: 'line',
                        labels: sleepSorted.map(d => fmtDate(d.date)),
                        datasets: [
                            { label: 'Schlaf-Score', data: sleepSorted.map(d => d.sleep_score ?? null), borderColor: C.violet, backgroundColor: makeGradient(C.violet), fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2 },
                        ],
                        scales: { y: { min: 0, max: 100 } },
                    },
                ],
                formula: [
                    ['HRV (RMSSD)', 'Root Mean Square of Successive Differences — nächtliche Messung via PPG'],
                    ['Wochenø',     'Arithmetisches Mittel der letzten 7 Nächte'],
                    ['Schlaf-Score','Garmin Composite-Score 0–100 (Dauer + Phasen + HRV während Schlaf)'],
                    ['Korrelation', 'Pearson r: Schlaf-Score(N) → HRV_letzte_Nacht(N+1), min. 10 Paare'],
                    ['Interpretation', 'r ≥ 0.7 stark · r ≥ 0.4 moderat · r ≥ 0.2 schwach'],
                ],
                science: 'HRV wird während des Schlafs gemessen — der parasympathische Vagotonus ist nachts maximal aktiv und gibt den präzisesten Erholungsmarker. Tiefschlaf (NREM-SWS) ist die Phase höchster HRV und größter physischer Regeneration: Wachstumshormon-Peak, Gewebereparatur, Glykogen-Resynthese. Die Korrelation Schlaf-Score(N) → HRV(N+1) testet, ob besserer Schlaf tatsächlich am nächsten Tag eine höhere HRV produziert — ein kausaler Pfad, der durch RCTs zu Schlafhygiene-Interventionen gestützt wird (Besedovsky et al., 2019). Plews et al. (2013) zeigten, dass nächtliche RMSSD der robusteste Einzelmarker für Erholungsstatus bei Ausdauersportlern ist.',
                sources: [
                    { label: 'Task Force ESC/NASPE (1996): HRV Standards of Measurement — Circulation', url: 'https://www.ahajournals.org/doi/10.1161/01.CIR.93.5.1043' },
                    { label: 'Plews et al. (2013): HRV in Elite Endurance Athletes — IJSPP', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                    { label: 'Besedovsky et al. (2019): Sleep and Immune Function — Pflügers Archiv', url: 'https://pubmed.ncbi.nlm.nih.gov/30689000/' },
                    { label: 'Cappuccio et al. (2011): Sleep Duration and All-Cause Mortality — Sleep', url: 'https://pubmed.ncbi.nlm.nih.gov/21300732/' },
                ],
                eli5: 'Dein Herz wird nachts vom Erholungsnerv (Parasympathikus) kontrolliert — je tiefer du schläfst, desto stärker ist dieser Nerv aktiv, desto höher ist deine HRV. Tiefschlaf ist die Phase, wo dein Körper wirklich repariert: Muskeln, Immunsystem, Energiereserven. Die Korrelation zeigt, ob bei dir persönlich guter Schlaf am nächsten Tag tatsächlich eine höhere HRV produziert — das ist dein persönlicher Schlaf-Erholungs-Zusammenhang.',
            };
        },
    },
};
