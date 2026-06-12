import { makeGradient, fmtDate } from './chart-utils.js';

export const ML_METRICS = {
    'hr-zscore': {
        title: 'Ruhepuls Z-Score',
        section: 'ML & Status',
        async fetch() {
            return Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/daily?days=90').then((r) => r.json()),
            ]);
        },
        render([ml, daily]) {
            const anomaly = ml.anomaly_hr;
            const zscore = anomaly?.z_score?.toFixed(2) ?? '—';
            const isAnom = anomaly?.is_anomaly;
            const today = daily.at(-1);
            const validRhr = daily.filter((d) => d.resting_hr);
            const rhrDelta = validRhr.length >= 2 ? validRhr.at(-1).resting_hr - validRhr.at(-2).resting_hr : null;
            return {
                value: zscore,
                sub: isAnom ? '⚠ Mögliche Auffälligkeit' : anomaly?.z_score != null ? '✓ Normal' : 'zu wenig Daten',
                kpis: [
                    { label: 'Z-Score heute (Standardabweichungen vom Ø)', value: zscore },
                    {
                        label: 'Status',
                        value: isAnom ? '⚠ Mögliche Auffälligkeit' : anomaly?.z_score != null ? '✓ Normal' : '—',
                    },
                    {
                        label: 'Baseline Ø (30 Tage)',
                        value: anomaly?.baseline_mean ? `${Math.round(anomaly.baseline_mean)} bpm` : '—',
                    },
                    {
                        label: 'Ruhepuls heute',
                        value: today?.resting_hr ? `${today.resting_hr} bpm` : '—',
                        delta: rhrDelta,
                    },
                ],
                chart: daily.some((d) => d.resting_hr)
                    ? {
                          title: 'Ruhepuls-Verlauf (90 Tage)',
                          type: 'line',
                          labels: daily.map((d) => fmtDate(d.date)),
                          datasets: [
                              {
                                  data: daily.map((d) => d.resting_hr ?? null),
                                  borderColor: C.red,
                                  backgroundColor: 'transparent',
                                  tension: 0.3,
                                  pointRadius: 0,
                              },
                          ],
                      }
                    : null,
                formula: [
                    ['Baseline', 'Gleitendes 30-Tage-Fenster (min. 7 Messpunkte erforderlich)'],
                    ['Z-Score', 'Z = (HR_heute − μ₃₀) / σ₃₀'],
                    ['Anomalie', '|Z| > 2.0 = Anomalie (≈ äußerste 5% der Normalverteilung)'],
                    ['Positiv (Z > +2)', 'Hoher Ruhepuls → Übertraining, Krankheit, Schlafmangel'],
                    ['Negativ (Z < −2)', 'Sehr tiefer Ruhepuls → Super-Erholung oder Messproblem'],
                ],
                science:
                    'Resting Heart Rate (RHR) ist ein sensitiver Biomarker des autonomen Gleichgewichts: sympathische Aktivierung durch Übertraining, Infektion oder Schlafmangel erhöht RHR messbar vor klinischen Symptomen. Die Z-Score-basierte Anomalieerkennung entstammt der statistischen Prozesskontrolle. Die |Z| > 2.0-Schwelle entspricht den äußersten ≈ 5% einer Normalverteilung (zweiseitig) und liefert bei ausreichend langem Beobachtungsfenster spezifische Anomaliemeldungen. Bidirektionale Erkennung (|Z|, nicht nur Z > 0) ist wichtig, da ein ungewöhnlich tiefer Ruhepuls ebenso auf Messartefakte oder atypische Erholung hinweisen kann.',
                sources: [
                    {
                        label: 'Buchheit (2014): Monitoring Recovery in Endurance Sports — BJSM',
                        url: 'https://bjsm.bmj.com/content/48/4/243',
                    },
                    {
                        label: 'Achten & Jeukendrup (2003): Heart Rate Monitoring — Sports Medicine',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/14561293/',
                    },
                ],
                eli5: 'Wir schauen, ob dein heutiger Ruhepuls ungewöhnlich anders ist als dein eigener Normalwert der letzten 30 Tage. Z=0 heißt: genau wie immer. Z=+2 heißt: heute 2 Standardabweichungen höher als normal. Wenn du sonst immer 44bpm hast, aber heute 52bpm, kann das ein frühes Zeichen für eine Erkältung sein — noch bevor du dich krank fühlst.',
                summary:
                    'Vergleicht deinen heutigen Ruhepuls mit deiner persönlichen 30-Tage-Baseline. Erkennt ungewöhnliche Abweichungen frühzeitig.',
                recommendation: (() => {
                    if (anomaly == null)
                        return 'Noch keine ML-Auswertung (zu wenig Daten) — der Ruhepuls-Verlauf unten zeigt solange deine Rohdaten.';
                    if (isAnom && (anomaly.z_score ?? 0) > 2)
                        return 'Ruhepuls ungewöhnlich hoch — mögliches Zeichen für Übertraining, Stress oder Erkrankung. Belastung heute reduzieren.';
                    if (isAnom) return 'Mögliche Auffälligkeit — auf körperliche Signale achten.';
                    return 'Ruhepuls im Normalbereich. Kein Anlass zur Sorge.';
                })(),
            };
        },
    },

    'readiness-rf': {
        title: 'Readiness-Prognose',
        section: 'ML & Status',
        async fetch() {
            return Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/ml-history?days=90').then((r) => r.json()),
            ]);
        },
        render([ml, history]) {
            const rf = ml.readiness_rf;
            const meta = ml.model_meta_rf;
            const hist = history.readiness_rf || [];
            const score = rf?.value != null ? Math.round(rf.value) : null;
            const ciLo = rf?.confidence_low != null ? Math.round(rf.confidence_low) : null;
            const ciHi = rf?.confidence_high != null ? Math.round(rf.confidence_high) : null;
            const cls =
                score != null ? (score >= 80 ? 'badge-balanced' : score >= 50 ? 'badge-unbalanced' : 'badge-poor') : '';
            const lbl = score != null ? (score >= 80 ? 'Gut' : score >= 50 ? 'Moderat' : 'Niedrig') : '—';
            return {
                value:
                    score != null
                        ? `<span class="badge ${cls}" style="font-size:2.5rem;padding:.2rem .8rem;letter-spacing:-.01em">${score}</span>`
                        : '—',
                sub: lbl + (score != null ? ' · Readiness (0–100)' : ''),
                kpis: [
                    { label: 'Heutiger Score', value: score ?? '—' },
                    {
                        label: 'Konfidenz (10–90%)',
                        value: ciLo != null && ciHi != null ? `${ciLo}–${ciHi}` : '—',
                    },
                    {
                        label: 'Trainingsdaten',
                        value: meta?.n_rows != null ? `${meta.n_rows} Tage` : '—',
                    },
                    { label: 'Letztes Training', value: meta?.trained_at ? fmtDate(meta.trained_at) : '—' },
                ],
                chart:
                    hist.length > 3
                        ? {
                              title: 'Prognose-Verlauf (90 Tage)',
                              type: 'line',
                              labels: hist.map((d) => fmtDate(d.date)),
                              datasets: [
                                  {
                                      data: hist.map((d) => d.value ?? null),
                                      borderColor: C.indigo,
                                      backgroundColor: makeGradient(C.indigo),
                                      fill: true,
                                      tension: 0.3,
                                      pointRadius: 0,
                                  },
                              ],
                              scales: { y: { min: 0, max: 100 } },
                          }
                        : null,
                formula: [
                    ['Modell', 'Random Forest Regressor (scikit-learn, 100 Entscheidungsbäume)'],
                    ['Features', 'hrv_last_night, sleep_score, resting_hr, aerobic_effect, anaerobic_effect'],
                    [
                        'Label',
                        'Energie-basierter Readiness-Score des Folgetages (Physical × 0.35 + Autonomic × 0.40 + Cognitive × 0.25)',
                    ],
                    ['Training', 'Wöchentlich (Sonntag 3:00 Uhr), min. 30 Datenpunkte erforderlich'],
                    ['Output', 'Prognostizierter Readiness-Score für morgen (0–100)'],
                ],
                science:
                    'Random Forests (Breiman, 2001) sind Ensemble-Lernverfahren, die aus B Bootstrap-Stichproben B dekorrelierte Entscheidungsbäume trainieren. Averaging über alle Bäume reduziert Varianz ohne Bias-Erhöhung. Das Konfidenzintervall (10./90. Perzentil der Tree-Prognosen) quantifiziert Prognose-Unsicherheit — besonders relevant bei wenigen Trainingsdaten. Das Modell lernt personalisiert: Features (HRV, Schlaf, Ruhepuls, Trainingseffekt) am Tag N sagen den energie-basierten Readiness-Score am Tag N+1 vorher.',
                sources: [
                    {
                        label: 'Breiman (2001): Random Forests — Machine Learning',
                        url: 'https://link.springer.com/article/10.1023/A:1010933404324',
                    },
                    {
                        label: 'Claudino et al. (2019): ML for Athlete Monitoring — Frontiers in Physiology',
                        url: 'https://www.frontiersin.org/articles/10.3389/fphys.2019.00337/full',
                    },
                    {
                        label: 'Saw et al. (2016): Monitoring Athlete Well-Being — Sports Medicine',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/26412149/',
                    },
                ],
                eli5: 'Ein Computerprogramm hat aus deinen Daten gelernt: "Wenn HRV hoch, Schlaf gut und Ruhepuls normal ist, dann ist diese Person morgen meistens fit." 100 Entscheidungsbäume stimmen jeweils unabhängig voneinander ab und ihr Durchschnitt ist die Prognose. Je mehr Tage das Modell beobachtet hat, desto besser kennt es deine persönlichen Muster.',
                summary:
                    'Automatisierte KI-Prognose deiner Readiness für morgen — trainiert auf deinen eigenen Daten. Informativ, kein medizinischer Befund (EU AI Act Art. 52).',
                recommendation: (() => {
                    if (score == null) return null;
                    if (score >= 75)
                        return `Prognose ${score} — gute Erholung erwartet. Intensives Training morgen möglich.`;
                    if (score >= 50)
                        return `Prognose ${score} — moderate Erholung erwartet. Normales Training morgen planbar.`;
                    return `Prognose ${score} — eingeschränkte Erholung erwartet. Morgen eher leicht trainieren.`;
                })(),
            };
        },
    },

    'hrv-status': {
        title: 'HRV-Status',
        section: 'ML & Status',
        async fetch() {
            return fetch('/api/hrv/trend?days=90').then((r) => r.json());
        },
        render(data) {
            const statusLabels = {
                balanced: 'Ausgeglichen',
                unbalanced: 'Unausgeglichen',
                low: 'Niedrig',
                poor: 'Niedrig',
            };
            const statusCls = {
                balanced: 'badge-balanced',
                unbalanced: 'badge-unbalanced',
                low: 'badge-poor',
                poor: 'badge-poor',
            };
            const latest = data.at(-1);
            const key = (latest?.hrv_status || '').toLowerCase();
            const label = statusLabels[key] ?? latest?.hrv_status ?? '—';
            const cls = statusCls[key] ?? '';
            const countBalanced = data.filter((d) => (d.hrv_status || '').toLowerCase() === 'balanced').length;
            return {
                value: cls
                    ? `<span class="badge ${cls}" style="font-size:1.8rem;padding:.2rem .7rem">${label}</span>`
                    : '—',
                sub: latest?.hrv_last_night ? `${latest.hrv_last_night} ms letzte Nacht` : '',
                kpis: [
                    { label: 'Aktueller Status', value: label },
                    { label: 'Letzte Nacht HRV', value: latest?.hrv_last_night ? `${latest.hrv_last_night} ms` : '—' },
                    {
                        label: 'Ausgeglichen (90d)',
                        value: data.length ? `${countBalanced} / ${data.length} Tage` : '—',
                    },
                ],
                chart: data.some((d) => d.hrv_last_night)
                    ? {
                          title: 'HRV letzte Nacht (90 Tage)',
                          type: 'line',
                          labels: data.map((d) => fmtDate(d.date)),
                          datasets: [
                              {
                                  label: 'HRV letzte Nacht',
                                  data: data.map((d) => d.hrv_last_night ?? null),
                                  borderColor: C.green,
                                  backgroundColor: 'transparent',
                                  tension: 0.3,
                                  pointRadius: 0,
                              },
                          ],
                      }
                    : null,
                formula: [
                    ['Quelle', 'Garmin Firstbeat-Algorithmus (hrv_daily.hrv_status)'],
                    ['Vergleich', 'HRV letzte Nacht vs. persönliche 3-Wochen-Baseline'],
                    ['BALANCED', 'HRV im Normalbereich → gute Erholung'],
                    ['UNBALANCED', 'HRV leicht außerhalb → erhöhte Belastung oder Stress'],
                    ['LOW / POOR', 'HRV deutlich unter Baseline → Überbelastung oder Erkrankung'],
                ],
                science:
                    'Garmin HRV Status basiert auf dem proprietären Firstbeat Analytics-Algorithmus, der nächtliches RMSSD mit einer rollierenden 3-Wochen-Baseline vergleicht. Die Klassifikation (BALANCED/UNBALANCED/LOW/POOR) spiegelt konzeptionell die wissenschaftliche Literatur zur HRV-gestützten Trainingsteuerung wider (Plews et al., 2013). Der Algorithmus ist nicht öffentlich peer-reviewed. Die zugrundeliegenden Prinzipien — täglicher Vergleich gegen persönlichen Baseline, Tiefenfilterung via Wochenø — sind wissenschaftlich fundiert.',
                sources: [
                    {
                        label: 'Firstbeat Technologies: HRV-Based Recovery Analysis',
                        url: 'https://www.firstbeat.com/en/science-behind-firstbeat/',
                    },
                    {
                        label: 'Plews et al. (2013): HRV in Elite Endurance Athletes — IJSPP',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/',
                    },
                    {
                        label: 'Task Force ESC/NASPE (1996): HRV Standards — Circulation',
                        url: 'https://www.ahajournals.org/doi/10.1161/01.CIR.93.5.1043',
                    },
                ],
                eli5: 'Garmin schaut jeden Morgen auf dein HRV und vergleicht es mit deinem persönlichen Normalwert der letzten 3 Wochen. "Ausgeglichen" heißt: alles normal, gut erholt. "Unausgeglichen" heißt: etwas stimmt nicht ganz. "Niedrig" ist ein klares Signal: heute solltest du regenerieren, nicht intensiv trainieren.',
                summary:
                    'Garmins HRV-Statusklassifikation (Firstbeat): vergleicht heutige HRV mit persönlicher 3-Wochen-Baseline.',
                recommendation: (() => {
                    const k = (latest?.hrv_status || '').toLowerCase();
                    if (k === 'balanced') return 'HRV ausgeglichen — gut erholt. Volles Training möglich.';
                    if (k === 'unbalanced')
                        return 'HRV leicht außerhalb des Normalbereichs. Moderate Belastung empfohlen.';
                    if (k === 'low' || k === 'poor')
                        return 'HRV deutlich unter Baseline. Heute regenerieren statt intensiv trainieren.';
                    return null;
                })(),
            };
        },
    },

    'training-status': {
        title: 'Trainingszustand',
        section: 'ML & Status',
        async fetch() {
            return Promise.all([
                fetch('/api/training-status').then((r) => r.json()),
                fetch('/api/ml-history?days=90').then((r) => r.json()),
            ]);
        },
        render([data, history]) {
            const tsMap = {
                PRODUCTIVE: {
                    label: 'Aufbauend',
                    cls: 'badge-balanced',
                    desc: 'Dein Training ist effektiv — du wirst gerade fitter.',
                },
                MAINTAINING: {
                    label: 'Erhalt',
                    cls: 'badge-balanced',
                    desc: 'Du hältst dein aktuelles Fitnesslevel stabil.',
                },
                RECOVERY: {
                    label: 'Erholung',
                    cls: 'badge-unbalanced',
                    desc: 'Dein Körper erholt sich nach hoher Belastung.',
                },
                UNPRODUCTIVE: {
                    label: 'Nicht produktiv',
                    cls: 'badge-unbalanced',
                    desc: 'Zu wenig oder zu viel Training für Fortschritte.',
                },
                OVERREACHING: {
                    label: 'Übertraining',
                    cls: 'badge-poor',
                    desc: 'Zu hohe Belastung — Erholung dringend empfohlen.',
                },
                DETRAINING: { label: 'Abfall', cls: 'badge-poor', desc: 'Zu wenig Aktivität — Fitness nimmt ab.' },
            };
            const key = (data?.training_status || '').toUpperCase();
            const entry = tsMap[key] || { label: data?.training_status ?? '—', cls: '', desc: '' };
            return {
                value: entry.cls
                    ? `<span class="badge ${entry.cls}" style="font-size:1.8rem;padding:.2rem .7rem">${entry.label}</span>`
                    : '—',
                sub: data?.date ? `Stand ${fmtDate(data.date)}` : '',
                kpis: [
                    { label: 'Status', value: entry.label },
                    { label: 'Bedeutung', value: entry.desc || '—' },
                ],
                chart: (() => {
                    const physHist = history.energy_physical || [];
                    return physHist.length > 3
                        ? {
                              title: 'Training Stress Balance — TSB (90 Tage)',
                              type: 'line',
                              labels: physHist.map((d) => fmtDate(d.date)),
                              datasets: [
                                  {
                                      label: 'TSB',
                                      data: physHist.map((d) => d.tsb ?? null),
                                      borderColor: C.indigo,
                                      backgroundColor: makeGradient(C.indigo),
                                      fill: true,
                                      tension: 0.3,
                                      pointRadius: 0,
                                  },
                              ],
                          }
                        : null;
                })(),
                formula: [
                    ['Quelle', 'Garmin Firstbeat-Algorithmus (daily_summary.training_status)'],
                    ['Inputs', 'Trainingsbelastung letzte Wochen, VO₂max-Schätzung, Erholungsstatus'],
                    ['PRODUCTIVE', 'Belastung erhöht VO₂max → Fitness wächst'],
                    ['MAINTAINING', 'Belastung hält aktuelles Level stabil'],
                    ['RECOVERY', 'Bewusste Entlastungsphase nach hoher Belastung'],
                    ['OVERREACHING', 'Chronische Überbelastung — Verletzungsrisiko steigt'],
                ],
                science:
                    'Garmin Training Status integriert VO₂max-Schätzung via submaximaler Laufanalyse (Firstbeat-Algorithmus) mit Trainingsbelastungsperiodisierung. Die Klassifikation modelliert das Prinzip der Superkompensation: ausreichende Belastung + Erholung → PRODUCTIVE; chronische Überbelastung ohne ausreichende Erholung → OVERREACHING (Meeusen et al., 2013). Wie Body Battery ist dieser Wert ein proprietäres Firstbeat-Modell ohne externe Peer-Review-Validierung — als Orientierung, nicht als klinische Diagnose zu interpretieren.',
                sources: [
                    {
                        label: 'Firstbeat Technologies: Training Status Overview',
                        url: 'https://www.firstbeat.com/en/science-behind-firstbeat/training-effect/',
                    },
                    {
                        label: 'Meeusen et al. (2013): Overtraining Syndrome Consensus — Med Sci Sports Exerc',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23247672/',
                    },
                ],
                eli5: 'Garmin analysiert deine Trainingsbelastung der letzten Wochen und vergleicht sie mit deiner geschätzten Fitness. "Aufbauend" bedeutet: du machst es perfekt, du wirst gerade stärker. "Übertraining" ist ein rotes Licht — dein Körper kann die Belastung nicht mehr sinnvoll verarbeiten. Dann hilft mehr Training nicht mehr, sondern schadet.',
                summary:
                    'Garmins Bewertung ob dein Training gerade aufbauend, erhaltend oder überbelastend ist — basierend auf Firstbeat-Analyse.',
                recommendation: (() => {
                    const k = (data?.training_status || '').toUpperCase();
                    if (k === 'PRODUCTIVE') return 'Training wirkt aufbauend — weiter so. Belastung stabil halten.';
                    if (k === 'MAINTAINING')
                        return 'Fitnesslevel wird gehalten. Für Steigerung Umfang oder Intensität leicht erhöhen.';
                    if (k === 'RECOVERY') return 'Erholungsphase — Belastung bewusst reduziert halten.';
                    if (k === 'OVERREACHING')
                        return 'Übertraining erkannt — Erholung priorisieren, Umfang deutlich reduzieren.';
                    if (k === 'DETRAINING')
                        return 'Zu wenig Aktivität — Fitness nimmt ab. Regelmäßige Einheiten einplanen.';
                    return null;
                })(),
            };
        },
    },

    'battery-pattern': {
        title: 'Body Battery Muster',
        section: 'ML & Status',
        async fetch() {
            return fetch('/api/ml-insights').then((r) => r.json());
        },
        render(ml) {
            const bp = ml.battery_pattern;
            if (!bp?.pattern)
                return {
                    value: '—',
                    sub: 'zu wenig Daten',
                    recommendation:
                        'Noch keine ML-Auswertung (zu wenig Daten) — der Body-Battery-Verlauf im Dashboard zeigt solange deine Rohdaten.',
                };

            const BP_LABELS = {
                stabil_hoch: 'Hohe & stabile Energie',
                erholung: 'Erholung',
                erschoepft: 'Erschöpft / hohe Belastung',
            };
            const BP_ICONS = { stabil_hoch: '⚡', erholung: '🔄', erschoepft: '📉' };
            const feat = bp.features || {};

            return {
                value: `<span style="font-size:2.5rem">${BP_ICONS[bp.pattern] ?? '•'}</span>`,
                sub: BP_LABELS[bp.pattern] ?? bp.pattern,
                kpis: [
                    { label: 'Muster', value: BP_LABELS[bp.pattern] ?? bp.pattern },
                    { label: 'Cluster', value: String(bp.cluster ?? '—') },
                    { label: 'Morgen (06–09h)', value: feat.morning_avg?.toFixed(1) ?? '—' },
                    { label: 'Abend (20–23h)', value: feat.evening_avg?.toFixed(1) ?? '—' },
                    { label: 'Tagesreichweite', value: feat.daily_range?.toFixed(1) ?? '—' },
                    { label: 'Ø Niveau (AUC)', value: feat.auc?.toFixed(1) ?? '—' },
                    { label: 'Einbrüche', value: String(feat.n_dips ?? '—') },
                ],
                eli5: 'Deine Body Battery zeigt über den Tag, wie viel Energie du hast. Das System schaut sich 5 Kennzahlen an (Morgen-Start, Abend-End, Schwankungsbreite, Gesamtniveau, Einbrüche) und ordnet deinen Tag einem von 3 Mustern zu: ⚡ Hohe Energie, 🔄 Erholung, oder 📉 Erschöpft.',
                summary:
                    'k-Means Klassifikation deines Body-Battery-Kurventyps — beschreibt das Verlaufsmuster der letzten Wochen, nicht nur heute.',
                recommendation:
                    bp.pattern === 'stabil_hoch'
                        ? 'Stabiles Energiemuster — Training wie geplant.'
                        : bp.pattern === 'erholung'
                          ? 'Erholungsmuster erkannt — Energie steigt typischerweise über den Tag.'
                          : 'Erschöpftes Muster in letzter Zeit — längerfristige Belastung reduzieren erwägen.',
                formula: [
                    ['Modell', 'k-Means Clustering auf 5 Body-Battery-Features'],
                    ['Features', 'morning_avg, evening_avg, daily_range, auc, n_dips'],
                    ['Cluster', 'Stabil Hoch / Erholung / Erschöpft (k=3)'],
                ],
            };
        },
    },

    correlations: {
        title: 'Korrelationen',
        section: 'ML & Status',
        async fetch() {
            return fetch('/api/ml-insights').then((r) => r.json());
        },
        render(ml) {
            const CORR_META = {
                correlation_sleep_hrv: {
                    label: 'Schlaf → HRV (nächster Tag)',
                    desc: 'Besserer Schlaf geht typischerweise mit höherer HRV am nächsten Morgen einher.',
                    expected: 'positiv',
                },
                correlation_sleep_rhr: {
                    label: 'Schlaf → Ruhepuls (nächster Tag)',
                    desc: 'Schlechter Schlaf erhöht typischerweise den Ruhepuls am Folgetag.',
                    expected: 'negativ',
                },
                correlation_bb_rhr: {
                    label: 'Body Battery → Ruhepuls (nächster Tag)',
                    desc: 'Hohe Body Battery korreliert mit niedrigerem Ruhepuls am nächsten Tag.',
                    expected: 'negativ',
                },
            };
            const kpis = [];
            const corrItems = [];
            for (const [key, meta] of Object.entries(CORR_META)) {
                const corr = ml[key];
                if (!corr || corr.r == null) continue;
                const absR = Math.abs(corr.r);
                const dir = corr.r >= 0 ? 'positiv' : 'negativ';
                const strength = absR >= 0.6 ? 'starker' : absR >= 0.3 ? 'moderater' : 'schwacher';
                const barColor = corr.r >= 0 ? 'rgba(99,102,241,.75)' : 'rgba(245,158,11,.75)';
                const dirMatch = dir === meta.expected;
                kpis.push({ label: meta.label, value: `r = ${corr.r.toFixed(2)}` });
                corrItems.push(`<div class="corr-row">
                    <div class="corr-label">${meta.label}</div>
                    <div class="corr-bar-wrap"><div class="corr-bar" style="width:${absR * 100}%;background:${barColor}"></div></div>
                    <div class="corr-r">r = ${corr.r.toFixed(2)}</div>
                    <div class="corr-meta">${strength} ${dir}er Zusammenhang · n = ${corr.n} Nächte · ${dirMatch ? '✓ erwartete Richtung' : '↔ unerwartete Richtung'}</div>
                    <div class="corr-desc">${meta.desc}</div>
                </div>`);
            }
            return {
                value: kpis.length ? kpis[0].value : '—',
                sub: kpis.length ? 'Schlaf → HRV' : 'zu wenig Daten',
                kpis,
                customHtml: corrItems.length ? `<div class="card">${corrItems.join('')}</div>` : '',
                eli5: 'r misst, ob zwei Dinge zusammenhängen — auf einer Skala von −1 bis +1. r = +1 heißt: wenn A steigt, steigt B immer. r = −1 heißt: wenn A steigt, fällt B immer. r = 0 heißt: kein Zusammenhang. Wichtig: Zusammenhang bedeutet nicht Ursache.',
                summary:
                    'Zeigt statistische Zusammenhänge zwischen deinen Schlaf-, HRV- und Body-Battery-Werten über 90 Tage (Pearson r).',
                recommendation: kpis.length
                    ? null
                    : 'Noch zu wenig Daten für Korrelationsanalyse (min. 10 Paare). Nutze solange die Schlaf- und HRV-Charts im Dashboard.',
                formula: [
                    ['r-Wert', 'Pearson-Korrelationskoeffizient (−1 bis +1)'],
                    ['|r| > 0,6', 'Starker Zusammenhang'],
                    ['|r| 0,3–0,6', 'Moderater Zusammenhang'],
                    ['|r| < 0,3', 'Schwacher oder kein Zusammenhang'],
                    ['Minimum', 'Min. 10 Paare erforderlich'],
                ],
            };
        },
    },
};
