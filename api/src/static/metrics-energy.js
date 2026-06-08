import { makeGradient, fmtDate } from './chart-utils.js';

export const ENERGY_METRICS = {
    physical: {
        title: 'Physische Energie',
        section: 'Energie',
        async fetch() {
            return Promise.all([
                fetch('/api/energy').then((r) => r.json()),
                fetch('/api/ml-history?days=90').then((r) => r.json()),
            ]);
        },
        render([energy, history]) {
            const phys = energy.energy_physical;
            const hist = history.energy_physical || [];
            const atl = phys?.atl?.toFixed(1) ?? '—';
            const ctl = phys?.ctl?.toFixed(1) ?? '—';
            const tsb = phys?.tsb != null ? (phys.tsb >= 0 ? `+${phys.tsb.toFixed(1)}` : phys.tsb.toFixed(1)) : '—';
            return {
                value: phys?.score != null ? Math.round(phys.score) : '—',
                sub: tsb !== '—' ? `TSB ${tsb}` : phys == null ? 'noch keine Daten' : '',
                kpis: [
                    { label: 'Score (0–100)', value: phys?.score != null ? Math.round(phys.score) : '—' },
                    { label: 'ATL — Erschöpfung', value: atl },
                    { label: 'CTL — Fitness', value: ctl },
                    { label: 'TSB — Balance', value: tsb },
                ],
                chart:
                    hist.length > 3
                        ? {
                              title: 'TSB / ATL / CTL Verlauf (90 Tage)',
                              type: 'line',
                              labels: hist.map((d) => fmtDate(d.date)),
                              datasets: [
                                  {
                                      label: 'CTL (Fitness)',
                                      data: hist.map((d) => d.ctl ?? null),
                                      borderColor: C.green,
                                      backgroundColor: 'transparent',
                                      tension: 0.3,
                                      pointRadius: 0,
                                  },
                                  {
                                      label: 'ATL (Erschöpfung)',
                                      data: hist.map((d) => d.atl ?? null),
                                      borderColor: C.red,
                                      backgroundColor: 'transparent',
                                      tension: 0.3,
                                      pointRadius: 0,
                                  },
                                  {
                                      label: 'TSB (Balance)',
                                      data: hist.map((d) => d.tsb ?? null),
                                      borderColor: C.indigo,
                                      backgroundColor: makeGradient(C.indigo),
                                      fill: true,
                                      tension: 0.3,
                                      pointRadius: 0,
                                  },
                              ],
                          }
                        : null,
                formula: [
                    ['HRr (Heart Rate Reserve)', 'HRr = (HR − RHR) / (HRmax − RHR)'],
                    [
                        'TRIMP (kontinuierlich)',
                        'Dauer(min) × HRr × (HRr × 4 + 1)  — kontinuierliches Polynom, nicht zonenbasiert',
                    ],
                    ['ATL (τ=7d)', 'ATLₜ = ATLₜ₋₁ × e^(−1/7) + TRIMPₜ × (1 − e^(−1/7))'],
                    ['CTL (τ=42d)', 'CTLₜ = CTLₜ₋₁ × e^(−1/42) + TRIMPₜ × (1 − e^(−1/42))'],
                    ['TSB', 'TSB = CTL − ATL  (positiv = erholt, negativ = ermüdet)'],
                    ['Score', 'Score = 72 + TSB × 1.5  (geclampt 0–100)'],
                    ['Anker TSB +10 → 87', 'Wettkampf-Taper-Zone: Busso (2003) + Friel — "Fresh zone" beginnt bei +5'],
                    ['Anker TSB −30 → 27', 'Overreaching-Schwelle: Friel / TrainingPeaks — "below −30 = injury risk"'],
                    ['Produktiver Block', 'TSB −10 bis −30 → Score 57–27 — normale, gesunde Trainingsermüdung'],
                ],
                science:
                    'Das Banister-Impuls-Antwort-Modell (1991) modelliert Fitness als Differenz zweier exponentieller Glättungsfilter: Chronic Training Load (CTL, τ = 42 Tage) approximiert langfristige Fitnessadaptation; Acute Training Load (ATL, τ = 7 Tage) modelliert kurzfristige Ermüdung. Training Stress Balance (TSB = CTL − ATL) quantifiziert den aktuellen Leistungszustand. Die Scoring-Konstante (72 statt 50) ist literaturverankert: Aus den Anker-Punkten TSB = +10 → 87 (Wettkampf-Taper, Busso 2003) und TSB = −30 → 27 (Overreaching-Schwelle, Friel/TrainingPeaks) ergibt sich über ein lineares Gleichungssystem exakt a = 72, b = 1.5. TSB = 0 ergibt damit Score 72 ("ausgeglichen ist gut"), nicht 50 ("mittelmäßig"). Die lineare Formel ist angemessen, da ATL/CTL bereits exponentielle Glättungsfilter sind — die Nicht-Linearität sitzt im Modell selbst, nicht im sekundären Score-Mapping.',
                sources: [
                    {
                        label: 'Wikipedia: Fitness–Fatigue Model (Banister 1991)',
                        url: 'https://en.wikipedia.org/wiki/Fitness%E2%80%93fatigue_model',
                    },
                    {
                        label: 'Achten & Jeukendrup (2003): Heart Rate Monitoring — Sports Medicine',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/14561293/',
                    },
                    {
                        label: 'Busso (2003): Variable Dose-Response Model — Med Sci Sports Exerc',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/12783043/',
                    },
                ],
                eli5: 'Denk an ein Sparkonto: Jedes Training hebt Geld ab (ATL = kurzfristige Erschöpfung). Regelmäßiges Training über Monate baut Zinsen auf (CTL = Fitness-Basis). TSB ist dein Kontostand: positiv = ausgeruht und fit, negativ = müde. Score 72 heißt "ausgeglichen" — das ist gut! Wer regelmäßig trainiert hat fast immer leicht negatives TSB, z.B. −15 (Score 49, gelb) — völlig normal. Problematisch wird es erst unter −30 (Score 27, rot). Vor Wettkämpfen ist ein leicht positiver TSB (+5 bis +15, Score 79–87) ideal.',
                summary:
                    'Zeigt deine Trainingsform (TSB = Fitness minus Erschöpfung). Positiv = frisch, negativ = im Trainingsblock — beides kann richtig sein.',
                recommendation: (() => {
                    const tsb = phys?.tsb ?? null;
                    if (tsb == null) return null;
                    if (tsb >= 5)
                        return 'TSB positiv — Körper ist frisch. Guter Zeitpunkt für intensive Einheit oder Wettkampf.';
                    if (tsb >= -15) return 'TSB ausgeglichen. Normales Training möglich, du bist in guter Form.';
                    if (tsb >= -30) return 'Trainingsphase — moderate Erschöpfung ist normal. Belastung wie geplant.';
                    return 'TSB sehr negativ — hohe Erschöpfung. Regeneration oder leichte Einheit empfohlen.';
                })(),
            };
        },
    },

    autonomic: {
        title: 'Autonome Energie',
        section: 'Energie',
        async fetch() {
            return Promise.all([
                fetch('/api/energy').then((r) => r.json()),
                fetch('/api/ml-history?days=90').then((r) => r.json()),
            ]);
        },
        render([energy, history]) {
            const auton = energy.energy_autonomic;
            const hist = history.energy_autonomic || [];
            const dev =
                auton?.deviation != null ? `${(auton.deviation >= 0 ? '+' : '') + auton.deviation.toFixed(2)} σ` : '—';
            const baseline =
                auton?.baseline_ln_mean != null ? `${Math.round(Math.exp(auton.baseline_ln_mean))} ms` : '—';
            return {
                value: auton?.score != null ? Math.round(auton.score) : '—',
                sub: dev !== '—' ? `${dev} vom Baseline` : auton == null ? 'noch keine Daten' : '',
                kpis: [
                    { label: 'Score (0–100)', value: auton?.score != null ? Math.round(auton.score) : '—' },
                    { label: 'Abweichung (σ = Standardabweichungen)', value: dev },
                    { label: 'Persönlicher Baseline (Ø 90 Tage)', value: baseline },
                ],
                chart:
                    hist.length > 3
                        ? {
                              title: 'HRV-Baseline Score (90 Tage)',
                              type: 'line',
                              labels: hist.map((d) => fmtDate(d.date)),
                              datasets: [
                                  {
                                      data: hist.map((d) => d.value ?? null),
                                      borderColor: C.green,
                                      backgroundColor: makeGradient(C.green),
                                      fill: true,
                                      tension: 0.3,
                                      pointRadius: 0,
                                  },
                              ],
                              scales: { y: { min: 0, max: 100 } },
                          }
                        : null,
                formula: [
                    ['Normierung', 'ln(HRV) — logarithmische Transformation für Normalverteilung'],
                    ['Baseline', 'Gleitendes Mittel μ und Stdabw σ über 90 Tage (min. 20 Messpunkte)'],
                    ['Z-Score', 'z = (ln(HRVₜ) − μ₉₀) / σ₉₀'],
                    ['Score', 'Score = 70 + z × 15  (geclampt 0–100)'],
                    [
                        'Anker z = 0 → 70',
                        'Altini & Plews (2021): Baseline-HRV = normaler Erholungsstatus — nicht mittelmäßig',
                    ],
                    [
                        'Anker z = ±1σ → 85/55',
                        'Buchheit (2014): Smallest Worthwhile Change ≈ 1σ — erst dann klinisch relevant',
                    ],
                    [
                        'Lineares Mapping nach log',
                        'ln(RMSSD) korrigiert Rechtsschiefe → σ-Raum ist gaußisch → lineares Mapping statistisch korrekt',
                    ],
                ],
                science:
                    'Absolute HRV-Werte sind interindividuell extrem variabel (RMSSD 20–100 ms normal bei Ausdauersportlern), aber intraindividuell stabil. Die ln-Transformation normalisiert die rechtsschiefe RMSSD-Verteilung — nach der Transformation ist der z-Score-Raum annähernd gaußisch, weshalb ein lineares Mapping statistisch korrekt ist (kein Sigmoid nötig). Die Score-Konstante (70 statt 50) ist literaturverankert: Altini & Plews (2021, Frontiers Physiol) zeigen, dass Baseline-HRV den Normalzustand beschreibt, nicht die Untergrenze — deshalb z = 0 → Score 70 ("In Ordnung"), nicht 50 ("Erholen"). ±1σ markiert die Smallest Worthwhile Change (Buchheit 2014) und wird auf Score 85/55 abgebildet.',
                sources: [
                    {
                        label: 'Kiviniemi et al. (2007): HRV-Guided Endurance Training — IJSPP',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/17492574/',
                    },
                    {
                        label: 'Plews et al. (2013): HRV in Elite Endurance Athletes — IJSPP',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/',
                    },
                    {
                        label: 'Buchheit (2014): Monitoring Recovery with HRV — BJSM',
                        url: 'https://bjsm.bmj.com/content/48/4/243',
                    },
                ],
                eli5: 'Wir vergleichen dein HRV nur mit DEINEM eigenen Normalwert. Score 70 = dein HRV ist genau auf deiner persönlichen Baseline — das ist gut, nicht mittelmäßig! Score 85+ = du bist heute deutlich erholter als üblich. Score 55 = leicht unter Baseline, kein Alarm. Score unter 40 = dein HRV ist ungewöhnlich niedrig, Vorsicht. Das ist aussagekräftiger als ein absoluter Wert, weil jeder Mensch seinen eigenen HRV-Normalbereich hat.',
                summary:
                    'Vergleicht deine HRV von heute Nacht mit deiner persönlichen 90-Tage-Baseline — zeigt autonomen Erholungsstatus.',
                recommendation: (() => {
                    const z = auton?.deviation ?? null;
                    if (z == null) return null;
                    if (z > 0.5) return 'HRV über Baseline — autonomes System gut erholt. Intensives Training möglich.';
                    if (z > -0.5) return 'HRV im Normalbereich. Training wie geplant.';
                    if (z > -1.5) return 'HRV leicht unter Baseline. Moderates Training, auf Signale achten.';
                    return 'HRV deutlich unter Baseline. Belastung heute reduzieren, Regeneration priorisieren.';
                })(),
            };
        },
    },

    cognitive: {
        title: 'Kognitive Energie',
        section: 'Energie',
        async fetch() {
            return Promise.all([
                fetch('/api/energy').then((r) => r.json()),
                fetch('/api/ml-history?days=90').then((r) => r.json()),
            ]);
        },
        render([energy, history]) {
            const cog = energy.energy_cognitive;
            const hist = history.energy_cognitive || [];
            return {
                value: cog?.score != null ? Math.round(cog.score) : '—',
                sub:
                    cog?.debt_hours != null
                        ? `${cog.debt_hours.toFixed(1)}h Schlafschuld`
                        : cog == null
                          ? 'noch keine Daten'
                          : '',
                kpis: [
                    { label: 'Score (0–100)', value: cog?.score != null ? Math.round(cog.score) : '—' },
                    {
                        label: 'Schlafschuld (7d)',
                        value: cog?.debt_hours != null ? `${cog.debt_hours.toFixed(1)}h` : '—',
                    },
                ],
                chart:
                    hist.length > 3
                        ? {
                              title: 'Schlafschuld Score (90 Tage)',
                              type: 'line',
                              labels: hist.map((d) => fmtDate(d.date)),
                              datasets: [
                                  {
                                      data: hist.map((d) => d.value ?? null),
                                      borderColor: C.violet,
                                      backgroundColor: makeGradient(C.violet),
                                      fill: true,
                                      tension: 0.3,
                                      pointRadius: 0,
                                  },
                              ],
                              scales: { y: { min: 0, max: 100 } },
                          }
                        : null,
                formula: [
                    ['Ziel', '7h Schlaf pro Nacht (NSF-Empfehlung Erwachsene, untere Grenze)'],
                    ['Debt/Nacht', 'max(0, 7h − tatsächlicher Schlaf)'],
                    ['Gesamt-Debt', 'Σ der letzten 7 Nächte'],
                    ['Score', 'Score = 100 − Debt × 6  (0 bei 16.7h kumulativer Schuld)'],
                ],
                science:
                    'Borbélys Zwei-Prozess-Modell (1982) ist das einflussreichste Modell der Schlafregulation: Process S (homöostatischer Schlafdruck) akkumuliert während Wachheit und dissipiert während NREM-Slow-Wave-Sleep. Chronische Schlafrestrik­tion (< 7h) akkumuliert kognitive Schulden ohne subjektives Bewusstsein: Van Dongen et al. (2003) zeigten, dass Probanden mit 6h Schlaf nach 14 Tagen kognitive Defizite auf dem Niveau von 24h totalem Schlafentzug aufwiesen. Kein Tiefschlaf-Qualitätsfaktor: Garmins Tiefschlaf-Erkennung (Akzelerometer + optisches HRV) ist zu unzuverlässig für eine rauscharme Qualitätsgewichtung — der Score basiert bewusst nur auf Schlafdauer.',
                sources: [
                    {
                        label: 'Borbély (1982): Two-Process Model of Sleep Regulation — Human Neurobiology',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/7185792/',
                    },
                    {
                        label: 'Van Dongen et al. (2003): Cumulative Sleep Restriction — Sleep',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/12683469/',
                    },
                    {
                        label: 'Sleep Foundation: How Much Sleep Do We Really Need?',
                        url: 'https://www.sleepfoundation.org/how-sleep-works/how-much-sleep-do-we-really-need',
                    },
                ],
                eli5: 'Jede Nacht mit zu wenig Schlaf packt dir Gewichte in einen unsichtbaren Rucksack. Der Rucksack macht es schwerer, klar zu denken und Entscheidungen zu treffen. Score 100 = leerer Rucksack. Score 27 heißt, du trägst ca. 10h Schlafschuld mit dir. Zwei gute Nächte hintereinander können das schon merklich verbessern.',
                summary:
                    'Bewertet kognitive Energie basierend auf der Schlafschuld der letzten 7 Nächte (Ziel: 7h/Nacht).',
                recommendation: (() => {
                    const debt = cog?.debt_hours ?? null;
                    if (debt == null) return null;
                    if (debt < 1)
                        return 'Kein wesentliches Schlafdefizit. Kognitive Leistungsfähigkeit unbeeinträchtigt.';
                    if (debt < 4)
                        return `${debt.toFixed(1)}h Schlafschuld akkumuliert. Priorität auf ausreichend Schlaf legen.`;
                    return `${debt.toFixed(1)}h Schlafschuld — deutliches Defizit. Intensive Belastung heute vermeiden.`;
                })(),
            };
        },
    },

    'body-battery-custom': {
        title: 'Body Battery (Custom)',
        section: 'Energie',
        async fetch() {
            const [insights, history, daily] = await Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/ml-history?days=30').then((r) => r.json()),
                fetch('/api/daily?days=30').then((r) => r.json()),
            ]);
            return { insights, history, daily };
        },
        render(data) {
            const d = data.insights.body_battery_custom;
            if (!d || d.score == null) return { value: '—', sub: 'Zu wenig Daten', kpis: [] };
            const color = d.score >= 75 ? '✓ Gute Energie' : d.score >= 40 ? '⚠️ Ausreichend' : '❌ Erschöpft';
            const hist = data.history.body_battery_custom || [];
            const sleepQualityPct = d.sleep_quality != null ? `${Math.round(d.sleep_quality * 100)} %` : '—';
            const hrvFactorPct = d.hrv_factor != null ? `${Math.round(d.hrv_factor * 100)} %` : '—';
            const deepStr = d.deep_h != null ? `${d.deep_h} h` : '—';
            const remStr = d.rem_h != null ? `${d.rem_h} h` : '—';
            const drainFmt = (v) => (v == null ? '—' : v === 0 ? '0' : `−${v}`);
            return {
                value: Math.round(d.score),
                sub: color,
                kpis: [
                    { label: 'Schlafqualität', value: sleepQualityPct },
                    { label: 'HRV-Faktor (vs. Baseline)', value: hrvFactorPct },
                    { label: 'Schlaf letzte Nacht', value: d.sleep_h != null ? `${d.sleep_h} h` : '—' },
                    { label: 'Tiefschlaf', value: deepStr },
                    { label: 'REM-Schlaf', value: remStr },
                    { label: 'Aktivitäts-Drain', value: drainFmt(d.activity_drain) },
                    { label: 'Stress-Drain', value: drainFmt(d.stress_drain) },
                    { label: 'Vortag', value: d.prev_score != null ? Math.round(d.prev_score) : '—' },
                ],
                chart: {
                    title: '30-Tage-Verlauf',
                    type: 'line',
                    labels: hist.map((d) => fmtDate(d.date)),
                    datasets: [
                        {
                            label: 'Custom Score',
                            data: hist.map((d) => d.value),
                            borderColor: C.amber,
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            pointRadius: 0,
                        },
                        {
                            label: 'Garmin Wert',
                            data: data.daily.map((d) => d.body_battery_high),
                            borderColor: C.muted,
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            borderDash: [4, 4],
                            pointRadius: 0,
                        },
                    ],
                    scales: { y: { beginAtZero: true, max: 100 } },
                },
                formula: [
                    ['Schlafqualität', '0.40 × (total_h / 7.5) + 0.60 × (0.55 × deep_score + 0.45 × rem_score)'],
                    ['deep_score', 'min(1, (deep_h / total_h) / 0.20)  — Ziel: 20% Tiefschlaf (Walker 2017)'],
                    ['rem_score', 'min(1, (rem_h / total_h) / 0.25)   — Ziel: 25% REM (Dijk & Czeisler 1995)'],
                    ['HRV-Faktor', 'min(1, hrv_last_night / hrv_baseline_30d)  — (Plews et al. 2013)'],
                    ['Fresh State', '40 + sleep_quality × 35 + hrv_factor × 25  (max 100 bei Idealwerten)'],
                    ['Score', '0.30 × prev + 0.70 × fresh − activity_drain − stress_drain  (clamped 5–100)'],
                    ['Aktivitäts-Drain', 'min(40, TRIMP × 0.5)'],
                    ['Stress-Drain', 'max(0, (avg_stress − 25) × 0.2)'],
                ],
                science:
                    'Das Fresh-State-Modell (v2, Mai 2026) ersetzt das frühere Banister-Akkumulationsmodell, das bei mehrtägiger Ruhe zu Plateaus bei 100 führte (Scientific Reports 2025: fundamentale statistische Mängel des FFM). Schlafphasen sind primärer Erholungsindikator: Tiefschlaf (SWS) für physische Erholung, REM für kognitive Erholung (Walker 2017; Dijk & Czeisler 1995). HRV vs. persönliche 30-Tage-Baseline als autonomer Erholungsindikator (Plews et al. 2013). Composite-Aggregation bleibt heuristisch — kein Hersteller veröffentlicht klinisch validierte Formel.',
                sources: [
                    {
                        label: 'Walker M (2017): Why We Sleep — sleep stage targets (Deep ~20%, REM ~25%)',
                        url: 'https://www.simonandschuster.com/books/Why-We-Sleep/Matthew-Walker/9781501144325',
                    },
                    {
                        label: 'Dijk DJ, Czeisler CA (1995): J Neurosci 15(5):3526–3538 — SWS/REM physiology',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/7536830/',
                    },
                    {
                        label: 'Plews DJ et al. (2013): Sports Med 43(9):773–781 — HRV vs. baseline',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23852425/',
                    },
                    {
                        label: 'Flaws in fitness-fatigue model. Sci Rep (2025)',
                        url: 'https://doi.org/10.1038/s41598-025-88153-7',
                    },
                ],
                eli5: 'Stell dir deinen Akku vor: Jeden Morgen startest du neu — basierend darauf wie gut du geschlafen hast (Tiefschlaf + REM zählen mehr als bloße Stunden) und wie erholt dein Nervensystem laut HRV ist. Training und Stress verbrauchen Energie. 30% Trägheit vom Vortag verhindert, dass der Wert täglich wild springt.',
                summary:
                    'Tagesenergie als physiologischer Snapshot: 70% aktuelle Physiologie (Schlaf + HRV), 30% Vortags-Trägheit.',
                recommendation: (() => {
                    const sc = d?.score ?? null;
                    if (sc == null) return null;
                    if (sc >= 75) return 'Gute Energie — ideal für Training oder anspruchsvolle Aufgaben.';
                    if (sc >= 45) return 'Moderate Energie. Mittelschwere Aktivität möglich, auf Signale achten.';
                    return 'Niedrige Energie. Leichte Aktivität oder bewusste Erholung empfohlen.';
                })(),
            };
        },
    },

    'stress-score-custom': {
        title: 'Stress Score (Custom)',
        section: 'Energie',
        async fetch() {
            const [insights, history, daily] = await Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/ml-history?days=30').then((r) => r.json()),
                fetch('/api/daily?days=30').then((r) => r.json()),
            ]);
            return { insights, history, daily };
        },
        render(data) {
            const d = data.insights.stress_score_custom;
            if (!d || d.score == null) return { value: '—', sub: 'HRV-Daten fehlen', kpis: [] };
            const level = d.score < 30 ? '✓ Niedrig' : d.score < 60 ? '⚠️ Mittel' : '❌ Hoch';
            const hist = data.history.stress_score_custom || [];
            const dailyByDate = {};
            (data.daily || []).forEach((day) => {
                if (day.avg_stress != null) dailyByDate[day.date] = day.avg_stress;
            });
            return {
                value: d.score.toFixed(0),
                sub: level,
                kpis: [
                    { label: 'HRV-Komponente', value: d.hrv_component.toFixed(0) },
                    { label: 'Garmin avg_stress', value: d.garmin_stress != null ? d.garmin_stress.toFixed(0) : '—' },
                    { label: 'HRV-Abweichung', value: `${d.hrv_deviation.toFixed(2)} σ` },
                    { label: 'Daten (97d)', value: `${d.n_hrv} Nächte` },
                ],
                chart: {
                    title: '30-Tage-Verlauf: unser Score (60% HRV) vs. Garmin Stress (40% Gewicht)',
                    type: 'line',
                    labels: hist.map((d) => fmtDate(d.date)),
                    datasets: [
                        {
                            label: 'Stress Score (Custom)',
                            data: hist.map((d) => d.value),
                            borderColor: C.red,
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            pointRadius: 0,
                        },
                        {
                            label: 'Garmin avg_stress',
                            data: hist.map((d) => dailyByDate[d.date] ?? null),
                            borderColor: C.muted,
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            borderDash: [4, 4],
                            pointRadius: 0,
                        },
                    ],
                    scales: { y: { beginAtZero: true, max: 100 } },
                },
                formula: [
                    ['Blending', 'Score = HRV-Komponente × 0.6 + Garmin avg_stress × 0.4'],
                    ['HRV-Component', '50 − (ln(HRV_today) − μ) / σ × 20'],
                    ['μ, σ', 'Mittel und Standardabw. von ln(HRV), letzte 97 Tage'],
                    ['Höhere HRV', '→ Niedrigerer Score (Erholung)'],
                    ['─── Parameter', ''],
                    [
                        'Aus Literatur',
                        'Task Force ESC/NASPE (1996) HRV-Standarisierung · Shaffer (2017) ln(HRV) Normalisierung',
                    ],
                    ['Heuristisch', '60/40-Blend HRV/Garmin · ×20 Skalierungsfaktor'],
                ],
                science:
                    'Die logarithmische Transformation von HRV (ln RMSSD) ist eine Standard-Normalisierungstechnik (Task Force 1996, Shaffer 2017) für nicht-Gaußsche RMSSD-Verteilungen. Z-Scores nach ln-Transformation ermöglichen Vergleiche über Zeit ohne Abhängigkeit vom absoluten Niveau. Der 60/40-Blend kombiniert parasympathische Aktivität (HRV) mit sympathischen Markernen (Garmin avg_stress) — beide widerspiegeln autonome Balance, sind aber statistisch unabhängig.',
                sources: [
                    {
                        label: 'Task Force ESC/NASPE (1996): HRV Standards — Circulation 93(5)',
                        url: 'https://www.ahajournals.org/doi/10.1161/01.CIR.93.5.1043',
                    },
                    {
                        label: 'Shaffer F, Ginsberg JP (2017): An Overview of HRV — Frontiers Pub Health',
                        url: 'https://www.frontiersin.org/articles/10.3389/fpubh.2017.00258/full',
                    },
                    {
                        label: 'Plews DL et al. (2013): Comparison of HRV Variants — IJSPP 8(6)',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/',
                    },
                ],
                eli5: 'Ein hoher Stress Score bedeutet: dein Nervensystem ist aktiviert (hohe Herzfrequenzvariabilität ist schlecht = hoher Stress). Gemessen wird das über HRV-Abweichung von deinem 97-Tage-Durchschnitt. Ein Score unter 30 = du bist entspannt. Über 60 = dein Körper ist in Kampf-oder-Flucht-Modus. Das kombiniert auch Garmins Stressmarker (sympathische Aktivität).',
                summary:
                    'Bewertet physiologischen Stress via HRV-Abweichung (60%) und Garmin-Stressdaten (40%). Niedriger Score = entspannt.',
                recommendation: (() => {
                    const sc = d?.score ?? null;
                    if (sc == null) return null;
                    if (sc < 30) return 'Niedriger Stress — guter Zustand für Belastung oder anspruchsvolle Arbeit.';
                    if (sc < 60) return 'Moderater Stress — normaler Alltag. Bei Training auf Erholung achten.';
                    return 'Hoher Stress — autonomes Nervensystem stark aktiviert. Intensives Training heute vermeiden.';
                })(),
            };
        },
    },
};
