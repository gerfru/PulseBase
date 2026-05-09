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
                    ['Formel', 'RMSSD = √( Σ(RRn+1 − RRn)² / (N−1) )'],
                    ['Wochenø', 'Arithmetisches Mittel der letzten 7 Nächte'],
                    ['Messung', 'Während Schlaf via optisches Herzfrequenzmessung'],
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
                    ['Edwards TRIMP', 'Σ (Minuten in Herzfrequenzzone × Zonenfaktor), Zonen 1–5 → Faktor 1–5'],
                    ['ATL (τ=7d)', 'ATLₜ = ATLₜ₋₁ × e^(−1/7) + TRIMPₜ × (1 − e^(−1/7))'],
                    ['CTL (τ=42d)', 'CTLₜ = CTLₜ₋₁ × e^(−1/42) + TRIMPₜ × (1 − e^(−1/42))'],
                    ['TSB', 'TSB = CTL − ATL'],
                    ['Score', 'Score = 50 + TSB × 2 (geclampt 0–100)'],
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
                    { label: 'Abweichung', value: dev },
                    { label: 'Persönlicher Baseline', value: baseline },
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
                    ['Soll', '8h Schlaf pro Nacht'],
                    ['Debt/Nacht', 'max(0, 8h − tatsächlicher Schlaf)'],
                    ['Gesamt-Debt', 'Σ der letzten 7 Nächte (max. 14h)'],
                    ['Score', 'Score = 100 × max(0, 1 − Debt / 14h)'],
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
                    { label: 'Z-Score heute', value: zscore },
                    { label: 'Status', value: isAnom ? '⚠ Anomalie' : (anomaly?.z_score != null ? '✓ Normal' : '—') },
                    { label: 'Baseline Ø (30d)', value: anomaly?.baseline_mean ? Math.round(anomaly.baseline_mean) + ' bpm' : '—' },
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
                    ['Features', 'hrv_last_night, sleep_score, resting_hr, training_load_7d'],
                    ['Label', 'Readiness-Score des Folgetages (regelbasiertes Modell)'],
                    ['Training', 'Wöchentlich (Sonntag 3:00 Uhr), min. 30 Datenpunkte erforderlich'],
                    ['Output', 'Prognostizierter Readiness-Score für morgen (0–100)'],
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
                    ['Quelle', 'Garmin-Algorithmus (hrv_daily.hrv_status)'],
                    ['Vergleich', 'HRV letzte Nacht vs. persönliche 3-Wochen-Baseline'],
                    ['BALANCED', 'HRV im Normalbereich → gute Erholung'],
                    ['UNBALANCED', 'HRV leicht außerhalb → erhöhte Belastung oder Stress'],
                    ['LOW / POOR', 'HRV deutlich unter Baseline → Überbelastung oder Erkrankung'],
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

            // Historischen Readiness-Verlauf aus Energie-Komponenten rekonstruieren
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
                    ['Physische Energie', 'Edwards TRIMP + Banister ATL/CTL/TSB → Score (0–100) — Gewicht: 35%'],
                    ['Autonome Energie', 'HRV (RMSSD) ln-normiert, σ-Abweichung von 90d-Baseline — Gewicht: 40%'],
                    ['Kognitive Energie', 'Borbély Process S: Schlafschuld 7d, tiefschlaf-qualitätsjustiert — Gewicht: 25%'],
                    ['Fehlende Komponenten', 'Verbleibende Gewichte werden proportional normiert'],
                    ['Score', 'Gewichtetes Mittel, geclampt 0–100'],
                ],
                eli5: 'Der Readiness-Score kombiniert drei eigene, transparent berechnete Dimensionen. Physisch: Wie viel Trainingsbelastung steckt noch im System? Autonom: Ist dein Nervensystem (HRV) heute besser oder schlechter erholt als dein persönlicher Normalwert? Kognitiv: Wie viel Schlafschuld hast du angehäuft? Alles ohne Garmin-Blackbox — nur unsere eigenen Formeln.',
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

        if (result.formula?.length) {
            document.getElementById('formula-card').style.display = '';
            document.getElementById('formula-content').innerHTML =
                `<div class="formula-table">${result.formula.map(([k, v]) =>
                    `<div class="formula-row"><strong>${k}</strong><span>${v}</span></div>`
                ).join('')}</div>`;
        }

        if (result.eli5) {
            document.getElementById('eli5-card').style.display = '';
            document.getElementById('eli5-text').textContent = result.eli5;
        }
    } catch (err) {
        document.getElementById('metric-value').textContent = 'Fehler beim Laden';
        console.error('metrics load error:', err);
    }
}

load();
