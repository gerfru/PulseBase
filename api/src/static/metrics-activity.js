import { fmtDate } from './chart-utils.js';

export const ACTIVITY_METRICS = {
    'intensity-minutes': {
        title: 'Intensitätsminuten (Karvonen)',
        section: 'Aktivität',
        async fetch() {
            return fetch('/api/ml-insights').then((r) => r.json());
        },
        render(data) {
            const d = data.intensity_minutes_custom;
            if (!d || d.moderate_minutes == null)
                return { value: '—', sub: 'Keine Aktivitätsdaten für heute', kpis: [] };
            const total = d.moderate_minutes + d.vigorous_minutes * 2;
            return {
                value: total,
                sub: `${d.moderate_minutes} min moderat · ${d.vigorous_minutes} min intensiv`,
                kpis: [
                    { label: 'Moderat (50–70% HRr)', value: `${d.moderate_minutes} min` },
                    { label: 'Intensiv (≥70% HRr)', value: `${d.vigorous_minutes} min` },
                    { label: 'Äquivalente Minuten', value: `${total} min (intensiv ×2)` },
                    { label: 'HRmax (verwendet)', value: d.hrmax_used != null ? `${d.hrmax_used} bpm` : '—' },
                ],
                formula: [
                    ['HRR (Karvonen)', 'HRr = (HR − Ruhepuls) / (HRmax − Ruhepuls)'],
                    ['Moderat', '0.50 ≤ HRr < 0.70 — jede Sekunde zählt als 1/60 Minute'],
                    ['Intensiv', 'HRr ≥ 0.70 — jede Sekunde zählt als 1/60 Minute'],
                    ['WHO-Äquivalent', 'moderat_min + intensiv_min × 2 (intensiv zählt doppelt)'],
                    ['Wochenziel WHO', '150–300 min moderat ODER 75–150 min intensiv'],
                ],
                science:
                    'Die Karvonen-Methode (Heart Rate Reserve) ist physiologisch präziser als absolute HR-Zonen, da sie Ruhepuls und maximale HR individuell berücksichtigt. Garmin verwendet für Intensitätsminuten einen festen Schwellenwert von 60% der maximalen HR — Karvonen passt sich deiner Fitness an.',
                sources: [
                    {
                        label: 'Karvonen et al. (1957): Effect of Training on Heart Rate — Ann Med Exp',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/13470504/',
                    },
                    {
                        label: 'WHO (2020): Physical Activity Guidelines',
                        url: 'https://www.who.int/publications/i/item/9789240015128',
                    },
                    {
                        label: 'ACSM Guidelines for Exercise Testing and Prescription, 11th Ed.',
                        url: 'https://www.acsm.org/education-resources/books/guidelines-exercise-testing-prescription',
                    },
                ],
                eli5: 'Garmin zählt Intensitätsminuten nach einem fixen Pulsgrenzwert — egal wie fit du bist. Karvonen berücksichtigt deinen Ruhepuls: Wenn dein Herz in Ruhe sehr langsam schlägt (gute Fitness), muss es bei gleicher Anstrengung weniger schlagen. Die Formel normalisiert das und gibt dir eine faire Einschätzung.',
                summary:
                    'Heutige Intensitätsminuten nach Karvonen-HRR-Methode — WHO-kompatibel gewichtet (intensiv × 2).',
                recommendation: (() => {
                    // total is derived from d.moderate_minutes (guaranteed by the early-return guard)
                    if (total >= 30)
                        return `${total} WHO-Äquivalent-Minuten heute — guter Beitrag zum Wochenziel (150 min).`;
                    if (total > 0)
                        return `${total} WHO-Äquivalent-Minuten. Mehr moderate oder intensive Aktivität einplanen.`;
                    return 'Heute keine Intensitätsminuten erfasst. Aktivität einplanen wenn möglich.';
                })(),
            };
        },
    },

    'training-effect': {
        title: 'Training Effect (Banister)',
        section: 'Aktivität',
        async fetch() {
            return fetch('/api/ml-insights').then((r) => r.json());
        },
        render(data) {
            const d = data.training_effect_custom;
            if (!d || d.effect == null)
                return { value: '—', sub: 'Profil (Geburtsdatum + Geschlecht) in Einstellungen eintragen', kpis: [] };
            const cls = d.effect >= 3.5 ? 'badge-balanced' : d.effect >= 2 ? 'badge-unbalanced' : 'badge-poor';
            const lbl =
                d.effect >= 4
                    ? 'Überbelastend'
                    : d.effect >= 3
                      ? 'Stark'
                      : d.effect >= 2
                        ? 'Moderat'
                        : d.effect >= 1
                          ? 'Leicht'
                          : 'Minimal';
            return {
                value: `<span class="badge ${cls}" style="font-size:3rem;padding:.2rem .8rem">${d.effect.toFixed(1)}</span>`,
                sub: `${lbl} · 0–5 Skala`,
                kpis: [
                    { label: 'Effect (0–5)', value: d.effect.toFixed(2) },
                    { label: 'TRIMP heute', value: d.trimp_today != null ? d.trimp_today.toFixed(1) : '—' },
                    { label: 'CTL (Fitness)', value: d.ctl != null ? d.ctl.toFixed(1) : '—' },
                    { label: 'VO₂max (Schätz.)', value: d.vo2max != null ? `${d.vo2max} ml/kg/min` : '—' },
                ],
                formula: [
                    ['Banister TRIMP', 'Dauer(min) × HRr × e^(b × HRr) — b = 1.92 (männlich) / 1.67 (weiblich)'],
                    ['CTL (42d EWM)', 'Fitness-Baseline: exponentiell gewichteter Mittelwert über 42 Tage'],
                    ['Training Effect', 'atan(TRIMP_heute / (CTL × 0.5)) × (10/π) → geclampt 0–5'],
                    ['VO₂max (Uth 2004)', '15 × (HRmax / HRruhepuls)'],
                    ['Geschlecht', 'Koeffizient b aus Profil — Einstellungen → Profil'],
                ],
                science:
                    'Banister TRIMP (1991) berücksichtigt im Gegensatz zu Edwards TRIMP die exponentielle HR-Intensitäts-Beziehung: Bei sehr hoher Belastung steigt der physiologische Stress überproportional. Die Koeffizienten b unterscheiden sich nach biologischem Geschlecht (Morton 1990). Der Training Effect normiert den täglichen TRIMP gegen die CTL-Baseline — eine Session hat relativ mehr Effekt bei geringer Grundfitness.',
                sources: [
                    {
                        label: 'Banister (1991): Modelling Elite Athletic Performance — Physiological Testing',
                        url: 'https://www.researchgate.net/publication/232157711',
                    },
                    {
                        label: 'Morton et al. (1990): Modeling Human Performance in Running — J Appl Physiol',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/2262449/',
                    },
                    {
                        label: 'Uth et al. (2004): Estimation of VO2max from HR — Eur J Appl Physiol',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/14624296/',
                    },
                ],
                eli5: 'Garmin zeigt dir einen Aerobic Training Effect nach einem Firstbeat-Algorithmus, den du nicht nachvollziehen kannst. Unser Wert basiert auf Banister TRIMP: Wie intensiv war das Training (Puls × Zeit), und wie viel davon verträgt dein aktuelles Fitness-Niveau (CTL)? Ein Training Effect von 3.0 bedeutet: deutliche Anpassungsreize, ohne überzubelasten.',
                summary:
                    'Trainingseffekt der letzten Einheit (0–5) basierend auf TRIMP relativ zur aktuellen CTL-Fitness.',
                recommendation: (() => {
                    const ef = d.effect; // guaranteed non-null by the early-return guard above
                    if (ef >= 4)
                        return `Training Effect ${ef.toFixed(1)} — sehr intensiv. Heute oder morgen Erholung einplanen.`;
                    if (ef >= 2.5)
                        return `Training Effect ${ef.toFixed(1)} — guter Trainingsreiz. Anpassungseffekte erwartet.`;
                    if (ef >= 1)
                        return `Training Effect ${ef.toFixed(1)} — leichter Reiz. Für Fitness-Aufbau Intensität erhöhen.`;
                    return `Training Effect ${ef.toFixed(1)} — minimaler Reiz. Training war sehr leicht.`;
                })(),
            };
        },
    },

    'training-monotony': {
        title: 'Training Monotony & Strain',
        section: 'Aktivität',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/ml-history?days=30').then((r) => r.json()),
            ]);
            return { insights, history };
        },
        render(data) {
            const d = data.insights.training_monotony;
            if (!d || d.monotony == null) return { value: '—', sub: 'Zu wenig Trainings-Daten', kpis: [] };
            const riskStr =
                d.monotony > 2.0
                    ? '⚠️ Zu monoton — Verletzungs-/Krankheitsrisiko'
                    : d.monotony > 1.5
                      ? '⚠️ Moderat'
                      : '✓ Gute Variation';
            return {
                value: d.monotony.toFixed(2),
                sub: riskStr,
                kpis: [
                    { label: 'Strain (7d)', value: d.strain.toFixed(1) },
                    { label: 'TRIMP-Ø 7d', value: d.trimp_7d_mean.toFixed(1) },
                    { label: 'σ TRIMP', value: d.trimp_7d_std.toFixed(1) },
                    { label: 'Grenzwert', value: '> 2.0 = zu monoton' },
                ],
                formula: [
                    ['Monotony', 'mean(TRIMP₇d) / σ(TRIMP₇d)'],
                    ['Strain', 'Σ(TRIMP₇d) × Monotony'],
                    ['Hohe Monotony', '< Variation im Training → Immunsystem swollen'],
                    ['Ziel', '1.0–1.5: Balance aus Konsistenz und Variation'],
                ],
                science:
                    'Foster (1998) fand in US-Schwimmern: trainingsbezogene Infekte waren um Faktor 6 höher bei hoher Monotony + hohem Strain. Die Mechanik ist wahrscheinlich Immuntoleranz (gleicher Reiz) vs. Überlastung (hohe Gesamtlast). Gute Trainingsprogramme variieren bewusst die Intensität und modality.',
                sources: [
                    {
                        label: 'Foster C (1998): Monitoring Training in Athletes — Med Sci Sports Exerc 30(7)',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/9694869/',
                    },
                    {
                        label: 'Halson SL (2014): Monitoring Training Load to Enhance Performance — Curr Opin Clin Nutr Metab Care',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/24979864/',
                    },
                ],
                eli5: 'Wenn du 7 Tage lang immer die gleiche Trainingsart mit der gleichen Intensität machst, wird dein Körper überlastet — nicht weil es zu viel ist, sondern weil die Reizvariation fehlt. Ein Schwimmer, der nur Tempotraining macht, bekommt eher Infekte als einer, der Temposchwimmen, Fondo und Sprintblöcke abwechselt.',
                summary:
                    'Zeigt ob die Trainingsbelastung der letzten 7 Tage zu monoton (gleichförmig) war — Risiko für Übertraining.',
                recommendation: (() => {
                    const mono = d.monotony; // guaranteed non-null by the early-return guard above
                    if (mono < 1.5) return `Monotonie ${mono.toFixed(2)} — gute Variation im Trainingsplan.`;
                    if (mono < 2.0)
                        return `Monotonie ${mono.toFixed(2)} — leicht erhöht. Mehr Variation zwischen harten und leichten Tagen einbauen.`;
                    return `Monotonie ${mono.toFixed(2)} — kritisch hoch (>2.0). Drastische Variation empfohlen, Infektrisiko erhöht.`;
                })(),
            };
        },
    },

    'running-economy': {
        title: 'Running Economy',
        section: 'Aktivität',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/ml-history?days=30').then((r) => r.json()),
            ]);
            return { insights, history };
        },
        render(data) {
            const d = data.insights.running_economy;
            if (!d || d.score == null) return { value: '—', sub: 'Keine Lauf-Daten mit Biomechanik', kpis: [] };
            const quality =
                d.score >= 80
                    ? '✓ Ausgezeichnet'
                    : d.score >= 60
                      ? '✓ Gut'
                      : d.score >= 40
                        ? '⚠️ Verbesserbar'
                        : '⚠️ Suboptimal';
            const hist = data.history.running_economy || [];
            return {
                value: d.score.toFixed(0),
                sub: `${quality} · Nur Laufen`,
                kpis: [
                    { label: 'GCT', value: `${d.avg_gct_ms} ms (Ziel: 200)` },
                    { label: 'VO', value: `${d.avg_vo_mm.toFixed(1)} mm (Ziel: 60)` },
                    { label: 'VR', value: `${d.avg_vr_pct.toFixed(1)}% (Ziel: 6)` },
                    { label: 'Ø der letzten', value: `${d.n_activities} Läufe` },
                ],
                chart: {
                    title: '30-Tage-Verlauf',
                    type: 'line',
                    labels: hist.map((d) => fmtDate(d.date)),
                    datasets: [
                        {
                            label: 'Running Economy',
                            data: hist.map((d) => d.value),
                            borderColor: C.blue,
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            pointRadius: 0,
                        },
                    ],
                    scales: { y: { beginAtZero: true, max: 100 } },
                },
                formula: [
                    ['Komponenten', '40% GCT + 35% VO + 25% VR'],
                    ['GCT Score', '100 − (avg_gct − 200) × 0.5'],
                    ['VO Score', '100 − (avg_vo − 60) × 2.5'],
                    ['VR Score', '100 − (avg_vr − 6) × 8.0'],
                    ['Optima', 'GCT 200ms, VO 60mm, VR 6% (Moore 2016)'],
                    ['─── Parameter', ''],
                    [
                        'Aus Literatur',
                        "Moore IS (2016) Runner's Injury Etiology · Cavanagh PE (1985) Biomechanics of Distance Running",
                    ],
                    ['Heuristisch', 'Gewichte 40/35/25% · Lineare Scoring-Funktion'],
                ],
                science:
                    'Ground Contact Time (GCT), Vertical Oscillation (VO) und Vertical Ratio (VR) sind Biomechanik-Marker aus Garmin Lauf-Dynamik. Moore (2016) et al. zeigten in 188 Läufern, dass GCT > 260ms und hohe VO mit Knieverletzungen assoziiert sind. Die Optima (200ms GCT, 60mm VO, 6% VR) basieren auf Meta-Analysen von Distanzläufern ohne Verletzungsgeschichte (Fletcher et al. 2009, Cavanagh 1985). Die Gewichtung (40/35/25) reflektiert relative Validität in der Literatur.',
                sources: [
                    {
                        label: "Moore IS et al. (2016): Runner's Injury Etiology Review — J Sports Sci 34(6):504–516",
                        url: 'https://pubmed.ncbi.nlm.nih.gov/26061909/',
                    },
                    {
                        label: 'Cavanagh PR (1985): Biomechanics of Distance Running — Human Kinetics',
                        url: 'https://scholar.google.com/scholar?q=cavanagh+1985+biomechanics+distance',
                    },
                    {
                        label: 'Fletcher JR et al. (2009): Ground Reaction Force Predictors of Injury — Sports Medicine 39(10)',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/19757861/',
                    },
                ],
                eli5: 'Beim Laufen brauchst du guten Kontakt mit dem Boden. Zu lange Bodenkontakt (>240ms) bedeutet, du drückst zu lange ab und verschwendest Energie. Zu viel Auf-und-Ab (hohes VO) belastet deine Knöchel und Knie. Ideale Werte: schneller Fuß-Kontakt, geringe vertikale Bewegung (effiziente Kraftübertragung). Dieser Score zeigt, ob dein Lauf-Stil ökonomisch ist.',
                summary:
                    'Laufökonomie-Score aus Bodenkontaktzeit + vertikaler Oszillation — verglichen mit deiner eigenen Baseline.',
                recommendation: (() => {
                    const sc = d.score; // guaranteed non-null by the early-return guard above
                    if (sc >= 75) return `Laufökonomie ${Math.round(sc)} — effizienter Laufstil. Technik beibehalten.`;
                    if (sc >= 50)
                        return `Laufökonomie ${Math.round(sc)} — durchschnittlich. Bodenkontaktzeit und vertikale Bewegung reduzieren.`;
                    return `Laufökonomie ${Math.round(sc)} — Verbesserungspotenzial. Lauftechnik-Training empfohlen.`;
                })(),
            };
        },
    },
};
