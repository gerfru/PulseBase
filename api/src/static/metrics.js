const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
Chart.defaults.borderColor = isDark ? 'rgba(51,65,85,.6)' : 'rgba(226,232,240,.8)';

function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso.length === 10 ? iso + 'T12:00:00' : iso);
    return d.toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit' });
}
function fmtHours(seconds) {
    if (!seconds) return '—';
    const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

const METRICS = {
    steps: {
        title: 'Schritte',
        section: 'Garmin-Daten',
        async fetch() { return fetch('/api/daily?days=90').then(r => r.json()); },
        render(data) {
            const valid = data.filter(d => d.steps);
            const latest = data.at(-1);
            const avg = valid.length ? Math.round(valid.reduce((s, d) => s + d.steps, 0) / valid.length) : 0;
            const max = valid.length ? Math.max(...valid.map(d => d.steps)) : 0;
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
                    labels: data.map(d => fmtDate(d.date)),
                    datasets: [{ data: data.map(d => d.steps || 0), backgroundColor: '#6366f1', borderRadius: 3 }],
                    scales: { y: { beginAtZero: true } },
                },
                formula: [
                    ['Quelle', 'Garmin-Gerät (daily_summary.steps)'],
                    ['Methode', 'Tri-axialer Beschleunigungsmesser erkennt Schritt-Muster'],
                    ['Update', 'Täglich nach Garmin-Sync'],
                ],
                science: 'Tri-axiale Beschleunigungssensoren erfassen Körperbewegungen entlang drei Raumachsen. Proprietäre Step-Detection-Algorithmen identifizieren das periodische Beschleunigungsmuster des Gehens und schätzen Schrittlänge. Meta-Analysen zeigen ab 7.000–8.000 Schritten täglich eine signifikant reduzierte Gesamtmortalität in der allgemeinen Bevölkerung (Paluch et al., 2022). Die WHO empfiehlt 150–300 Minuten moderate Aktivität pro Woche; Schrittzählung ist ein populationsweiter Proxy für diese Empfehlung.',
                sources: [
                    { label: 'Paluch et al. (2022): Steps per Day and All-Cause Mortality — JAMA Network Open', url: 'https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2793818' },
                    { label: 'Tudor-Locke et al. (2011): Normative Reference Values for Steps/Day — IJBNPA', url: 'https://ijbnpa.biomedcentral.com/articles/10.1186/1479-5868-8-99' },
                    { label: 'WHO Physical Activity Guidelines 2020', url: 'https://www.who.int/publications/i/item/9789240015128' },
                ],
                eli5: 'Dein Garmin zählt jeden Schritt mit einem eingebauten Bewegungssensor. Drei Achsen messen die Beschleunigung deines Körpers und erkennen das typische Auf-und-Ab-Muster beim Gehen. Das Ergebnis ist präziser als ein klassischer Schrittzähler, weil das Gerät auch Schrittlänge und Bewegungsrhythmus berücksichtigt.',
            };
        },
    },

    sleep: {
        title: 'Schlaf-Score',
        section: 'Garmin-Daten',
        async fetch() { return fetch('/api/sleep?days=90').then(r => r.json()); },
        render(data) {
            const sorted = [...data].reverse();
            const latest = sorted.at(-1);
            const valid = sorted.filter(d => d.sleep_score != null);
            const avg = valid.length ? Math.round(valid.reduce((s, d) => s + d.sleep_score, 0) / valid.length) : null;
            return {
                value: latest?.sleep_score ?? '—',
                sub: latest?.total_sleep_seconds ? fmtHours(latest.total_sleep_seconds) + ' letzte Nacht' : '',
                kpis: [
                    { label: 'Letzter Score', value: latest?.sleep_score ?? '—' },
                    { label: 'Schlafzeit', value: latest?.total_sleep_seconds ? fmtHours(latest.total_sleep_seconds) : '—' },
                    { label: 'Tiefschlaf', value: latest?.deep_sleep_seconds ? fmtHours(latest.deep_sleep_seconds) : '—' },
                    { label: 'Ø Score (90d)', value: avg ?? '—' },
                ],
                chart: {
                    title: 'Schlaf-Score Verlauf (90 Tage)',
                    type: 'line',
                    labels: sorted.map(d => fmtDate(d.date)),
                    datasets: [{ data: sorted.map(d => d.sleep_score ?? null), borderColor: '#8b5cf6', backgroundColor: 'transparent', tension: 0.3, pointRadius: 3 }],
                    scales: { y: { min: 0, max: 100 } },
                },
                formula: [
                    ['Quelle', 'Garmin Schlaf-Algorithmus (sleep_sessions.sleep_score, 0–100)'],
                    ['Schlafdauer', 'Gesamtschlafdauer inkl. Tiefschlaf, REM, Leichtschlaf'],
                    ['Qualität', 'Schlafphasen-Verteilung + HRV während Schlaf'],
                    ['Update', 'Einmal täglich nach Gerätesync'],
                ],
                science: 'Garmin\'s Sleep Score ist ein proprietärer Composite-Score auf Basis von Photoplethysmographie (PPG) und Aktigraphie — weniger präzise als klinische Polysomnographie (PSG), aber für longitudinales Monitoring ausreichend. Tiefschlaf (NREM-Slow-Wave-Sleep) ist primär für physische Regeneration und Wachstumshormonausschüttung relevant; REM-Schlaf für Gedächtniskonsolidierung und emotionale Verarbeitung (Walker, 2017). Epidemiologisch ist eine Schlafdauer unter 7h mit erhöhter kardiovaskulärer Mortalität assoziiert (Cappuccio et al., 2011).',
                sources: [
                    { label: 'Buysse et al. (1989): Pittsburgh Sleep Quality Index (PSQI) — Psychiatry Research', url: 'https://pubmed.ncbi.nlm.nih.gov/2748771/' },
                    { label: 'Cappuccio et al. (2011): Sleep Duration and All-Cause Mortality — Sleep', url: 'https://pubmed.ncbi.nlm.nih.gov/21300732/' },
                    { label: 'Sleep Foundation: How Much Sleep Do We Really Need?', url: 'https://www.sleepfoundation.org/how-sleep-works/how-much-sleep-do-we-really-need' },
                ],
                eli5: 'Garmin schaut, wie lange du geschlafen hast, und bewertet die Qualität deines Schlafs. Tiefschlaf ist besonders wertvoll — dort regeneriert sich dein Körper physisch. REM-Schlaf ist wichtig fürs Gedächtnis. Viele Wachphasen oder zu wenig Tiefschlaf senken den Score. Das Ergebnis ist eine Note von 0–100.',
            };
        },
    },

    hrv: {
        title: 'HRV Wochenø',
        section: 'Garmin-Daten',
        async fetch() { return fetch('/api/hrv/trend?days=90').then(r => r.json()); },
        render(data) {
            const latest = data.at(-1);
            const validW = data.filter(d => d.hrv_weekly_avg);
            const avg90 = validW.length ? Math.round(validW.reduce((s, d) => s + d.hrv_weekly_avg, 0) / validW.length) : null;
            return {
                value: latest?.hrv_weekly_avg ? latest.hrv_weekly_avg + ' ms' : '—',
                sub: latest?.hrv_last_night ? 'Letzte Nacht: ' + latest.hrv_last_night + ' ms' : '',
                kpis: [
                    { label: 'Wochenø', value: latest?.hrv_weekly_avg ? latest.hrv_weekly_avg + ' ms' : '—' },
                    { label: 'Letzte Nacht', value: latest?.hrv_last_night ? latest.hrv_last_night + ' ms' : '—' },
                    { label: 'Ø 90 Tage', value: avg90 ? avg90 + ' ms' : '—' },
                    { label: 'Status', value: latest?.hrv_status ?? '—' },
                ],
                chart: {
                    title: 'HRV-Verlauf (90 Tage)',
                    type: 'line',
                    labels: data.map(d => fmtDate(d.date)),
                    datasets: [
                        { label: 'Letzte Nacht', data: data.map(d => d.hrv_last_night), borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
                        { label: 'Wochenø', data: data.map(d => d.hrv_weekly_avg), borderColor: '#86efac', backgroundColor: 'transparent', tension: 0.3, borderDash: [4, 4], pointRadius: 0 },
                    ],
                },
                formula: [
                    ['Messgröße', 'RMSSD — Root Mean Square of Successive Differences (ms)'],
                    ['Formel', 'RMSSD = √( Σ(RRₙ₊₁ − RRₙ)² / (N−1) )'],
                    ['Wochenø', 'Arithmetisches Mittel der letzten 7 Nächte'],
                    ['Messung', 'Während Schlaf via optisches Herzfrequenzmessung'],
                ],
                science: 'RMSSD (Root Mean Square of Successive Differences) ist der wissenschaftlich am besten validierte Kurzzeit-HRV-Parameter für parasympathische Aktivität. Er reflektiert die kardiale vagale Modulation: hoher Vagotonus → hohe RMSSD → gute Erholung. Die European Task Force (1996) standardisierte HRV-Messparameter; nächtliche RMSSD-Werte gelten als robustester Einzelmarker für Erholungsstatus bei Athleten (Plews et al., 2013). Die logarithmische Transformation (ln RMSSD) normalisiert die rechtsschiefe Verteilung für statistische Vergleiche.',
                sources: [
                    { label: 'Task Force ESC/NASPE (1996): HRV Standards of Measurement — Circulation', url: 'https://www.ahajournals.org/doi/10.1161/01.CIR.93.5.1043' },
                    { label: 'Shaffer & Ginsberg (2017): Overview of HRV Metrics — Frontiers in Public Health', url: 'https://www.frontiersin.org/articles/10.3389/fpubh.2017.00258/full' },
                    { label: 'Plews et al. (2013): HRV in Elite Endurance Athletes — IJSPP', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                ],
                eli5: 'Dein Herz schlägt nicht perfekt gleichmäßig — zwischen je zwei Schlägen gibt es winzige Zeitunterschiede. RMSSD misst, wie groß diese Unterschiede sind. Je größer, desto aktiver arbeitet dein Erholungsnerv (Parasympathikus). Ein hoher HRV bedeutet: dein Körper ist gut erholt und kann flexibel auf Belastungen reagieren.',
            };
        },
    },

    'body-battery': {
        title: 'Body Battery',
        section: 'Garmin-Daten',
        async fetch() { return fetch('/api/daily?days=90').then(r => r.json()); },
        render(data) {
            const latest = data.at(-1);
            const valid = data.filter(d => d.body_battery_high);
            const avgHigh = valid.length ? Math.round(valid.reduce((s, d) => s + d.body_battery_high, 0) / valid.length) : null;
            return {
                value: latest?.body_battery_high ?? '—',
                sub: latest?.body_battery_low != null ? `Tagesminimum: ${latest.body_battery_low}` : '',
                kpis: [
                    { label: 'Maximum heute', value: latest?.body_battery_high ?? '—' },
                    { label: 'Minimum heute', value: latest?.body_battery_low ?? '—' },
                    { label: 'Ø Maximum (90d)', value: avgHigh ?? '—' },
                ],
                chart: {
                    title: 'Body Battery Verlauf (90 Tage)',
                    type: 'line',
                    labels: data.map(d => fmtDate(d.date)),
                    datasets: [
                        { label: 'Maximum', data: data.map(d => d.body_battery_high), borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
                        { label: 'Minimum', data: data.map(d => d.body_battery_low), borderColor: '#f97316', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
                    ],
                },
                formula: [
                    ['Quelle', 'Garmin Firstbeat-Algorithmus (proprietary)'],
                    ['Inputs', 'HRV, Stresslevel, Schlafqualität, Aktivitätsintensität'],
                    ['Skala', '0–100 (0 = leer, 100 = voll geladen)'],
                    ['Aufladen', 'Schlaf +++ / Entspannung + / Leichter Sport +'],
                    ['Entladen', 'Intensives Training −−− / Stress −− / Schlechter Schlaf −'],
                ],
                science: 'Garmin Body Battery basiert auf dem proprietären Firstbeat Analytics-Algorithmus, der HRV-basierte Stressanalyse, Schlafqualitätsbewertung und Aktivitätsintensität kontinuierlich integriert. Der Algorithmus ist nicht öffentlich peer-reviewed; das zugrundeliegende Konzept der energetischen Reserve spiegelt physiologische Prinzipien der autonomen Regulation wider. Body Battery ist als heuristischer Indikator zu verstehen — kein medizinischer Messwert und nicht unabhängig validiert.',
                sources: [
                    { label: 'Firstbeat Technologies: Stress and Recovery Analysis — White Paper', url: 'https://www.firstbeat.com/en/science-behind-firstbeat/' },
                    { label: 'Garmin Body Battery — Offizielle Erklärung', url: 'https://www.garmin.com/en-US/garmin-technology/health-science/body-battery/' },
                ],
                eli5: 'Stell dir einen Smartphone-Akku vor: Sport und Stress verbrauchen Energie, Schlaf und Erholung laden ihn wieder auf. Garmin berechnet das kontinuierlich aus deinem Herzrhythmus. Wenn du morgens mit 90+ aufwachst, hat die Nacht gut geladen. Wenn du nach einer intensiven Trainingswoche mit 30 aufwachst, ist eine Erholungspause fällig.',
            };
        },
    },

    physical: {
        title: 'Physische Energie',
        section: 'Energie',
        async fetch() {
            return Promise.all([
                fetch('/api/energy').then(r => r.json()),
                fetch('/api/ml-history?days=90').then(r => r.json()),
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
                sub: tsb !== '—' ? `TSB ${tsb}` : (phys == null ? 'noch keine Daten' : ''),
                kpis: [
                    { label: 'Score (0–100)', value: phys?.score != null ? Math.round(phys.score) : '—' },
                    { label: 'ATL — Erschöpfung', value: atl },
                    { label: 'CTL — Fitness', value: ctl },
                    { label: 'TSB — Balance', value: tsb },
                ],
                chart: hist.length > 3 ? {
                    title: 'TSB / ATL / CTL Verlauf (90 Tage)',
                    type: 'line',
                    labels: hist.map(d => fmtDate(d.date)),
                    datasets: [
                        { label: 'CTL (Fitness)', data: hist.map(d => d.ctl ?? null), borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 },
                        { label: 'ATL (Erschöpfung)', data: hist.map(d => d.atl ?? null), borderColor: '#ef4444', backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 },
                        { label: 'TSB (Balance)', data: hist.map(d => d.tsb ?? null), borderColor: '#6366f1', backgroundColor: isDark ? 'rgba(99,102,241,.12)' : 'rgba(99,102,241,.08)', fill: true, tension: 0.3, pointRadius: 0 },
                    ],
                } : null,
                formula: [
                    ['HRr (Heart Rate Reserve)', 'HRr = (HR − RHR) / (HRmax − RHR)'],
                    ['TRIMP (kontinuierlich)', 'Dauer(min) × HRr × (HRr × 4 + 1)  — kontinuierliches Polynom, nicht zonenbasiert'],
                    ['ATL (τ=7d)', 'ATLₜ = ATLₜ₋₁ × e^(−1/7) + TRIMPₜ × (1 − e^(−1/7))'],
                    ['CTL (τ=42d)', 'CTLₜ = CTLₜ₋₁ × e^(−1/42) + TRIMPₜ × (1 − e^(−1/42))'],
                    ['TSB', 'TSB = CTL − ATL  (positiv = erholt, negativ = ermüdet)'],
                    ['Score', 'Score = 50 + TSB × 1.5 (geclampt 0–100)'],
                ],
                science: 'Das Banister-Impuls-Antwort-Modell (1991) modelliert Fitness als Differenz zweier exponentieller Glättungsfilter: Chronic Training Load (CTL, τ = 42 Tage) approximiert langfristige Fitnessadaptation; Acute Training Load (ATL, τ = 7 Tage) modelliert kurzfristige Ermüdung. Training Stress Balance (TSB = CTL − ATL) quantifiziert den aktuellen Leistungszustand. Die TRIMP-Berechnung nutzt eine kontinuierliche HRr-basierte Gewichtungsformel (HRr × (HRr × 4 + 1)), die das Edwards-Zonen-Konzept als stetiges Polynom umsetzt — metabolisch präziser als diskrete Zonen. Das Modell wurde extensiv in Ausdauersport-Periodisierung validiert; optimales Wettkampf-TSB liegt typischerweise bei +5 bis +15 (Busso, 2003).',
                sources: [
                    { label: 'Wikipedia: Fitness–Fatigue Model (Banister 1991)', url: 'https://en.wikipedia.org/wiki/Fitness%E2%80%93fatigue_model' },
                    { label: 'Achten & Jeukendrup (2003): Heart Rate Monitoring — Sports Medicine', url: 'https://pubmed.ncbi.nlm.nih.gov/14561293/' },
                    { label: 'Busso (2003): Variable Dose-Response Model — Med Sci Sports Exerc', url: 'https://pubmed.ncbi.nlm.nih.gov/12783043/' },
                ],
                eli5: 'Denk an ein Sparkonto: Jedes Training hebt Geld ab (ATL = kurzfristige Erschöpfung). Regelmäßiges Training über Monate baut Zinsen auf (CTL = Fitness-Basis). TSB ist dein Kontostand: positiv = ausgeruht und fit. Negativ = müde. Vor Wettkämpfen ist ein leicht positiver TSB (+5 bis +15) ideal — fit ohne erschöpft zu sein.',
            };
        },
    },

    autonomic: {
        title: 'Autonome Energie',
        section: 'Energie',
        async fetch() {
            return Promise.all([
                fetch('/api/energy').then(r => r.json()),
                fetch('/api/ml-history?days=90').then(r => r.json()),
            ]);
        },
        render([energy, history]) {
            const auton = energy.energy_autonomic;
            const hist = history.energy_autonomic || [];
            const dev = auton?.deviation != null
                ? (auton.deviation >= 0 ? '+' : '') + auton.deviation.toFixed(2) + ' σ'
                : '—';
            const baseline = auton?.baseline_ln_mean != null
                ? Math.round(Math.exp(auton.baseline_ln_mean)) + ' ms'
                : '—';
            return {
                value: auton?.score != null ? Math.round(auton.score) : '—',
                sub: dev !== '—' ? dev + ' vom Baseline' : (auton == null ? 'noch keine Daten' : ''),
                kpis: [
                    { label: 'Score (0–100)', value: auton?.score != null ? Math.round(auton.score) : '—' },
                    { label: 'Abweichung (σ = Standardabweichungen)', value: dev },
                    { label: 'Persönlicher Baseline (Ø 90 Tage)', value: baseline },
                ],
                chart: hist.length > 3 ? {
                    title: 'HRV-Baseline Score (90 Tage)',
                    type: 'line',
                    labels: hist.map(d => fmtDate(d.date)),
                    datasets: [{
                        data: hist.map(d => d.value ?? null),
                        borderColor: '#22c55e',
                        backgroundColor: isDark ? 'rgba(34,197,94,.1)' : 'rgba(34,197,94,.07)',
                        fill: true, tension: 0.3, pointRadius: 0,
                    }],
                    scales: { y: { min: 0, max: 100 } },
                } : null,
                formula: [
                    ['Normierung', 'ln(HRV) — logarithmische Transformation für Normalverteilung'],
                    ['Baseline', 'Gleitendes Mittel μ und Stdabw σ über 90 Tage (min. 20 Messpunkte)'],
                    ['Z-Score', 'z = (ln(HRVₜ) − μ₉₀) / σ₉₀'],
                    ['Score', 'Score = 50 + z × 15 (geclampt 0–100)'],
                ],
                science: 'Absolute HRV-Werte sind interindividuell extrem variabel (RMSSD 20–100 ms normal bei Ausdauersportlern), aber intraindividuell relativ stabil. Die ln-Transformation normalisiert die rechtsschiefe RMSSD-Verteilung. Die σ-Abweichung vom persönlichen 90-Tage-Baseline ist klinisch aussagekräftiger als ein absoluter Vergleich mit Referenzwerten: Kiviniemi et al. (2007) und Plews et al. (2013) zeigen, dass tägliche HRV-Abweichungen von > 1 σ signifikant mit suboptimaler Erholungsqualität korrelieren.',
                sources: [
                    { label: 'Kiviniemi et al. (2007): HRV-Guided Endurance Training — IJSPP', url: 'https://pubmed.ncbi.nlm.nih.gov/17492574/' },
                    { label: 'Plews et al. (2013): HRV in Elite Endurance Athletes — IJSPP', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                    { label: 'Buchheit (2014): Monitoring Recovery with HRV — BJSM', url: 'https://bjsm.bmj.com/content/48/4/243' },
                ],
                eli5: 'Wir vergleichen dein HRV nur mit DEINEM eigenen Normalwert. Score 50 = genau dein Durchschnitt. Score 70 = du bist heute deutlich erholter als üblich. Score 30 = dein HRV ist ungewöhnlich niedrig. Das ist aussagekräftiger als ein absoluter Wert, weil jeder Mensch seinen eigenen HRV-Normalbereich hat.',
            };
        },
    },

    cognitive: {
        title: 'Kognitive Energie',
        section: 'Energie',
        async fetch() {
            return Promise.all([
                fetch('/api/energy').then(r => r.json()),
                fetch('/api/ml-history?days=90').then(r => r.json()),
            ]);
        },
        render([energy, history]) {
            const cog = energy.energy_cognitive;
            const hist = history.energy_cognitive || [];
            return {
                value: cog?.score != null ? Math.round(cog.score) : '—',
                sub: cog?.debt_hours != null ? cog.debt_hours.toFixed(1) + 'h Schlafschuld' : (cog == null ? 'noch keine Daten' : ''),
                kpis: [
                    { label: 'Score (0–100)', value: cog?.score != null ? Math.round(cog.score) : '—' },
                    { label: 'Schlafschuld (7d)', value: cog?.debt_hours != null ? cog.debt_hours.toFixed(1) + 'h' : '—' },
                ],
                chart: hist.length > 3 ? {
                    title: 'Schlafschuld Score (90 Tage)',
                    type: 'line',
                    labels: hist.map(d => fmtDate(d.date)),
                    datasets: [{
                        data: hist.map(d => d.value ?? null),
                        borderColor: '#8b5cf6',
                        backgroundColor: isDark ? 'rgba(139,92,246,.1)' : 'rgba(139,92,246,.07)',
                        fill: true, tension: 0.3, pointRadius: 0,
                    }],
                    scales: { y: { min: 0, max: 100 } },
                } : null,
                formula: [
                    ['Ziel', '7h Schlaf pro Nacht (NSF-Empfehlung Erwachsene, untere Grenze)'],
                    ['Debt/Nacht', 'max(0, 7h − tatsächlicher Schlaf)'],
                    ['Gesamt-Debt', 'Σ der letzten 7 Nächte'],
                    ['Score', 'Score = 100 − Debt × 6  (0 bei 16.7h kumulativer Schuld)'],
                ],
                science: 'Borbélys Zwei-Prozess-Modell (1982) ist das einflussreichste Modell der Schlafregulation: Process S (homöostatischer Schlafdruck) akkumuliert während Wachheit und dissipiert während NREM-Slow-Wave-Sleep. Chronische Schlafrestrik­tion (< 7h) akkumuliert kognitive Schulden ohne subjektives Bewusstsein: Van Dongen et al. (2003) zeigten, dass Probanden mit 6h Schlaf nach 14 Tagen kognitive Defizite auf dem Niveau von 24h totalem Schlafentzug aufwiesen. Kein Tiefschlaf-Qualitätsfaktor: Garmins Tiefschlaf-Erkennung (Akzelerometer + optisches HRV) ist zu unzuverlässig für eine rauscharme Qualitätsgewichtung — der Score basiert bewusst nur auf Schlafdauer.',
                sources: [
                    { label: 'Borbély (1982): Two-Process Model of Sleep Regulation — Human Neurobiology', url: 'https://pubmed.ncbi.nlm.nih.gov/7185792/' },
                    { label: 'Van Dongen et al. (2003): Cumulative Sleep Restriction — Sleep', url: 'https://pubmed.ncbi.nlm.nih.gov/12683469/' },
                    { label: 'Sleep Foundation: How Much Sleep Do We Really Need?', url: 'https://www.sleepfoundation.org/how-sleep-works/how-much-sleep-do-we-really-need' },
                ],
                eli5: 'Jede Nacht mit zu wenig Schlaf packt dir Gewichte in einen unsichtbaren Rucksack. Der Rucksack macht es schwerer, klar zu denken und Entscheidungen zu treffen. Score 100 = leerer Rucksack. Score 27 heißt, du trägst ca. 10h Schlafschuld mit dir. Zwei gute Nächte hintereinander können das schon merklich verbessern.',
            };
        },
    },

    'hr-zscore': {
        title: 'Ruhepuls Z-Score',
        section: 'ML & Status',
        async fetch() {
            return Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/daily?days=90').then(r => r.json()),
            ]);
        },
        render([ml, daily]) {
            const anomaly = ml.anomaly_hr;
            const zscore = anomaly?.z_score?.toFixed(2) ?? '—';
            const isAnom = anomaly?.is_anomaly;
            const today = daily.at(-1);
            return {
                value: zscore,
                sub: isAnom ? '⚠ Anomalie erkannt' : (anomaly?.z_score != null ? '✓ Normal' : 'zu wenig Daten'),
                kpis: [
                    { label: 'Z-Score heute (Standardabweichungen vom Ø)', value: zscore },
                    { label: 'Status', value: isAnom ? '⚠ Anomalie' : (anomaly?.z_score != null ? '✓ Normal' : '—') },
                    { label: 'Baseline Ø (30 Tage)', value: anomaly?.baseline_mean ? Math.round(anomaly.baseline_mean) + ' bpm' : '—' },
                    { label: 'Ruhepuls heute', value: today?.resting_hr ? today.resting_hr + ' bpm' : '—' },
                ],
                chart: daily.some(d => d.resting_hr) ? {
                    title: 'Ruhepuls-Verlauf (90 Tage)',
                    type: 'line',
                    labels: daily.map(d => fmtDate(d.date)),
                    datasets: [{ data: daily.map(d => d.resting_hr ?? null), borderColor: '#ef4444', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 }],
                } : null,
                formula: [
                    ['Baseline', 'Gleitendes 30-Tage-Fenster (min. 7 Messpunkte erforderlich)'],
                    ['Z-Score', 'Z = (HR_heute − μ₃₀) / σ₃₀'],
                    ['Anomalie', '|Z| > 2.0 = Anomalie (≈ äußerste 5% der Normalverteilung)'],
                    ['Positiv (Z > +2)', 'Hoher Ruhepuls → Übertraining, Krankheit, Schlafmangel'],
                    ['Negativ (Z < −2)', 'Sehr tiefer Ruhepuls → Super-Erholung oder Messproblem'],
                ],
                science: 'Resting Heart Rate (RHR) ist ein sensitiver Biomarker des autonomen Gleichgewichts: sympathische Aktivierung durch Übertraining, Infektion oder Schlafmangel erhöht RHR messbar vor klinischen Symptomen. Die Z-Score-basierte Anomalieerkennung entstammt der statistischen Prozesskontrolle. Die |Z| > 2.0-Schwelle entspricht den äußersten ≈ 5% einer Normalverteilung (zweiseitig) und liefert bei ausreichend langem Beobachtungsfenster spezifische Anomaliemeldungen. Bidirektionale Erkennung (|Z|, nicht nur Z > 0) ist wichtig, da ein ungewöhnlich tiefer Ruhepuls ebenso auf Messartefakte oder atypische Erholung hinweisen kann.',
                sources: [
                    { label: 'Buchheit (2014): Monitoring Recovery in Endurance Sports — BJSM', url: 'https://bjsm.bmj.com/content/48/4/243' },
                    { label: 'Achten & Jeukendrup (2003): Heart Rate Monitoring — Sports Medicine', url: 'https://pubmed.ncbi.nlm.nih.gov/14561293/' },
                ],
                eli5: 'Wir schauen, ob dein heutiger Ruhepuls ungewöhnlich anders ist als dein eigener Normalwert der letzten 30 Tage. Z=0 heißt: genau wie immer. Z=+2 heißt: heute 2 Standardabweichungen höher als normal. Wenn du sonst immer 44bpm hast, aber heute 52bpm, kann das ein frühes Zeichen für eine Erkältung sein — noch bevor du dich krank fühlst.',
            };
        },
    },

    'readiness-rf': {
        title: 'Readiness-Prognose',
        section: 'ML & Status',
        async fetch() {
            return Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=90').then(r => r.json()),
            ]);
        },
        render([ml, history]) {
            const rf = ml.readiness_rf;
            const meta = ml.model_meta_rf;
            const hist = history.readiness_rf || [];
            const score = rf?.value != null ? Math.round(rf.value) : null;
            const cls = score != null ? (score >= 80 ? 'badge-balanced' : score >= 50 ? 'badge-unbalanced' : 'badge-poor') : '';
            const lbl = score != null ? (score >= 80 ? 'Gut' : score >= 50 ? 'Moderat' : 'Niedrig') : '—';
            return {
                value: score != null
                    ? `<span class="badge ${cls}" style="font-size:2.5rem;padding:.2rem .8rem;letter-spacing:-.01em">${score}</span>`
                    : '—',
                sub: lbl + (score != null ? ' · Readiness (0–100)' : ''),
                kpis: [
                    { label: 'Heutiger Score', value: score ?? '—' },
                    { label: 'Trainingsdaten', value: meta?.n_training_samples != null ? meta.n_training_samples + ' Tage' : '—' },
                    { label: 'Letztes Training', value: meta?.trained_at ? fmtDate(meta.trained_at) : '—' },
                ],
                chart: hist.length > 3 ? {
                    title: 'Prognose-Verlauf (90 Tage)',
                    type: 'line',
                    labels: hist.map(d => fmtDate(d.date)),
                    datasets: [{
                        data: hist.map(d => d.value ?? null),
                        borderColor: '#6366f1',
                        backgroundColor: isDark ? 'rgba(99,102,241,.12)' : 'rgba(99,102,241,.07)',
                        fill: true, tension: 0.3, pointRadius: 2,
                    }],
                    scales: { y: { min: 0, max: 100 } },
                } : null,
                formula: [
                    ['Modell', 'Random Forest Regressor (scikit-learn, 100 Entscheidungsbäume)'],
                    ['Features', 'hrv_last_night, sleep_score, resting_hr, aerobic_effect, anaerobic_effect'],
                    ['Label', 'Energie-basierter Readiness-Score des Folgetages (Physical × 0.35 + Autonomic × 0.40 + Cognitive × 0.25)'],
                    ['Training', 'Wöchentlich (Sonntag 3:00 Uhr), min. 30 Datenpunkte erforderlich'],
                    ['Output', 'Prognostizierter Readiness-Score für morgen (0–100)'],
                ],
                science: 'Random Forests (Breiman, 2001) sind Ensemble-Lernverfahren, die aus B Bootstrap-Stichproben B dekorrelierte Entscheidungsbäume trainieren. Averaging über alle Bäume reduziert Varianz ohne Bias-Erhöhung. Das Konfidenzintervall (10./90. Perzentil der Tree-Prognosen) quantifiziert Prognose-Unsicherheit — besonders relevant bei wenigen Trainingsdaten. Das Modell lernt personalisiert: Features (HRV, Schlaf, Ruhepuls, Trainingseffekt) am Tag N sagen den energie-basierten Readiness-Score am Tag N+1 vorher.',
                sources: [
                    { label: 'Breiman (2001): Random Forests — Machine Learning', url: 'https://link.springer.com/article/10.1023/A:1010933404324' },
                    { label: 'Claudino et al. (2019): ML for Athlete Monitoring — Frontiers in Physiology', url: 'https://www.frontiersin.org/articles/10.3389/fphys.2019.00337/full' },
                    { label: 'Saw et al. (2016): Monitoring Athlete Well-Being — Sports Medicine', url: 'https://pubmed.ncbi.nlm.nih.gov/26412149/' },
                ],
                eli5: 'Ein Computerprogramm hat aus deinen Daten gelernt: "Wenn HRV hoch, Schlaf gut und Ruhepuls normal ist, dann ist diese Person morgen meistens fit." 100 Entscheidungsbäume stimmen jeweils unabhängig voneinander ab und ihr Durchschnitt ist die Prognose. Je mehr Tage das Modell beobachtet hat, desto besser kennt es deine persönlichen Muster.',
            };
        },
    },

    'hrv-status': {
        title: 'HRV-Status',
        section: 'ML & Status',
        async fetch() { return fetch('/api/hrv/trend?days=90').then(r => r.json()); },
        render(data) {
            const statusLabels = { balanced: 'Ausgeglichen', unbalanced: 'Unausgeglichen', low: 'Niedrig', poor: 'Niedrig' };
            const statusCls = { balanced: 'badge-balanced', unbalanced: 'badge-unbalanced', low: 'badge-poor', poor: 'badge-poor' };
            const latest = data.at(-1);
            const key = (latest?.hrv_status || '').toLowerCase();
            const label = statusLabels[key] ?? (latest?.hrv_status ?? '—');
            const cls = statusCls[key] ?? '';
            const countBalanced = data.filter(d => (d.hrv_status || '').toLowerCase() === 'balanced').length;
            return {
                value: cls
                    ? `<span class="badge ${cls}" style="font-size:1.8rem;padding:.2rem .7rem">${label}</span>`
                    : '—',
                sub: latest?.hrv_last_night ? latest.hrv_last_night + ' ms letzte Nacht' : '',
                kpis: [
                    { label: 'Aktueller Status', value: label },
                    { label: 'Letzte Nacht HRV', value: latest?.hrv_last_night ? latest.hrv_last_night + ' ms' : '—' },
                    { label: 'Ausgeglichen (90d)', value: data.length ? countBalanced + ' / ' + data.length + ' Tage' : '—' },
                ],
                chart: data.some(d => d.hrv_last_night) ? {
                    title: 'HRV letzte Nacht (90 Tage)',
                    type: 'line',
                    labels: data.map(d => fmtDate(d.date)),
                    datasets: [{
                        label: 'HRV letzte Nacht',
                        data: data.map(d => d.hrv_last_night ?? null),
                        borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2,
                    }],
                } : null,
                formula: [
                    ['Quelle', 'Garmin Firstbeat-Algorithmus (hrv_daily.hrv_status)'],
                    ['Vergleich', 'HRV letzte Nacht vs. persönliche 3-Wochen-Baseline'],
                    ['BALANCED', 'HRV im Normalbereich → gute Erholung'],
                    ['UNBALANCED', 'HRV leicht außerhalb → erhöhte Belastung oder Stress'],
                    ['LOW / POOR', 'HRV deutlich unter Baseline → Überbelastung oder Erkrankung'],
                ],
                science: 'Garmin HRV Status basiert auf dem proprietären Firstbeat Analytics-Algorithmus, der nächtliches RMSSD mit einer rollierenden 3-Wochen-Baseline vergleicht. Die Klassifikation (BALANCED/UNBALANCED/LOW/POOR) spiegelt konzeptionell die wissenschaftliche Literatur zur HRV-gestützten Trainingsteuerung wider (Plews et al., 2013). Der Algorithmus ist nicht öffentlich peer-reviewed. Die zugrundeliegenden Prinzipien — täglicher Vergleich gegen persönlichen Baseline, Tiefenfilterung via Wochenø — sind wissenschaftlich fundiert.',
                sources: [
                    { label: 'Firstbeat Technologies: HRV-Based Recovery Analysis', url: 'https://www.firstbeat.com/en/science-behind-firstbeat/' },
                    { label: 'Plews et al. (2013): HRV in Elite Endurance Athletes — IJSPP', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                    { label: 'Task Force ESC/NASPE (1996): HRV Standards — Circulation', url: 'https://www.ahajournals.org/doi/10.1161/01.CIR.93.5.1043' },
                ],
                eli5: 'Garmin schaut jeden Morgen auf dein HRV und vergleicht es mit deinem persönlichen Normalwert der letzten 3 Wochen. "Ausgeglichen" heißt: alles normal, gut erholt. "Unausgeglichen" heißt: etwas stimmt nicht ganz. "Niedrig" ist ein klares Signal: heute solltest du regenerieren, nicht intensiv trainieren.',
            };
        },
    },

    'training-status': {
        title: 'Trainingszustand',
        section: 'ML & Status',
        async fetch() {
            return Promise.all([
                fetch('/api/training-status').then(r => r.json()),
                fetch('/api/ml-history?days=90').then(r => r.json()),
            ]);
        },
        render([data, history]) {
            const tsMap = {
                PRODUCTIVE:   { label: 'Aufbauend',       cls: 'badge-balanced',   desc: 'Dein Training ist effektiv — du wirst gerade fitter.' },
                MAINTAINING:  { label: 'Erhalt',          cls: 'badge-balanced',   desc: 'Du hältst dein aktuelles Fitnesslevel stabil.' },
                RECOVERY:     { label: 'Erholung',        cls: 'badge-unbalanced', desc: 'Dein Körper erholt sich nach hoher Belastung.' },
                UNPRODUCTIVE: { label: 'Nicht produktiv', cls: 'badge-unbalanced', desc: 'Zu wenig oder zu viel Training für Fortschritte.' },
                OVERREACHING: { label: 'Übertraining',    cls: 'badge-poor',       desc: 'Zu hohe Belastung — Erholung dringend empfohlen.' },
                DETRAINING:   { label: 'Abfall',          cls: 'badge-poor',       desc: 'Zu wenig Aktivität — Fitness nimmt ab.' },
            };
            const key = (data?.training_status || '').toUpperCase();
            const entry = tsMap[key] || { label: data?.training_status ?? '—', cls: '', desc: '' };
            return {
                value: entry.cls
                    ? `<span class="badge ${entry.cls}" style="font-size:1.8rem;padding:.2rem .7rem">${entry.label}</span>`
                    : '—',
                sub: data?.date ? 'Stand ' + fmtDate(data.date) : '',
                kpis: [
                    { label: 'Status', value: entry.label },
                    { label: 'Bedeutung', value: entry.desc || '—' },
                ],
                chart: (() => {
                    const physHist = history.energy_physical || [];
                    return physHist.length > 3 ? {
                        title: 'Training Stress Balance — TSB (90 Tage)',
                        type: 'line',
                        labels: physHist.map(d => fmtDate(d.date)),
                        datasets: [{
                            label: 'TSB',
                            data: physHist.map(d => d.tsb ?? null),
                            borderColor: '#6366f1',
                            backgroundColor: isDark ? 'rgba(99,102,241,.12)' : 'rgba(99,102,241,.07)',
                            fill: true, tension: 0.3, pointRadius: 0,
                        }],
                    } : null;
                })(),
                formula: [
                    ['Quelle', 'Garmin Firstbeat-Algorithmus (daily_summary.training_status)'],
                    ['Inputs', 'Trainingsbelastung letzte Wochen, VO₂max-Schätzung, Erholungsstatus'],
                    ['PRODUCTIVE', 'Belastung erhöht VO₂max → Fitness wächst'],
                    ['MAINTAINING', 'Belastung hält aktuelles Level stabil'],
                    ['RECOVERY', 'Bewusste Entlastungsphase nach hoher Belastung'],
                    ['OVERREACHING', 'Chronische Überbelastung — Verletzungsrisiko steigt'],
                ],
                science: 'Garmin Training Status integriert VO₂max-Schätzung via submaximaler Laufanalyse (Firstbeat-Algorithmus) mit Trainingsbelastungsperiodisierung. Die Klassifikation modelliert das Prinzip der Superkompensation: ausreichende Belastung + Erholung → PRODUCTIVE; chronische Überbelastung ohne ausreichende Erholung → OVERREACHING (Meeusen et al., 2013). Wie Body Battery ist dieser Wert ein proprietäres Firstbeat-Modell ohne externe Peer-Review-Validierung — als Orientierung, nicht als klinische Diagnose zu interpretieren.',
                sources: [
                    { label: 'Firstbeat Technologies: Training Status Overview', url: 'https://www.firstbeat.com/en/science-behind-firstbeat/training-effect/' },
                    { label: 'Meeusen et al. (2013): Overtraining Syndrome Consensus — Med Sci Sports Exerc', url: 'https://pubmed.ncbi.nlm.nih.gov/23247672/' },
                ],
                eli5: 'Garmin analysiert deine Trainingsbelastung der letzten Wochen und vergleicht sie mit deiner geschätzten Fitness. "Aufbauend" bedeutet: du machst es perfekt, du wirst gerade stärker. "Übertraining" ist ein rotes Licht — dein Körper kann die Belastung nicht mehr sinnvoll verarbeiten. Dann hilft mehr Training nicht mehr, sondern schadet.',
            };
        },
    },

    readiness: {
        title: 'Readiness-Score',
        section: 'Readiness',
        async fetch() {
            return Promise.all([
                fetch('/api/readiness').then(r => r.json()),
                fetch('/api/ml-history?days=90').then(r => r.json()),
            ]);
        },
        render([today, history]) {
            const scoreColors = { 'badge-balanced': '#22c55e', 'badge-unbalanced': '#f59e0b', 'badge-poor': '#ef4444' };
            const color = scoreColors[today?.cls] || '#64748b';

            const physMap  = Object.fromEntries((history.energy_physical  || []).map(d => [d.date, d.value]));
            const autonMap = Object.fromEntries((history.energy_autonomic || []).map(d => [d.date, d.value]));
            const cogMap   = Object.fromEntries((history.energy_cognitive || []).map(d => [d.date, d.value]));
            const dates    = [...new Set([...Object.keys(physMap), ...Object.keys(autonMap), ...Object.keys(cogMap)])].sort();
            const scores   = dates.map(date => {
                const parts = [[physMap[date], 0.35], [autonMap[date], 0.40], [cogMap[date], 0.25]]
                    .filter(([v]) => v != null);
                if (!parts.length) return null;
                const tw = parts.reduce((s, [, w]) => s + w, 0);
                return Math.round(parts.reduce((s, [v, w]) => s + v * w / tw, 0));
            });

            const p = today?.energy_physical  != null ? Math.round(today.energy_physical)  : null;
            const a = today?.energy_autonomic != null ? Math.round(today.energy_autonomic) : null;
            const c = today?.energy_cognitive != null ? Math.round(today.energy_cognitive) : null;

            return {
                value: today?.score != null
                    ? `<span style="color:${color};font-size:4rem;font-weight:800;letter-spacing:-.04em">${today.score}</span>`
                    : '—',
                sub: today?.label ?? '',
                kpis: [
                    { label: 'Physische Energie (35%)',  value: p != null ? p : '—' },
                    { label: 'Autonome Energie (40%)',   value: a != null ? a : '—' },
                    { label: 'Kognitive Energie (25%)',  value: c != null ? c : '—' },
                ],
                chart: dates.length > 3 ? {
                    title: 'Readiness-Verlauf (90 Tage)',
                    type: 'line',
                    labels: dates.map(fmtDate),
                    datasets: [{
                        data: scores,
                        borderColor: '#6366f1',
                        backgroundColor: isDark ? 'rgba(99,102,241,.12)' : 'rgba(99,102,241,.07)',
                        fill: true, tension: 0.3, pointRadius: 0,
                    }],
                    scales: { y: { min: 0, max: 100 } },
                } : null,
                formula: [
                    ['Physische Energie', 'TRIMP-Polynom + Banister ATL/CTL/TSB → Score (0–100) — Gewicht: 35%'],
                    ['Autonome Energie', 'HRV (RMSSD) ln-normiert, σ-Abweichung von persönlichem Baseline — Gewicht: 40%'],
                    ['Kognitive Energie', 'Borbély Process S: kumulative Schlafschuld 7d vs. 7h-Ziel — Gewicht: 25%'],
                    ['Fehlende Komponenten', 'Verbleibende Gewichte werden proportional normiert'],
                    ['Score', 'Gewichtetes Mittel, geclampt 0–100'],
                ],
                science: 'Der Composite-Readiness-Score integriert drei physiologisch eigenständige Dimensionen: (1) Physische Trainingsbelastung via Banister-Impuls-Antwort-Modell (CTL/ATL/TSB, Zeitkonstanten 42/7 Tage), (2) Autonome Erholungskapazität via HRV-Baseline-Deviation (ln RMSSD, σ-normiert gegen persönliches Baseline-Fenster), (3) Kognitive Kapazität via Borbély-Schlafschuld-Modell (Process S, 7h-Ziel, rein durationsbasiert). Die Gewichtung (35%/40%/25%) reflektiert die prädiktive Stärke von HRV als stärkstem Einzelprädiktor für Leistungsbereitschaft (Saw et al., 2016). Alle Berechnungen sind transparent und formelbasiert — keine proprietären Algorithmen.',
                sources: [
                    { label: 'Wikipedia: Fitness–Fatigue Model (Banister 1991)', url: 'https://en.wikipedia.org/wiki/Fitness%E2%80%93fatigue_model' },
                    { label: 'Borbély (1982): Two-Process Model of Sleep Regulation — Human Neurobiology', url: 'https://pubmed.ncbi.nlm.nih.gov/7185792/' },
                    { label: 'Plews et al. (2013): HRV Monitoring in Elite Athletes — IJSPP', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                    { label: 'Saw et al. (2016): Monitoring Athlete Well-Being — Sports Medicine', url: 'https://pubmed.ncbi.nlm.nih.gov/26412149/' },
                ],
                eli5: 'Der Readiness-Score kombiniert drei eigene, transparent berechnete Dimensionen. Physisch: Wie viel Trainingsbelastung steckt noch im System? Autonom: Ist dein Nervensystem (HRV) heute besser oder schlechter erholt als dein persönlicher Normalwert? Kognitiv: Wie viel Schlafschuld hast du angehäuft? Alles ohne Garmin-Blackbox — nur unsere eigenen Formeln.',
            };
        },
    },

    'sleep-score-custom': {
        title: 'Schlafqualität (Custom)',
        section: 'Schlaf',
        async fetch() {
            return fetch('/api/ml-insights').then(r => r.json());
        },
        render(data) {
            const d = data['sleep_score_custom'];
            if (!d || d.score == null) return { value: '—', sub: 'Keine Schlafdaten', kpis: [] };
            const sc  = Math.round(d.score);
            const cls = sc >= 75 ? 'badge-balanced' : sc >= 50 ? 'badge-unbalanced' : 'badge-poor';
            const lbl = sc >= 75 ? 'Gut' : sc >= 50 ? 'Okay' : 'Schlecht';
            return {
                value: `<span class="badge ${cls}" style="font-size:3rem;padding:.2rem .8rem">${sc}</span>`,
                sub: lbl + ' · 0–100',
                kpis: [
                    { label: 'Schlafdauer', value: d.total_h != null ? d.total_h + ' h' : '—' },
                    { label: 'Tiefschlaf', value: d.deep_pct != null ? d.deep_pct + ' %' : '—' },
                    { label: 'REM-Schlaf', value: d.rem_pct  != null ? d.rem_pct  + ' %' : '—' },
                    { label: 'Wachzeit',   value: d.wake_pct != null ? d.wake_pct + ' %' : '—' },
                ],
                formula: [
                    ['Tiefschlaf-Score (35%)', 'min(100, Tiefschlaf% / 20% × 100) — Optimum 20% Tiefschlaf'],
                    ['REM-Score (25%)',         'min(100, REM% / 22% × 100) — Optimum 22% REM'],
                    ['Dauer-Score (25%)',       'min(100, Stunden / 8 × 100) — Optimum 8h'],
                    ['Wach-Penalty (15%)',      'max(0, 100 − Wach% × 500) — Optimum < 0.2% Wachzeit'],
                    ['Fehlende Phasen',         'Verbleibende Gewichte werden proportional normiert'],
                ],
                science: 'Der Custom-Schlaf-Score gewichtet Schlafphasen nach physiologischer Relevanz. Tiefschlaf (SWS) ist für körperliche Erholung und Gedächtniskonsolidierung kritisch (Empfehlung NSF: 20%). REM-Schlaf reguliert emotionale Verarbeitung und Kreativität (Empfehlung NSF: 22%). Schlafdauer bildet die Grundlage; Wachphasen über dem Minimum wirken als Penalty.',
                sources: [
                    { label: 'Walker (2017): Why We Sleep — Penguin Books', url: 'https://www.amazon.de/Why-We-Sleep-Science-Dreams/dp/0141983760' },
                    { label: 'National Sleep Foundation: Sleep Architecture Recommendations', url: 'https://www.thensf.org/sleep-faqs/what-are-sleep-stages/' },
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
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=30').then(r => r.json()),
            ]);
            return { insights, history };
        },
        render({ insights, history }) {
            const d = insights['hrv_status_custom'];
            if (!d || d.status == null) return { value: '—', sub: 'Zu wenig HRV-Daten (min. 7 Tage)', kpis: [] };
            const cls    = d.status === 'BALANCED' ? 'badge-balanced' : d.status === 'POOR' ? 'badge-poor' : 'badge-unbalanced';
            const devStr = d.deviation != null ? `${d.deviation >= 0 ? '+' : ''}${d.deviation.toFixed(2)}σ` : '';

            const hist = (history['hrv_status_custom'] || []).slice(-30);
            const statusToScore = { BALANCED: 100, UNBALANCED: 50, LOW: 25, POOR: 0 };

            return {
                value: `<span class="badge ${cls}" style="font-size:2.5rem;padding:.3rem 1rem">${d.status}</span>`,
                sub: devStr + (d.baseline_mean != null ? ` · Baseline ${d.baseline_mean.toFixed(1)} ln(ms)` : ''),
                kpis: [
                    { label: 'σ-Abweichung',   value: devStr || '—' },
                    { label: 'Baseline Mean',   value: d.baseline_mean  != null ? d.baseline_mean.toFixed(1)  : '—' },
                    { label: 'Baseline Std',    value: d.baseline_std   != null ? d.baseline_std.toFixed(2)   : '—' },
                    { label: 'HRV 7T-Mittel (ln)', value: d.hrv_7d_mean != null ? d.hrv_7d_mean.toFixed(1) : '—' },
                ],
                chart: hist.length > 3 ? {
                    title: 'HRV Status Verlauf (30 Tage)',
                    type: 'line',
                    labels: hist.map(h => fmtDate(h.date)),
                    datasets: [{
                        label: 'Status-Score',
                        data: hist.map(h => h.status != null ? statusToScore[h.status] ?? null : null),
                        borderColor: '#6366f1', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2,
                    }],
                    scales: { y: { min: 0, max: 100, ticks: { callback: v => ({ 100: 'BALANCED', 50: 'UNBALANCED', 25: 'LOW', 0: 'POOR' })[v] ?? '' } } },
                } : null,
                formula: [
                    ['Log-Transformation',  'ln(RMSSD) × 20 — normalisiert rechtschiefe HRV-Verteilung (Ithlete/Elite HRV)'],
                    ['Baseline',            'Rollierendes 90-Tage-Fenster: Mittelwert + Standardabweichung'],
                    ['Deviation',           '(heute − baseline_mean) / baseline_std'],
                    ['BALANCED',            'Deviation ≥ −0.5σ'],
                    ['UNBALANCED',          '−1.5σ ≤ Deviation < −0.5σ'],
                    ['LOW',                 '−2.0σ ≤ Deviation < −1.5σ'],
                    ['POOR',               'Deviation < −2.0σ'],
                ],
                science: 'Im Gegensatz zu Garmins proprietärem HRV-Status (Firstbeat-Algorithmus, Black Box) verwendet dieser Score eine persönliche σ-Baseline: Der heutige ln(RMSSD)-Wert wird gegen dein eigenes 90-Tage-Fenster normiert. Dadurch sind Schwellenwerte individuell statt absolut — ein HRV von 35ms kann für Person A BALANCED und für Person B LOW sein.',
                sources: [
                    { label: 'Plews et al. (2013): HRV and Training Monitoring — IJSPP', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                    { label: 'Altini & Plews (2021): Making Sense of HRV — Frontiers', url: 'https://www.frontiersin.org/articles/10.3389/fphys.2021.615561' },
                    { label: 'Elite HRV Score Methodology', url: 'https://help.elitehrv.com/article/57-the-1-10-relative-balance-score' },
                ],
                eli5: 'Garmin vergleicht deine HRV mit einer anonymen Referenzpopulation — wir vergleichen sie mit DIR. Wenn du normalerweise eine HRV von 60ms hast und heute 55ms misst, ist das für dich anders als für jemanden dessen Normal bei 40ms liegt. Dein persönlicher Normalwert ist der einzig sinnvolle Vergleichsmaßstab.',
            };
        },
    },

    'intensity-minutes': {
        title: 'Intensitätsminuten (Karvonen)',
        section: 'Aktivität',
        async fetch() {
            return fetch('/api/ml-insights').then(r => r.json());
        },
        render(data) {
            const d = data['intensity_minutes_custom'];
            if (!d || d.moderate_minutes == null) return { value: '—', sub: 'Keine Aktivitätsdaten für heute', kpis: [] };
            const total = d.moderate_minutes + d.vigorous_minutes * 2;
            return {
                value: total,
                sub: `${d.moderate_minutes} min moderat · ${d.vigorous_minutes} min intensiv`,
                kpis: [
                    { label: 'Moderat (50–70% HRr)',  value: d.moderate_minutes + ' min' },
                    { label: 'Intensiv (≥70% HRr)',   value: d.vigorous_minutes + ' min' },
                    { label: 'Äquivalente Minuten',   value: total + ' min (intensiv ×2)' },
                    { label: 'HRmax (verwendet)',      value: d.hrmax_used != null ? d.hrmax_used + ' bpm' : '—' },
                ],
                formula: [
                    ['HRR (Karvonen)',     'HRr = (HR − Ruhepuls) / (HRmax − Ruhepuls)'],
                    ['Moderat',           '0.50 ≤ HRr < 0.70 — jede Sekunde zählt als 1/60 Minute'],
                    ['Intensiv',          'HRr ≥ 0.70 — jede Sekunde zählt als 1/60 Minute'],
                    ['WHO-Äquivalent',    'moderat_min + intensiv_min × 2 (intensiv zählt doppelt)'],
                    ['Wochenziel WHO',    '150–300 min moderat ODER 75–150 min intensiv'],
                ],
                science: 'Die Karvonen-Methode (Heart Rate Reserve) ist physiologisch präziser als absolute HR-Zonen, da sie Ruhepuls und maximale HR individuell berücksichtigt. Garmin verwendet für Intensitätsminuten einen festen Schwellenwert von 60% der maximalen HR — Karvonen passt sich deiner Fitness an.',
                sources: [
                    { label: 'Karvonen et al. (1957): Effect of Training on Heart Rate — Ann Med Exp', url: 'https://pubmed.ncbi.nlm.nih.gov/13470504/' },
                    { label: 'WHO (2020): Physical Activity Guidelines', url: 'https://www.who.int/publications/i/item/9789240015128' },
                    { label: 'ACSM Guidelines for Exercise Testing and Prescription, 11th Ed.', url: 'https://www.acsm.org/education-resources/books/guidelines-exercise-testing-prescription' },
                ],
                eli5: 'Garmin zählt Intensitätsminuten nach einem fixen Pulsgrenzwert — egal wie fit du bist. Karvonen berücksichtigt deinen Ruhepuls: Wenn dein Herz in Ruhe sehr langsam schlägt (gute Fitness), muss es bei gleicher Anstrengung weniger schlagen. Die Formel normalisiert das und gibt dir eine faire Einschätzung.',
            };
        },
    },

    'training-effect': {
        title: 'Training Effect (Banister)',
        section: 'Aktivität',
        async fetch() {
            return fetch('/api/ml-insights').then(r => r.json());
        },
        render(data) {
            const d = data['training_effect_custom'];
            if (!d || d.effect == null) return { value: '—', sub: 'Profil (Geburtsdatum + Geschlecht) in Einstellungen eintragen', kpis: [] };
            const cls = d.effect >= 3.5 ? 'badge-balanced' : d.effect >= 2 ? 'badge-unbalanced' : 'badge-poor';
            const lbl = d.effect >= 4 ? 'Überbelastend' : d.effect >= 3 ? 'Stark' : d.effect >= 2 ? 'Moderat' : d.effect >= 1 ? 'Leicht' : 'Minimal';
            return {
                value: `<span class="badge ${cls}" style="font-size:3rem;padding:.2rem .8rem">${d.effect.toFixed(1)}</span>`,
                sub: `${lbl} · 0–5 Skala`,
                kpis: [
                    { label: 'Effect (0–5)',     value: d.effect.toFixed(2) },
                    { label: 'TRIMP heute',      value: d.trimp_today != null ? d.trimp_today.toFixed(1) : '—' },
                    { label: 'CTL (Fitness)',    value: d.ctl != null ? d.ctl.toFixed(1) : '—' },
                    { label: 'VO₂max (Schätz.)', value: d.vo2max != null ? d.vo2max + ' ml/kg/min' : '—' },
                ],
                formula: [
                    ['Banister TRIMP',     'Dauer(min) × HRr × e^(b × HRr) — b = 1.92 (männlich) / 1.67 (weiblich)'],
                    ['CTL (42d EWM)',      'Fitness-Baseline: exponentiell gewichteter Mittelwert über 42 Tage'],
                    ['Training Effect',   'atan(TRIMP_heute / (CTL × 0.5)) × (10/π) → geclampt 0–5'],
                    ['VO₂max (Uth 2004)', '15 × (HRmax / HRruhepuls)'],
                    ['Geschlecht',        'Koeffizient b aus Profil — Einstellungen → Profil'],
                ],
                science: 'Banister TRIMP (1991) berücksichtigt im Gegensatz zu Edwards TRIMP die exponentielle HR-Intensitäts-Beziehung: Bei sehr hoher Belastung steigt der physiologische Stress überproportional. Die Koeffizienten b unterscheiden sich nach biologischem Geschlecht (Morton 1990). Der Training Effect normiert den täglichen TRIMP gegen die CTL-Baseline — eine Session hat relativ mehr Effekt bei geringer Grundfitness.',
                sources: [
                    { label: 'Banister (1991): Modelling Elite Athletic Performance — Physiological Testing', url: 'https://www.researchgate.net/publication/232157711' },
                    { label: 'Morton et al. (1990): Modeling Human Performance in Running — J Appl Physiol', url: 'https://pubmed.ncbi.nlm.nih.gov/2262449/' },
                    { label: 'Uth et al. (2004): Estimation of VO2max from HR — Eur J Appl Physiol', url: 'https://pubmed.ncbi.nlm.nih.gov/14624296/' },
                ],
                eli5: 'Garmin zeigt dir einen Aerobic Training Effect nach einem Firstbeat-Algorithmus, den du nicht nachvollziehen kannst. Unser Wert basiert auf Banister TRIMP: Wie intensiv war das Training (Puls × Zeit), und wie viel davon verträgt dein aktuelles Fitness-Niveau (CTL)? Ein Training Effect von 3.0 bedeutet: deutliche Anpassungsreize, ohne überzubelasten.',
            };
        },
    },

    'acwr': {
        title: 'ACWR — Acute-to-Chronic Workload Ratio',
        section: 'Aktivität',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=30').then(r => r.json()),
            ]);
            return { insights, history };
        },
        render(data) {
            const d = data.insights['acwr'];
            if (!d || d.acwr == null) return { value: '—', sub: 'Zu wenig Trainings-Daten', kpis: [] };
            const hist = data.history['acwr'] || [];
            const badgeColor = d.level === 'red' ? 'badge-poor' : d.level === 'amber' ? 'badge-unbalanced' : 'badge-balanced';
            const risk = d.acwr > 1.5 || d.acwr < 0.8 ? '⚠️ Verletzungsrisiko erhöht' : d.acwr > 1.3 ? '⚠️ Erhöht' : '✓ Grüne Zone';
            return {
                value: d.acwr.toFixed(2),
                sub: `${risk}`,
                kpis: [
                    { label: 'ATL (7d)',          value: d.atl.toFixed(1) },
                    { label: 'CTL (42d)',         value: d.ctl.toFixed(1) },
                    { label: 'Grüne Zone',        value: '0.8 – 1.3' },
                    { label: 'Amber Zone',        value: '1.3 – 1.5' },
                ],
                formula: [
                    ['ACWR',              'ATL(7d) / CTL(42d)'],
                    ['ATL (Acute)',       'Trainingslast letzte 7 Tage (kurzfristige Ermüdung)'],
                    ['CTL (Chronic)',     'Trainingslast letzte 42 Tage (langfristige Fitness)'],
                    ['Grüne Zone',        '0.8 – 1.3: optimal, minimales Verletzungsrisiko'],
                    ['Rot/Amber',         '> 1.5 oder < 0.8: Überbelastung oder Detraining'],
                ],
                science: 'Gabbett (2016) zeigte in Ballsportlern: ACWR > 1.5 erhöht Verletzungsrisiko um 40–50%, unabhängig vom absoluten Trainingsvolumen. Der „Süßpunkt" liegt bei 0.8–1.3: ausreichend Reiz für Anpassung, aber nicht so plötzlich, dass Strukturen überfordert sind. ATL und CTL sind exponentiell gewichtete Durchschnitte (τ=7d bzw. τ=42d), daher stabiler als Fenster-Mittelwerte.',
                sources: [
                    { label: 'Gabbett TJ (2016): The training-injury prevention paradox — BJSM 50(5):273–280', url: 'https://pubmed.ncbi.nlm.nih.gov/26933171/' },
                    { label: 'Banister EW, Calvert TW (1991): Modeling Elite Athletic Performance — Physiological Testing', url: 'https://www.researchgate.net/publication/232157711' },
                ],
                eli5: 'Verletzungen entstehen oft nicht, wenn du hart trainierst, sondern wenn du zu schnell deinen Trainingsplan erhöhst. ACWR misst: Wie schnell steigerst du die Last? Wenn deine 7-Tage-Last plötzlich 50% über deiner normalen 42-Tage-Last liegt, warnt dich das System.',
            };
        },
    },

    'training-monotony': {
        title: 'Training Monotony & Strain',
        section: 'Aktivität',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=30').then(r => r.json()),
            ]);
            return { insights, history };
        },
        render(data) {
            const d = data.insights['training_monotony'];
            if (!d || d.monotony == null) return { value: '—', sub: 'Zu wenig Trainings-Daten', kpis: [] };
            const riskStr = d.monotony > 2.0 ? '⚠️ Zu monoton — Verletzungs-/Krankheitsrisiko' : d.monotony > 1.5 ? '⚠️ Moderat' : '✓ Gute Variation';
            return {
                value: d.monotony.toFixed(2),
                sub: riskStr,
                kpis: [
                    { label: 'Strain (7d)',       value: d.strain.toFixed(1) },
                    { label: 'TRIMP-Ø 7d',        value: d.trimp_7d_mean.toFixed(1) },
                    { label: 'σ TRIMP',           value: d.trimp_7d_std.toFixed(1) },
                    { label: 'Grenzwert',         value: '> 2.0 = zu monoton' },
                ],
                formula: [
                    ['Monotony',          'mean(TRIMP₇d) / σ(TRIMP₇d)'],
                    ['Strain',            'Σ(TRIMP₇d) × Monotony'],
                    ['Hohe Monotony',     '< Variation im Training → Immunsystem swollen'],
                    ['Ziel',              '1.0–1.5: Balance aus Konsistenz und Variation'],
                ],
                science: 'Foster (1998) fand in US-Schwimmern: trainingsbezogene Infekte waren um Faktor 6 höher bei hoher Monotony + hohem Strain. Die Mechanik ist wahrscheinlich Immuntoleranz (gleicher Reiz) vs. Überlastung (hohe Gesamtlast). Gute Trainingsprogramme variieren bewusst die Intensität und modality.',
                sources: [
                    { label: 'Foster C (1998): Monitoring Training in Athletes — Med Sci Sports Exerc 30(7)', url: 'https://pubmed.ncbi.nlm.nih.gov/9694869/' },
                    { label: 'Halson SL (2014): Monitoring Training Load to Enhance Performance — Curr Opin Clin Nutr Metab Care', url: 'https://pubmed.ncbi.nlm.nih.gov/24979864/' },
                ],
                eli5: 'Wenn du 7 Tage lang immer die gleiche Trainingsart mit der gleichen Intensität machst, wird dein Körper überlastet — nicht weil es zu viel ist, sondern weil die Reizvariation fehlt. Ein Schwimmer, der nur Tempotraining macht, bekommt eher Infekte als einer, der Temposchwimmen, Fondo und Sprintblöcke abwechselt.',
            };
        },
    },

    'spo2-trend': {
        title: 'SpO₂ Trend & Schlafapnoe-Flag',
        section: 'Garmin-Daten',
        async fetch() {
            const [insights, daily] = await Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/daily?days=30').then(r => r.json()),
            ]);
            return { insights, daily };
        },
        render(data) {
            const d = data.insights['spo2_trend'];
            if (!d || d.mean_spo2 == null) return { value: '—', sub: 'Keine SpO₂-Daten', kpis: [] };
            const trendIcon = d.trend === 'falling' ? '📉' : d.trend === 'rising' ? '📈' : '➡️';
            const apnea = d.apnea_flag ? '⚠️ Flag aktiv' : '✓ Normal';
            return {
                value: d.mean_spo2.toFixed(1) + ' %',
                sub: `${trendIcon} ${d.trend} · ${apnea}`,
                kpis: [
                    { label: 'Ø SpO₂ (7d)',       value: d.mean_spo2.toFixed(1) + ' %' },
                    { label: 'Min SpO₂',         value: d.min_spo2_7d + ' %' },
                    { label: '7d Trend',         value: d.slope > 0 ? '+' + d.slope.toFixed(2) : d.slope.toFixed(2) + ' %/Tag' },
                    { label: 'Nächte <90 %',     value: d.apnea_nights + ' / ' + d.n_days },
                ],
                formula: [
                    ['SpO₂ Durchschnitt', 'mean(daily_avg_spo2) letzte 7 Nächte'],
                    ['Linear Trend',      'Steigung der SpO₂-Kurve (% pro Tag)'],
                    ['Apnoe-Flag',        'True wenn ≥ 2 Nächte mit min_spo2 < 90 %'],
                    ['Fallendes SpO₂',    'slope < −0.2 → mögl. Erkrankung oder Altitude-Effekt'],
                    ['Steigendes SpO₂',   'slope > 0.2 → Adaptierung oder Besserung'],
                ],
                science: d.apnea_flag
                    ? '<strong style="color:var(--red)">Disclaimer:</strong> Dieses Flag ist ein Hinweis, kein Befund. Obstruktive Schlafapnoe (OSA) erfordert eine Polysomnographie-Diagnose durch einen Pneumologen. Mögliche Ursachen für wiederholte nächtliche Desaturationen: OSA, Höhe, COPD, kardiale Stauung. Konsultiere deinen Arzt.'
                    : 'SpO₂ während des Schlafs reflektiert die Ventilations-Oxygenierung. Stetig fallende SpO₂ über mehrere Tage kann auf eine akute Erkrankung (Atemwegs-Infektion, Pneumonie) oder Höhenadaption hinweisen. Kapur et al. (2017) nutzen wiederholte Desaturationen < 90 % als Screening-Kriterium für OSA — erfordert aber formale Diagnose.',
                sources: [
                    { label: 'Kapur VK, et al. (2017): Clinical Guidelines for Sleep Apnea Diagnosis — J Clin Sleep Med 13(3):479–504', url: 'https://pubmed.ncbi.nlm.nih.gov/28162137/' },
                    { label: 'Duce BR et al. (1986): Nocturnal Oxygen Desaturation in COPD — Chest 88(3):346–350', url: 'https://pubmed.ncbi.nlm.nih.gov/3698677/' },
                ],
                eli5: 'Nachts sollte dein SpO₂ stabil bei 95–100 % bleiben. Wenn es regelmäßig unter 90 % fällt oder über mehrere Tage sinkt, kann das auf Schlafapnoe oder eine Erkrankung hindeuten. Das System zeigt dir den Trend — ein Arzt macht die Diagnose.',
            };
        },
    },

    'sleep-consistency': {
        title: 'Sleep Consistency Score',
        section: 'Schlaf',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=30').then(r => r.json()),
            ]);
            return { insights, history };
        },
        render(data) {
            const d = data.insights['sleep_consistency'];
            if (!d || d.score == null) return { value: '—', sub: 'Zu wenig Schlaf-Daten', kpis: [] };
            const quality = d.score >= 80 ? '✓ Ausgezeichnet' : d.score >= 70 ? '✓ Gut' : d.score >= 60 ? '⚠️ Akzeptabel' : '⚠️ Schlecht';
            return {
                value: d.score.toFixed(0),
                sub: quality,
                kpis: [
                    { label: 'σ Aufwachzeit',     value: d.std_wake_h.toFixed(2) + ' h' },
                    { label: 'σ Einschlafzeit',   value: d.std_sleep_h.toFixed(2) + ' h' },
                    { label: 'Nächte gemessen',   value: d.n_nights },
                    { label: 'Ziel-Varianz',      value: '< 30 min = Score ~90' },
                ],
                formula: [
                    ['Sleep Consistency', 'Score = 100 − (σ_wake × 15 + σ_sleep × 10)'],
                    ['σ_wake',            'Standardabw. von Aufwachzeiten (zirkulär, in Stunden)'],
                    ['σ_sleep',           'Standardabw. von Einschlafzeiten (zirkulär, in Stunden)'],
                    ['Zirkuläre Stat.',   'Berücksichtigt Wrap-around Mitternacht (23:45 ≠ 00:15)'],
                    ['Optimal',           '< 30 min Varianz in beiden = Score 90+'],
                ],
                science: 'Phillips et al. (2017) zeigten in 500+ College-Studierenden: Individuen mit hoher Varianz in Sleep-Onset und Wake-Time hatten signifikant schlechtere akademische Leistungen und mehr psychische Symptome — unabhängig von durchschnittlicher Schlafdauer. Dies ist das „Social Jet Lag"-Phänomen (Wittmann et al., Chronobiology Int.). Der Effekt ist wahrscheinlich circadian dysregulation: dein Körper kann seine Rhythmen nicht stabil halten, was Melatonin, Cortisol und Metabolismus durcheinander bringt.',
                sources: [
                    { label: 'Phillips AJ et al. (2017): Irregular Sleep Patterns and Academic Performance — Sci Rep 7:3216', url: 'https://pubmed.ncbi.nlm.nih.gov/28596593/' },
                    { label: 'Wittmann M et al. (2006): Social Jetlag and Obesity — Curr Biol 16(6):R187–188', url: 'https://pubmed.ncbi.nlm.nih.gov/16616641/' },
                    { label: 'West AC et al. (2019): Circadian Timing of Sleep — Nat Commun 10:5381', url: 'https://pubmed.ncbi.nlm.nih.gov/31772184/' },
                ],
                eli5: 'Wenn du eine Nacht um 22 Uhr schlafen gehst, die nächste um 00:30, und dann wieder um 23:15, „weiß" dein Körper nicht, was los ist. Dein Hirn versucht, zirkadianen Rhythmus stabil zu halten — ständiger Jet Lag verwirrt dein Melatonin und deine Fitness-Anpassungen. Regelmäßig schlafen gehen und aufstehen (auch am Wochenende) ist einer der stärksten Hebel für Schlafqualität und Gesundheit.',
            };
        },
    },

    'body-battery-custom': {
        title: 'Body Battery (Custom)',
        section: 'Energie',
        async fetch() {
            const [insights, history, daily] = await Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=30').then(r => r.json()),
                fetch('/api/daily?days=30').then(r => r.json()),
            ]);
            return { insights, history, daily };
        },
        render(data) {
            const d = data.insights['body_battery_custom'];
            if (!d || d.score == null) return { value: '—', sub: 'Zu wenig Daten', kpis: [] };
            const color = d.score >= 75 ? '✓ Gute Energie' : d.score >= 40 ? '⚠️ Ausreichend' : '❌ Erschöpft';
            const hist = data.history.body_battery_custom || [];
            return {
                value: Math.round(d.score),
                sub: color,
                kpis: [
                    { label: 'Erholung', value: d.recovery + ' (+ Recovery)' },
                    { label: 'Aktivitäts-Drain', value: d.activity_drain + ' (−)' },
                    { label: 'Stress-Drain', value: d.stress_drain + ' (−)' },
                    { label: 'Schlaf letzte Nacht', value: d.sleep_h + ' h' },
                ],
                chart: {
                    title: '30-Tage-Verlauf',
                    type: 'line',
                    labels: hist.map(d => fmtDate(d.date)),
                    datasets: [
                        { label: 'Custom Score', data: hist.map(d => d.value), borderColor: '#f59e0b', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
                        { label: 'Garmin Wert', data: data.daily.map(d => d.body_battery_high), borderColor: '#94a3b8', backgroundColor: 'transparent', tension: 0.3, borderDash: [4, 4], pointRadius: 0 },
                    ],
                    scales: { y: { beginAtZero: true, max: 100 } },
                },
                formula: [
                    ['Formel', 'Energie = Vortag + Recovery − Activity-Drain − Stress-Drain'],
                    ['Recovery', '+30 × (Schlaf/7h) × (HRV/Baseline)'],
                    ['Activity-Drain', 'min(40, TRIMP × 0.5)'],
                    ['Stress-Drain', 'max(0, (avg_stress − 25) × 0.2)'],
                    ['Bereich', 'Clamped [5..100]'],
                    ['─── Parameter', ''],
                    ['Aus Literatur', 'Banister (1991) Impulse-Response · Kellmann (2001) Recovery-Konzept'],
                    ['Heuristisch', '+30 Recovery-Max · ×0.5 Activity-Drain · ×0.2 Stress-Drain'],
                ],
                science: 'Das Energie-Budget basiert auf Banister\'s Impulse-Response-Modell (1991): Training ist ein Impuls, der Adaptationen (Fitness) und Ermüdung (Fatigue) auslöst. Erholung (Recovery) wird über Schlafqualität (Dauer × HRV-Ratio) gemessen; Trainings-Stress über TRIMP (Training-Impulse). Die Parameter sind heuristische Kalibrationen, nicht aus RCTs.',
                sources: [
                    { label: 'Banister EW (1991): Modeling Elite Athletic Performance — Modeling Human Performance', url: 'https://pubmed.ncbi.nlm.nih.gov/1751282/' },
                    { label: 'Kellmann M (2001): Recovery and Overtraining — Sports Medicine 31(11)', url: 'https://pubmed.ncbi.nlm.nih.gov/11735321/' },
                    { label: 'HRV-Recovery-Ratio in Endurance Sports — Current Sports Medicine Reports', url: 'https://pubmed.ncbi.nlm.nih.gov/25226276/' },
                ],
                eli5: 'Dein Körper ist wie eine Batterie. Schlaf und gute HRV laden die Batterie auf. Intensives Training und Stress entladen sie. Dieser Score verfolgt dein Energie-Budget täglich und zeigt, ob du erholungsbedürftig bist oder voll geladen ins nächste Training gehen kannst.',
            };
        },
    },

    'stress-score-custom': {
        title: 'Stress Score (Custom)',
        section: 'Energie',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=30').then(r => r.json()),
            ]);
            return { insights, history };
        },
        render(data) {
            const d = data.insights['stress_score_custom'];
            if (!d || d.score == null) return { value: '—', sub: 'HRV-Daten fehlen', kpis: [] };
            const level = d.score < 30 ? '✓ Niedrig' : d.score < 60 ? '⚠️ Mittel' : '❌ Hoch';
            const hist = data.history.stress_score_custom || [];
            return {
                value: d.score.toFixed(0),
                sub: level,
                kpis: [
                    { label: 'HRV-Komponente', value: d.hrv_component.toFixed(0) },
                    { label: 'Garmin avg_stress', value: d.garmin_stress != null ? d.garmin_stress.toFixed(0) : '—' },
                    { label: 'HRV-Abweichung', value: d.hrv_deviation.toFixed(2) + ' σ' },
                    { label: 'Daten (97d)', value: d.n_hrv + ' Nächte' },
                ],
                chart: {
                    title: '30-Tage-Verlauf',
                    type: 'line',
                    labels: hist.map(d => fmtDate(d.date)),
                    datasets: [
                        { label: 'Stress Score', data: hist.map(d => d.value), borderColor: '#ef4444', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
                    ],
                    scales: { y: { beginAtZero: true, max: 100 } },
                },
                formula: [
                    ['Blending', 'Score = HRV-Komponente × 0.6 + Garmin avg_stress × 0.4'],
                    ['HRV-Component', '50 − (ln(HRV_today) − μ) / σ × 20'],
                    ['μ, σ', 'Mittel und Standardabw. von ln(HRV), letzte 97 Tage'],
                    ['Höhere HRV', '→ Niedrigerer Score (Erholung)'],
                    ['─── Parameter', ''],
                    ['Aus Literatur', 'Task Force ESC/NASPE (1996) HRV-Standarisierung · Shaffer (2017) ln(HRV) Normalisierung'],
                    ['Heuristisch', '60/40-Blend HRV/Garmin · ×20 Skalierungsfaktor'],
                ],
                science: 'Die logarithmische Transformation von HRV (ln RMSSD) ist eine Standard-Normalisierungstechnik (Task Force 1996, Shaffer 2017) für nicht-Gaußsche RMSSD-Verteilungen. Z-Scores nach ln-Transformation ermöglichen Vergleiche über Zeit ohne Abhängigkeit vom absoluten Niveau. Der 60/40-Blend kombiniert parasympathische Aktivität (HRV) mit sympathischen Markernen (Garmin avg_stress) — beide widerspiegeln autonome Balance, sind aber statistisch unabhängig.',
                sources: [
                    { label: 'Task Force ESC/NASPE (1996): HRV Standards — Circulation 93(5)', url: 'https://www.ahajournals.org/doi/10.1161/01.CIR.93.5.1043' },
                    { label: 'Shaffer F, Ginsberg JP (2017): An Overview of HRV — Frontiers Pub Health', url: 'https://www.frontiersin.org/articles/10.3389/fpubh.2017.00258/full' },
                    { label: 'Plews DL et al. (2013): Comparison of HRV Variants — IJSPP 8(6)', url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/' },
                ],
                eli5: 'Ein hoher Stress Score bedeutet: dein Nervensystem ist aktiviert (hohe Herzfrequenzvariabilität ist schlecht = hoher Stress). Gemessen wird das über HRV-Abweichung von deinem 97-Tage-Durchschnitt. Ein Score unter 30 = du bist entspannt. Über 60 = dein Körper ist in Kampf-oder-Flucht-Modus. Das kombiniert auch Garmins Stressmarker (sympathische Aktivität).',
            };
        },
    },

    'running-economy': {
        title: 'Running Economy',
        section: 'Aktivität',
        async fetch() {
            const [insights, history] = await Promise.all([
                fetch('/api/ml-insights').then(r => r.json()),
                fetch('/api/ml-history?days=30').then(r => r.json()),
            ]);
            return { insights, history };
        },
        render(data) {
            const d = data.insights['running_economy'];
            if (!d || d.score == null) return { value: '—', sub: 'Keine Lauf-Daten mit Biomechanik', kpis: [] };
            const quality = d.score >= 80 ? '✓ Ausgezeichnet' : d.score >= 60 ? '✓ Gut' : d.score >= 40 ? '⚠️ Verbesserbar' : '⚠️ Suboptimal';
            const hist = data.history.running_economy || [];
            return {
                value: d.score.toFixed(0),
                sub: quality + ' · Nur Laufen',
                kpis: [
                    { label: 'GCT', value: d.avg_gct_ms + ' ms (Ziel: 200)' },
                    { label: 'VO', value: d.avg_vo_mm.toFixed(1) + ' mm (Ziel: 60)' },
                    { label: 'VR', value: d.avg_vr_pct.toFixed(1) + '% (Ziel: 6)' },
                    { label: 'Ø der letzten', value: d.n_activities + ' Läufe' },
                ],
                chart: {
                    title: '30-Tage-Verlauf',
                    type: 'line',
                    labels: hist.map(d => fmtDate(d.date)),
                    datasets: [
                        { label: 'Running Economy', data: hist.map(d => d.value), borderColor: '#06b6d4', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2 },
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
                    ['Aus Literatur', 'Moore IS (2016) Runner\'s Injury Etiology · Cavanagh PE (1985) Biomechanics of Distance Running'],
                    ['Heuristisch', 'Gewichte 40/35/25% · Lineare Scoring-Funktion'],
                ],
                science: 'Ground Contact Time (GCT), Vertical Oscillation (VO) und Vertical Ratio (VR) sind Biomechanik-Marker aus Garmin Lauf-Dynamik. Moore (2016) et al. zeigten in 188 Läufern, dass GCT > 260ms und hohe VO mit Knieverletzungen assoziiert sind. Die Optima (200ms GCT, 60mm VO, 6% VR) basieren auf Meta-Analysen von Distanzläufern ohne Verletzungsgeschichte (Fletcher et al. 2009, Cavanagh 1985). Die Gewichtung (40/35/25) reflektiert relative Validität in der Literatur.',
                sources: [
                    { label: 'Moore IS et al. (2016): Runner\'s Injury Etiology Review — J Sports Sci 34(6):504–516', url: 'https://pubmed.ncbi.nlm.nih.gov/26061909/' },
                    { label: 'Cavanagh PR (1985): Biomechanics of Distance Running — Human Kinetics', url: 'https://scholar.google.com/scholar?q=cavanagh+1985+biomechanics+distance' },
                    { label: 'Fletcher JR et al. (2009): Ground Reaction Force Predictors of Injury — Sports Medicine 39(10)', url: 'https://pubmed.ncbi.nlm.nih.gov/19757861/' },
                ],
                eli5: 'Beim Laufen brauchst du guten Kontakt mit dem Boden. Zu lange Bodenkontakt (>240ms) bedeutet, du drückst zu lange ab und verschwendest Energie. Zu viel Auf-und-Ab (hohes VO) belastet deine Knöchel und Knie. Ideale Werte: schneller Fuß-Kontakt, geringe vertikale Bewegung (effiziente Kraftübertragung). Dieser Score zeigt, ob dein Lauf-Stil ökonomisch ist.',
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
};

async function load() {
    const name = location.pathname.split('/').pop();
    const def = METRICS[name];
    if (!def) { location.href = '/dashboard'; return; }

    document.getElementById('metric-section').textContent = def.section;
    document.getElementById('metric-title').textContent = def.title;
    document.title = `PulseBase — ${def.title}`;

    try {
        const data = await def.fetch();
        const result = def.render(data);

        document.getElementById('metric-value').innerHTML = result.value;
        if (result.sub) document.getElementById('metric-sub').textContent = result.sub;

        if (result.kpis?.length) {
            document.getElementById('metrics-kpis').innerHTML = result.kpis.map(k => `
                <div class="metrics-kpi-tile card">
                    <div class="metrics-kpi-label">${k.label}</div>
                    <div class="metrics-kpi-value">${k.value}</div>
                </div>
            `).join('');
        }

        if (result.chart) {
            document.getElementById('chart-card').style.display = '';
            document.getElementById('chart-title').textContent = result.chart.title;
            new Chart(document.getElementById('metrics-chart'), {
                type: result.chart.type,
                data: { labels: result.chart.labels, datasets: result.chart.datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    plugins: { legend: { display: (result.chart.datasets?.length ?? 0) > 1 } },
                    scales: result.chart.scales || (result.chart.type === 'bar'
                        ? { y: { beginAtZero: true } }
                        : { y: { beginAtZero: false } }),
                },
            });
        }

        if (result.eli5) {
            document.getElementById('eli5-card').style.display = '';
            document.getElementById('eli5-text').textContent = result.eli5;
        }

        if (result.formula?.length || result.science) {
            document.getElementById('formula-card').style.display = '';
            if (result.science) {
                const sciEl = document.getElementById('science-text');
                sciEl.textContent = result.science;
                sciEl.style.display = '';
            }
            if (result.formula?.length) {
                document.getElementById('formula-content').innerHTML =
                    `<div class="formula-table">${result.formula.map(([k, v]) =>
                        `<div class="formula-row"><strong>${k}</strong><span>${v}</span></div>`
                    ).join('')}</div>`;
            }
        }

        if (result.sources?.length) {
            document.getElementById('sources-card').style.display = '';
            document.getElementById('sources-list').innerHTML = result.sources.map(s =>
                `<li><a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.label}</a></li>`
            ).join('');
        }
    } catch (err) {
        document.getElementById('metric-value').textContent = 'Fehler beim Laden';
        console.error('metrics load error:', err);
    }
}

load();
