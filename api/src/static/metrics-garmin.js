import { makeGradient, fmtDate, fmtHours } from './chart-utils.js';

export const GARMIN_METRICS = {
    steps: {
        title: 'Schritte',
        section: 'Garmin-Daten',
        async fetch() {
            return fetch('/api/daily?days=90').then((r) => r.json());
        },
        render(data) {
            const valid = data.filter((d) => d.steps);
            const latest = data.at(-1);
            const avg = valid.length ? Math.round(valid.reduce((s, d) => s + d.steps, 0) / valid.length) : 0;
            const max = valid.length ? Math.max(...valid.map((d) => d.steps)) : 0;
            return {
                value: latest?.steps?.toLocaleString('de-AT') ?? '—',
                sub: '',
                kpis: [
                    { label: 'Heute', value: latest?.steps?.toLocaleString('de-AT') ?? '—' },
                    { label: 'Ø 90 Tage', value: avg ? avg.toLocaleString('de-AT') : '—' },
                    { label: 'Maximum', value: max ? max.toLocaleString('de-AT') : '—' },
                ],
                chart: {
                    title: '90-Tage-Verlauf',
                    type: 'bar',
                    labels: data.map((d) => fmtDate(d.date)),
                    datasets: [{ data: data.map((d) => d.steps || 0), backgroundColor: C.indigo, borderRadius: 3 }],
                    scales: { y: { beginAtZero: true } },
                },
                formula: [
                    ['Quelle', 'Garmin-Gerät (daily_summary.steps)'],
                    ['Methode', 'Tri-axialer Beschleunigungsmesser erkennt Schritt-Muster'],
                    ['Update', 'Täglich nach Garmin-Sync'],
                ],
                science:
                    'Tri-axiale Beschleunigungssensoren erfassen Körperbewegungen entlang drei Raumachsen. Proprietäre Step-Detection-Algorithmen identifizieren das periodische Beschleunigungsmuster des Gehens und schätzen Schrittlänge. Meta-Analysen zeigen ab 7.000–8.000 Schritten täglich eine signifikant reduzierte Gesamtmortalität in der allgemeinen Bevölkerung (Paluch et al., 2022). Die WHO empfiehlt 150–300 Minuten moderate Aktivität pro Woche; Schrittzählung ist ein populationsweiter Proxy für diese Empfehlung.',
                sources: [
                    {
                        label: 'Paluch et al. (2022): Steps per Day and All-Cause Mortality — JAMA Network Open',
                        url: 'https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2793818',
                    },
                    {
                        label: 'Tudor-Locke et al. (2011): Normative Reference Values for Steps/Day — IJBNPA',
                        url: 'https://ijbnpa.biomedcentral.com/articles/10.1186/1479-5868-8-99',
                    },
                    {
                        label: 'WHO Physical Activity Guidelines 2020',
                        url: 'https://www.who.int/publications/i/item/9789240015128',
                    },
                ],
                eli5: 'Dein Garmin zählt jeden Schritt mit einem eingebauten Bewegungssensor. Drei Achsen messen die Beschleunigung deines Körpers und erkennen das typische Auf-und-Ab-Muster beim Gehen. Das Ergebnis ist präziser als ein klassischer Schrittzähler, weil das Gerät auch Schrittlänge und Bewegungsrhythmus berücksichtigt.',
            };
        },
    },

    sleep: {
        title: 'Schlaf-Score',
        section: 'Garmin-Daten',
        async fetch() {
            return fetch('/api/sleep?days=90').then((r) => r.json());
        },
        render(data) {
            const sorted = [...data].reverse();
            const latest = sorted.at(-1);
            const valid = sorted.filter((d) => d.sleep_score != null);
            const avg = valid.length ? Math.round(valid.reduce((s, d) => s + d.sleep_score, 0) / valid.length) : null;
            const scoreDelta = valid.length >= 2 ? valid.at(-1).sleep_score - valid.at(-2).sleep_score : null;

            const bedtimes = [];
            const waketimes = [];
            sorted.forEach((d) => {
                if (!d.start_time || !d.end_time) return;
                const bedDate = new Date(d.start_time);
                bedtimes.push(bedDate.getHours() + bedDate.getMinutes() / 60);
                const wakeDate = new Date(d.end_time);
                waketimes.push(wakeDate.getHours() + wakeDate.getMinutes() / 60);
            });

            const hasRhythmData = bedtimes.length >= 7;
            const bedAvg = bedtimes.length ? bedtimes.reduce((a, b) => a + b, 0) / bedtimes.length : 0;
            const wakeAvg = waketimes.length ? waketimes.reduce((a, b) => a + b, 0) / waketimes.length : 0;
            const formatTime = (h) => `${Math.floor(h)}:${String(Math.round((h % 1) * 60)).padStart(2, '0')}`;
            const bedAvgStr = bedtimes.length ? formatTime(bedAvg) : '—';
            const wakeAvgStr = waketimes.length ? formatTime(wakeAvg) : '—';

            return {
                value: latest?.sleep_score ?? '—',
                sub: latest?.total_sleep_seconds ? `${fmtHours(latest.total_sleep_seconds)} letzte Nacht` : '',
                kpis: [
                    { label: 'Letzter Score', value: latest?.sleep_score ?? '—', delta: scoreDelta },
                    {
                        label: 'Schlafzeit',
                        value: latest?.total_sleep_seconds ? fmtHours(latest.total_sleep_seconds) : '—',
                    },
                    {
                        label: 'Tiefschlaf',
                        value: latest?.deep_sleep_seconds ? fmtHours(latest.deep_sleep_seconds) : '—',
                    },
                    { label: 'Ø Score (90d)', value: avg ?? '—' },
                    ...(hasRhythmData
                        ? [
                              { label: 'Ø Einschlafzeit', value: bedAvgStr },
                              { label: 'Ø Aufwachzeit', value: wakeAvgStr },
                          ]
                        : []),
                ],
                chart: hasRhythmData
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
                                  borderWidth: 2,
                              },
                              {
                                  label: 'Aufwachzeit',
                                  data: waketimes,
                                  borderColor: C.amber,
                                  backgroundColor: 'transparent',
                                  tension: 0.3,
                                  pointRadius: 0,
                                  borderWidth: 2,
                              },
                          ],
                          scales: {
                              y: {
                                  min: 0,
                                  max: 24,
                                  ticks: {
                                      stepSize: 2,
                                      callback: (v) =>
                                          v === 0
                                              ? '00:00'
                                              : v === 24
                                                ? '00:00'
                                                : `${String(Math.floor(v)).padStart(2, '0')}:00`,
                                  },
                              },
                          },
                      }
                    : {
                          title: 'Schlaf-Score Verlauf (90 Tage)',
                          type: 'line',
                          labels: sorted.map((d) => fmtDate(d.date)),
                          datasets: [
                              {
                                  data: sorted.map((d) => d.sleep_score ?? null),
                                  borderColor: C.violet,
                                  backgroundColor: 'transparent',
                                  tension: 0.3,
                                  pointRadius: 0,
                              },
                          ],
                          scales: { y: { min: 0, max: 100 } },
                      },
                formula: [
                    ['Quelle', 'Garmin Schlaf-Algorithmus (sleep_sessions.sleep_score, 0–100)'],
                    ['Schlafdauer', 'Gesamtschlafdauer inkl. Tiefschlaf, REM, Leichtschlaf'],
                    ['Qualität', 'Schlafphasen-Verteilung + HRV während Schlaf'],
                    ['Update', 'Einmal täglich nach Gerätesync'],
                ],
                science:
                    "Garmin's Sleep Score ist ein proprietärer Composite-Score auf Basis von Photoplethysmographie (PPG) und Aktigraphie — weniger präzise als klinische Polysomnographie (PSG), aber für longitudinales Monitoring ausreichend. Tiefschlaf (NREM-Slow-Wave-Sleep) ist primär für physische Regeneration und Wachstumshormonausschüttung relevant; REM-Schlaf für Gedächtniskonsolidierung und emotionale Verarbeitung (Walker, 2017). Epidemiologisch ist eine Schlafdauer unter 7h mit erhöhter kardiovaskulärer Mortalität assoziiert (Cappuccio et al., 2011).",
                sources: [
                    {
                        label: 'Buysse et al. (1989): Pittsburgh Sleep Quality Index (PSQI) — Psychiatry Research',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/2748771/',
                    },
                    {
                        label: 'Cappuccio et al. (2011): Sleep Duration and All-Cause Mortality — Sleep',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/21300732/',
                    },
                    {
                        label: 'Sleep Foundation: How Much Sleep Do We Really Need?',
                        url: 'https://www.sleepfoundation.org/how-sleep-works/how-much-sleep-do-we-really-need',
                    },
                ],
                eli5: 'Garmin schaut, wie lange du geschlafen hast, und bewertet die Qualität deines Schlafs. Tiefschlaf ist besonders wertvoll — dort regeneriert sich dein Körper physisch. REM-Schlaf ist wichtig fürs Gedächtnis. Viele Wachphasen oder zu wenig Tiefschlaf senken den Score. Das Ergebnis ist eine Note von 0–100.',
            };
        },
    },

    hrv: {
        title: 'HRV Wochenø',
        section: 'Garmin-Daten',
        async fetch() {
            return fetch('/api/hrv/trend?days=90').then((r) => r.json());
        },
        render(data) {
            const latest = data.at(-1);
            const validW = data.filter((d) => d.hrv_weekly_avg);
            const avg90 = validW.length
                ? Math.round(validW.reduce((s, d) => s + d.hrv_weekly_avg, 0) / validW.length)
                : null;
            const validN = data.filter((d) => d.hrv_last_night);
            const nightDelta = validN.length >= 2 ? validN.at(-1).hrv_last_night - validN.at(-2).hrv_last_night : null;
            return {
                value: latest?.hrv_weekly_avg ? `${latest.hrv_weekly_avg} ms` : '—',
                sub: latest?.hrv_last_night ? `Letzte Nacht: ${latest.hrv_last_night} ms` : '',
                kpis: [
                    { label: 'Wochenø', value: latest?.hrv_weekly_avg ? `${latest.hrv_weekly_avg} ms` : '—' },
                    {
                        label: 'Letzte Nacht',
                        value: latest?.hrv_last_night ? `${latest.hrv_last_night} ms` : '—',
                        delta: nightDelta,
                    },
                    { label: 'Ø 90 Tage', value: avg90 ? `${avg90} ms` : '—' },
                    { label: 'Status', value: latest?.hrv_status ?? '—' },
                ],
                chart: {
                    title: 'HRV-Verlauf (90 Tage)',
                    type: 'line',
                    labels: data.map((d) => fmtDate(d.date)),
                    datasets: [
                        {
                            label: 'Letzte Nacht',
                            data: data.map((d) => d.hrv_last_night),
                            borderColor: C.green,
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            pointRadius: 0,
                        },
                        {
                            label: 'Wochenø',
                            data: data.map((d) => d.hrv_weekly_avg),
                            borderColor: '#86efac',
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            borderDash: [4, 4],
                            pointRadius: 0,
                        },
                    ],
                },
                formula: [
                    ['Messgröße', 'RMSSD — Root Mean Square of Successive Differences (ms)'],
                    ['Formel', 'RMSSD = √( Σ(RRₙ₊₁ − RRₙ)² / (N−1) )'],
                    ['Wochenø', 'Arithmetisches Mittel der letzten 7 Nächte'],
                    ['Messung', 'Während Schlaf via optisches Herzfrequenzmessung'],
                ],
                science:
                    'RMSSD (Root Mean Square of Successive Differences) ist der wissenschaftlich am besten validierte Kurzzeit-HRV-Parameter für parasympathische Aktivität. Er reflektiert die kardiale vagale Modulation: hoher Vagotonus → hohe RMSSD → gute Erholung. Die European Task Force (1996) standardisierte HRV-Messparameter; nächtliche RMSSD-Werte gelten als robustester Einzelmarker für Erholungsstatus bei Athleten (Plews et al., 2013). Die logarithmische Transformation (ln RMSSD) normalisiert die rechtsschiefe Verteilung für statistische Vergleiche.',
                sources: [
                    {
                        label: 'Task Force ESC/NASPE (1996): HRV Standards of Measurement — Circulation',
                        url: 'https://www.ahajournals.org/doi/10.1161/01.CIR.93.5.1043',
                    },
                    {
                        label: 'Shaffer & Ginsberg (2017): Overview of HRV Metrics — Frontiers in Public Health',
                        url: 'https://www.frontiersin.org/articles/10.3389/fpubh.2017.00258/full',
                    },
                    {
                        label: 'Plews et al. (2013): HRV in Elite Endurance Athletes — IJSPP',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/',
                    },
                ],
                eli5: 'Dein Herz schlägt nicht perfekt gleichmäßig — zwischen je zwei Schlägen gibt es winzige Zeitunterschiede. RMSSD misst, wie groß diese Unterschiede sind. Je größer, desto aktiver arbeitet dein Erholungsnerv (Parasympathikus). Ein hoher HRV bedeutet: dein Körper ist gut erholt und kann flexibel auf Belastungen reagieren.',
            };
        },
    },

    'body-battery': {
        title: 'Body Battery',
        section: 'Garmin-Daten',
        async fetch() {
            return fetch('/api/daily?days=90').then((r) => r.json());
        },
        render(data) {
            const latest = data.at(-1);
            const valid = data.filter((d) => d.body_battery_high);
            const avgHigh = valid.length
                ? Math.round(valid.reduce((s, d) => s + d.body_battery_high, 0) / valid.length)
                : null;
            const bbDelta = valid.length >= 2 ? valid.at(-1).body_battery_high - valid.at(-2).body_battery_high : null;
            return {
                value: latest?.body_battery_high ?? '—',
                sub: latest?.body_battery_low != null ? `Tagesminimum: ${latest.body_battery_low}` : '',
                kpis: [
                    { label: 'Maximum heute', value: latest?.body_battery_high ?? '—', delta: bbDelta },
                    { label: 'Minimum heute', value: latest?.body_battery_low ?? '—' },
                    { label: 'Ø Maximum (90d)', value: avgHigh ?? '—' },
                ],
                chart: {
                    title: 'Body Battery Verlauf (90 Tage)',
                    type: 'line',
                    labels: data.map((d) => fmtDate(d.date)),
                    datasets: [
                        {
                            label: 'Maximum',
                            data: data.map((d) => d.body_battery_high),
                            borderColor: C.green,
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            pointRadius: 0,
                        },
                        {
                            label: 'Minimum',
                            data: data.map((d) => d.body_battery_low),
                            borderColor: C.orange,
                            backgroundColor: 'transparent',
                            tension: 0.3,
                            pointRadius: 0,
                        },
                    ],
                },
                formula: [
                    ['Quelle', 'Garmin Firstbeat-Algorithmus (proprietary)'],
                    ['Inputs', 'HRV, Stresslevel, Schlafqualität, Aktivitätsintensität'],
                    ['Skala', '0–100 (0 = leer, 100 = voll geladen)'],
                    ['Aufladen', 'Schlaf +++ / Entspannung + / Leichter Sport +'],
                    ['Entladen', 'Intensives Training −−− / Stress −− / Schlechter Schlaf −'],
                ],
                science:
                    'Garmin Body Battery basiert auf dem proprietären Firstbeat Analytics-Algorithmus, der HRV-basierte Stressanalyse, Schlafqualitätsbewertung und Aktivitätsintensität kontinuierlich integriert. Der Algorithmus ist nicht öffentlich peer-reviewed; das zugrundeliegende Konzept der energetischen Reserve spiegelt physiologische Prinzipien der autonomen Regulation wider. Body Battery ist als heuristischer Indikator zu verstehen — kein medizinischer Messwert und nicht unabhängig validiert.',
                sources: [
                    {
                        label: 'Firstbeat Technologies: Stress and Recovery Analysis — White Paper',
                        url: 'https://www.firstbeat.com/en/science-behind-firstbeat/',
                    },
                    {
                        label: 'Garmin Body Battery — Offizielle Erklärung',
                        url: 'https://www.garmin.com/en-US/garmin-technology/health-science/body-battery/',
                    },
                ],
                eli5: 'Stell dir einen Smartphone-Akku vor: Sport und Stress verbrauchen Energie, Schlaf und Erholung laden ihn wieder auf. Garmin berechnet das kontinuierlich aus deinem Herzrhythmus. Wenn du morgens mit 90+ aufwachst, hat die Nacht gut geladen. Wenn du nach einer intensiven Trainingswoche mit 30 aufwachst, ist eine Erholungspause fällig.',
            };
        },
    },

    'spo2-trend': {
        title: 'SpO₂ Trend & Schlafapnoe-Flag',
        section: 'Garmin-Daten',
        async fetch() {
            const [insights, daily] = await Promise.all([
                fetch('/api/ml-insights').then((r) => r.json()),
                fetch('/api/daily?days=30').then((r) => r.json()),
            ]);
            return { insights, daily };
        },
        render(data) {
            const d = data.insights.spo2_trend;
            if (!d || d.mean_spo2 == null) return { value: '—', sub: 'Keine SpO₂-Daten', kpis: [] };
            const trendIcon = d.trend === 'falling' ? '📉' : d.trend === 'rising' ? '📈' : '➡️';
            const apnea = d.apnea_flag ? '⚠️ Flag aktiv' : '✓ Normal';
            return {
                value: `${d.mean_spo2.toFixed(1)} %`,
                sub: `${trendIcon} ${d.trend} · ${apnea}`,
                kpis: [
                    { label: 'Ø SpO₂ (7d)', value: `${d.mean_spo2.toFixed(1)} %` },
                    { label: 'Min SpO₂', value: `${d.min_spo2_7d} %` },
                    {
                        label: '7d Trend',
                        value: d.slope > 0 ? `+${d.slope.toFixed(2)}` : `${d.slope.toFixed(2)} %/Tag`,
                    },
                    { label: 'Nächte <90 %', value: `${d.apnea_nights} / ${d.n_days}` },
                ],
                formula: [
                    ['SpO₂ Durchschnitt', 'mean(daily_avg_spo2) letzte 7 Nächte'],
                    ['Linear Trend', 'Steigung der SpO₂-Kurve (% pro Tag)'],
                    ['Apnoe-Flag', 'True wenn ≥ 2 Nächte mit min_spo2 < 90 %'],
                    ['Fallendes SpO₂', 'slope < −0.2 → mögl. Erkrankung oder Altitude-Effekt'],
                    ['Steigendes SpO₂', 'slope > 0.2 → Adaptierung oder Besserung'],
                ],
                science: d.apnea_flag
                    ? '<strong style="color:var(--red)">Disclaimer:</strong> Dieses Flag ist ein Hinweis, kein Befund. Obstruktive Schlafapnoe (OSA) erfordert eine Polysomnographie-Diagnose durch einen Pneumologen. Mögliche Ursachen für wiederholte nächtliche Desaturationen: OSA, Höhe, COPD, kardiale Stauung. Konsultiere deinen Arzt.'
                    : 'SpO₂ während des Schlafs reflektiert die Ventilations-Oxygenierung. Stetig fallende SpO₂ über mehrere Tage kann auf eine akute Erkrankung (Atemwegs-Infektion, Pneumonie) oder Höhenadaption hinweisen. Kapur et al. (2017) nutzen wiederholte Desaturationen < 90 % als Screening-Kriterium für OSA — erfordert aber formale Diagnose.',
                sources: [
                    {
                        label: 'Kapur VK, et al. (2017): Clinical Guidelines for Sleep Apnea Diagnosis — J Clin Sleep Med 13(3):479–504',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/28162137/',
                    },
                    {
                        label: 'Duce BR et al. (1986): Nocturnal Oxygen Desaturation in COPD — Chest 88(3):346–350',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/3698677/',
                    },
                ],
                eli5: 'Nachts sollte dein SpO₂ stabil bei 95–100 % bleiben. Wenn es regelmäßig unter 90 % fällt oder über mehrere Tage sinkt, kann das auf Schlafapnoe oder eine Erkrankung hindeuten. Das System zeigt dir den Trend — ein Arzt macht die Diagnose.',
            };
        },
    },
};
