/* PulseBase /help — inline content catalog + client-side search */

/* eslint-disable */

// Evidence metadata from API
let _ev = {};

// ── HELP_CATALOG ──────────────────────────────────────────────────────────────
// Each entry: { title, metricName (→ /metrics/<name>), eli5, formula, science, sources }
// metricName is also the evidence key for /api/evidence lookup.
// Grouped by display category for the help page.

const HELP_GROUPS = [
    {
        label: 'Erholung',
        articles: [
            {
                key: 'energy_autonomic',
                metricName: 'autonomic',
                title: 'Autonome Energie (HRV-Baseline)',
                eli5: 'Wir vergleichen dein HRV nur mit DEINEM eigenen Normalwert. Score 70 = dein HRV ist genau auf deiner persönlichen Baseline — das ist gut, nicht mittelmäßig! Score 85+ = du bist heute deutlich erholter als üblich. Score unter 40 = dein HRV ist ungewöhnlich niedrig. Das ist aussagekräftiger als ein absoluter Wert, weil jeder Mensch seinen eigenen HRV-Normalbereich hat.',
                formula: [
                    ['Normierung', 'ln(HRV) — logarithmische Transformation für Normalverteilung'],
                    ['Baseline', 'Gleitendes Mittel μ und Stdabw σ über 90 Tage (min. 20 Messpunkte)'],
                    ['Z-Score', 'z = (ln(HRVₜ) − μ₉₀) / σ₉₀'],
                    ['Score', 'Score = 70 + z × 15  (geclampt 0–100)'],
                    ['Anker z = 0 → 70', 'Altini & Plews (2021): Baseline-HRV = normaler Erholungsstatus'],
                    ['Anker z = ±1σ → 85/55', 'Buchheit (2014): Smallest Worthwhile Change ≈ 1σ'],
                ],
                science:
                    'Absolute HRV-Werte sind interindividuell extrem variabel (RMSSD 20–100 ms normal bei Ausdauersportlern), aber intraindividuell stabil. Die ln-Transformation normalisiert die rechtsschiefe RMSSD-Verteilung — nach der Transformation ist der z-Score-Raum annähernd gaußisch, weshalb ein lineares Mapping statistisch korrekt ist. Die Score-Konstante (70 statt 50) ist literaturverankert: Altini & Plews (2021) zeigen, dass Baseline-HRV den Normalzustand beschreibt, nicht die Untergrenze.',
                sources: [
                    {
                        label: 'Plews et al. (2013): HRV in Elite Endurance Athletes',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/',
                    },
                    {
                        label: 'Buchheit (2014): Monitoring Recovery with HRV',
                        url: 'https://bjsm.bmj.com/content/48/4/243',
                    },
                ],
            },
            {
                key: 'energy_cognitive',
                metricName: 'cognitive',
                title: 'Kognitive Energie (Schlafschuld)',
                eli5: 'Jede Nacht mit zu wenig Schlaf packt dir Gewichte in einen unsichtbaren Rucksack. Der Rucksack macht es schwerer, klar zu denken und Entscheidungen zu treffen. Score 100 = leerer Rucksack. Score 27 heißt, du trägst ca. 10h Schlafschuld mit dir. Zwei gute Nächte hintereinander können das schon merklich verbessern.',
                formula: [
                    ['Ziel', '7h Schlaf pro Nacht (NSF-Empfehlung Erwachsene, untere Grenze)'],
                    ['Debt/Nacht', 'max(0, 7h − tatsächlicher Schlaf)'],
                    ['Gesamt-Debt', 'Σ der letzten 7 Nächte'],
                    ['Score', 'Score = 100 − Debt × 6  (0 bei 16.7h kumulativer Schuld)'],
                ],
                science:
                    'Borbélys Zwei-Prozess-Modell (1982) ist das einflussreichste Modell der Schlafregulation. Chronische Schlafrestriktion (< 7h) akkumuliert kognitive Schulden ohne subjektives Bewusstsein: Van Dongen et al. (2003) zeigten, dass Probanden mit 6h Schlaf nach 14 Tagen kognitive Defizite auf dem Niveau von 24h totalem Schlafentzug aufwiesen.',
                sources: [
                    {
                        label: 'Borbély (1982): Two-Process Model of Sleep Regulation',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/7185792/',
                    },
                    {
                        label: 'Van Dongen et al. (2003): Cumulative Sleep Restriction',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/12683469/',
                    },
                ],
            },
            {
                key: 'body_battery_custom',
                metricName: 'body-battery-custom',
                title: 'Body Battery (Custom)',
                eli5: 'Stell dir deinen Akku vor: Jeden Morgen startest du neu — basierend darauf wie gut du geschlafen hast (Tiefschlaf + REM zählen mehr als bloße Stunden) und wie erholt dein Nervensystem laut HRV ist. Training und Stress verbrauchen Energie. 30% Trägheit vom Vortag verhindert, dass der Wert täglich wild springt.',
                formula: [
                    ['Schlafqualität', '0.40 × (total_h / 7.5) + 0.60 × (0.55 × deep_score + 0.45 × rem_score)'],
                    ['deep_score', 'min(1, (deep_h / total_h) / 0.20)  — Ziel: 20% Tiefschlaf (Walker 2017)'],
                    ['rem_score', 'min(1, (rem_h / total_h) / 0.25)   — Ziel: 25% REM (Dijk & Czeisler 1995)'],
                    ['HRV-Faktor', 'min(1, hrv_last_night / hrv_baseline_30d)'],
                    ['Fresh State', '40 + sleep_quality × 35 + hrv_factor × 25  (max 100 bei Idealwerten)'],
                    ['Score', '0.30 × prev + 0.70 × fresh − activity_drain − stress_drain'],
                ],
                science:
                    'Das Fresh-State-Modell (v2, Mai 2026) ersetzt das frühere Banister-Akkumulationsmodell, das bei mehrtägiger Ruhe zu Plateaus bei 100 führte (Scientific Reports 2025: fundamentale statistische Mängel des FFM). Schlafphasen sind primärer Erholungsindikator: Tiefschlaf (SWS) für physische Erholung, REM für kognitive Erholung.',
                sources: [
                    {
                        label: 'Walker M (2017): Why We Sleep — sleep stage targets',
                        url: 'https://www.simonandschuster.com/books/Why-We-Sleep/Matthew-Walker/9781501144325',
                    },
                    {
                        label: 'Flaws in fitness-fatigue model. Sci Rep (2025)',
                        url: 'https://doi.org/10.1038/s41598-025-88153-7',
                    },
                ],
            },
            {
                key: 'stress_score_custom',
                metricName: 'stress-score-custom',
                title: 'Autonomer Stressindex',
                eli5: "Der Autonome Stressindex misst, wie angespannt dein Nervensystem gerade ist. Gemessen wird das über HRV-Abweichung von deinem 97-Tage-Durchschnitt. Ein Score unter 30 = du bist entspannt. Über 60 = dein Körper ist in Kampf-oder-Flucht-Modus. Garmin's eigener Stress-Wert fließt zu 25% ein — er ist aber selbst HRV-basiert, daher niedrig gewichtet.",
                formula: [
                    ['Blending', 'Score = HRV-Komponente × 0.75 + Garmin avg_stress × 0.25'],
                    ['HRV-Component', '50 − (ln(HRV_today) − μ) / σ × 20'],
                    ['μ, σ', 'Mittel und Standardabw. von ln(HRV), letzte 97 Tage'],
                ],
                science:
                    'Die logarithmische Transformation von HRV (ln RMSSD) ist eine Standard-Normalisierungstechnik. Z-Scores nach ln-Transformation ermöglichen Vergleiche über Zeit ohne Abhängigkeit vom absoluten Niveau. Der 75/25-Blend gewichtet HRV stärker, da Garmins avg_stress ebenfalls HRV-basiert ist und eine 60/40-Teilung das Signal doppelt zählen würde.',
                sources: [
                    {
                        label: 'Task Force ESC/NASPE (1996): HRV Standards',
                        url: 'https://www.ahajournals.org/doi/10.1161/01.CIR.93.5.1043',
                    },
                    {
                        label: 'Shaffer F, Ginsberg JP (2017): An Overview of HRV',
                        url: 'https://www.frontiersin.org/articles/10.3389/fpubh.2017.00258/full',
                    },
                ],
            },
        ],
    },
    {
        label: 'Training & Kapazität',
        articles: [
            {
                key: 'energy_physical',
                metricName: 'physical',
                title: 'Physische Energie (TRIMP / ATL · CTL · TSB)',
                eli5: 'Denk an ein Sparkonto: Jedes Training hebt Geld ab (ATL = kurzfristige Erschöpfung). Regelmäßiges Training über Monate baut Zinsen auf (CTL = Fitness-Basis). TSB ist dein Kontostand: positiv = ausgeruht und fit, negativ = müde. Score 72 heißt "ausgeglichen" — das ist gut! Problematisch wird es erst unter −30.',
                formula: [
                    ['HRr (Heart Rate Reserve)', 'HRr = (HR − RHR) / (HRmax − RHR)'],
                    ['TRIMP', 'Dauer(min) × HRr × (HRr × 4 + 1)'],
                    ['ATL (τ=7d)', 'ATLₜ = ATLₜ₋₁ × e^(−1/7) + TRIMPₜ × (1 − e^(−1/7))'],
                    ['CTL (τ=42d)', 'CTLₜ = CTLₜ₋₁ × e^(−1/42) + TRIMPₜ × (1 − e^(−1/42))'],
                    ['TSB', 'TSB = CTL − ATL'],
                    ['Score', 'Score = 72 + TSB × 1.5  (geclampt 0–100)'],
                ],
                science:
                    'Das Banister-Impuls-Antwort-Modell (1991) modelliert Fitness als Differenz zweier exponentieller Glättungsfilter. TSB = 0 ergibt Score 72 ("ausgeglichen ist gut"), nicht 50. Die Scoring-Konstante ist literaturverankert aus Busso (2003) und Friel/TrainingPeaks.',
                sources: [
                    {
                        label: 'Fitness–Fatigue Model (Banister 1991)',
                        url: 'https://en.wikipedia.org/wiki/Fitness%E2%80%93fatigue_model',
                    },
                    {
                        label: 'Busso (2003): Variable Dose-Response Model',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/12783043/',
                    },
                ],
            },
            {
                key: 'training_effect_custom',
                metricName: 'training-effect',
                title: 'Training Effect (Banister TRIMP-basiert)',
                eli5: 'Eine Zahl von 0 bis 5, die zeigt wie intensiv deine letzte Einheit war — im Verhältnis zu deiner aktuellen Fitness. 1–2 = leichter Reiz. 3 = guter Trainingsreiz. 4+ = sehr intensiv oder überbelastend. Berechnet aus TRIMP (Herzfrequenz × Zeit) gegen deine CTL-Basis.',
                formula: [
                    ['TRIMP', 'Banister-Modell (HRr × Dauer × exp-Faktor)'],
                    ['Effect', 'atan(TRIMP / CTL × k) × 5/π  (normiert 0–5)'],
                    ['k', 'Skalierungsfaktor kalibriert auf Garmin-Referenz-Skala'],
                ],
                science:
                    'Skalierung des TRIMP auf Trainingseffekt 0–5 via atan gegen persönliche CTL-Baseline. Methode basiert auf Banister-Modell und EPOC-Proxy-Validierung über Esteve-Lanao et al.',
                sources: [
                    {
                        label: 'Morton RH et al. (1990): J Appl Physiol 69(3)',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/2246154/',
                    },
                    {
                        label: 'Esteve-Lanao J et al. (2005): Med Sci Sports Exerc',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/16260977/',
                    },
                ],
            },
            {
                key: 'training_monotony',
                metricName: 'training-monotony',
                title: 'Training Monotony & Strain',
                eli5: 'Wenn du jeden Tag gleich viel trainierst (keine Variation), steigt die Monotonie. Hohe Monotonie (>2.0) erhöht das Übertrainings- und Krankheitsrisiko. Abwechslung zwischen harten und leichten Tagen hält die Monotonie niedrig. Strain = Monotony × Wochenvolumen.',
                formula: [
                    ['Monotony', 'Ø TRIMP / Stdabw TRIMP (letzte 7 Tage)'],
                    ['Strain', 'Σ TRIMP × Monotony'],
                    ['Grenzwert', 'Monotony > 2.0 → erhöhtes Risiko (Foster 1998)'],
                ],
                science:
                    'Foster (1998) zeigte, dass hohe Training Monotony (>2.0) mit erhöhter Infektanfälligkeit und Übertrainings-Symptomen korreliert. Mehrfach repliziert in Ausdauer- und Teamsport-Settings.',
                sources: [
                    {
                        label: 'Foster C (1998): Med Sci Sports Exerc 30(7)',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/9662687/',
                    },
                    {
                        label: 'Halson SL (2014): Monitoring Training Load',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/24950796/',
                    },
                ],
            },
            {
                key: 'intensity_minutes_custom',
                metricName: 'intensity-minutes',
                title: 'Intensitätsminuten (Karvonen-Methode)',
                eli5: 'Garmin zählt Intensitätsminuten nach einem fixen Pulsgrenzwert — egal wie fit du bist. Karvonen berücksichtigt deinen Ruhepuls: Wenn dein Herz in Ruhe sehr langsam schlägt (gute Fitness), muss es bei gleicher Anstrengung weniger schlagen. Die Formel normalisiert das und gibt dir eine faire Einschätzung.',
                formula: [
                    ['HRR (Karvonen)', 'HRr = (HR − Ruhepuls) / (HRmax − Ruhepuls)'],
                    ['Moderat', '0.50 ≤ HRr < 0.70'],
                    ['Intensiv', 'HRr ≥ 0.70'],
                    ['WHO-Äquivalent', 'moderat_min + intensiv_min × 2'],
                ],
                science:
                    'Die Karvonen-Methode (Heart Rate Reserve) ist physiologisch präziser als absolute HR-Zonen, da sie Ruhepuls und maximale HR individuell berücksichtigt. WHO empfiehlt 150–300 min moderat oder 75–150 min intensiv pro Woche.',
                sources: [
                    {
                        label: 'Karvonen et al. (1957): Effect of Training on Heart Rate',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/13470504/',
                    },
                    {
                        label: 'WHO (2020): Physical Activity Guidelines',
                        url: 'https://www.who.int/publications/i/item/9789240015128',
                    },
                ],
            },
            {
                key: 'running_economy',
                metricName: 'running-economy',
                title: 'Laufökonomie-Score',
                eli5: 'Misst wie effizient du läufst — anhand von Bodenkontaktzeit, vertikaler Bewegung und Schrittfrequenz. Ein guter Wert bedeutet weniger Energieverschwendung bei gleicher Pace. Wird gegen deine eigene Baseline verglichen, nicht gegen populationsweite Normen.',
                formula: [
                    ['GCT-Score', 'Z-Score von Bodenkontaktzeit vs. Baseline (negativ = gut)'],
                    ['VO-Score', 'Z-Score von vertikaler Oszillation vs. Baseline (negativ = gut)'],
                    ['Score', 'Composite aus GCT + VO + VR, normiert 0–100'],
                ],
                science:
                    'Bodenkontaktzeit, vertikale Oszillation und vertikales Verhältnis sind meta-analytisch als valide Laufökonomie-Indikatoren bestätigt. Moore (2016) systematischer Review: GCT und VO sind die stärksten Prädiktoren.',
                sources: [
                    {
                        label: 'Moore IS (2016): Sports Med 46(6):793–807',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/26816209/',
                    },
                    {
                        label: 'Cavanagh PR, Kram R (1985): Med Sci Sports Exerc',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/4021469/',
                    },
                ],
            },
        ],
    },
    {
        label: 'Schlaf',
        articles: [
            {
                key: 'sleep_score_custom',
                metricName: 'sleep-score-custom',
                title: 'Schlafqualität (Custom)',
                eli5: 'Statt einfach zu sagen wie lange du geschlafen hast, schaut dieser Score auch ob du genug Tiefschlaf (körperliche Erholung) und REM-Schlaf (Träume, emotionale Verarbeitung) hattest. Ein guter Score bedeutet: die richtige Menge und die richtigen Phasen — nicht nur lange im Bett.',
                formula: [
                    ['Tiefschlaf-Score (35%)', 'min(100, Tiefschlaf% / 20% × 100) — Optimum 20%'],
                    ['REM-Score (25%)', 'min(100, REM% / 22% × 100) — Optimum 22%'],
                    ['Dauer-Score (25%)', 'min(100, Stunden / 8 × 100)'],
                    ['Wach-Penalty (15%)', 'max(0, 100 − Wach% × 500)'],
                ],
                science:
                    'Der Custom-Schlaf-Score gewichtet Schlafphasen nach physiologischer Relevanz. Tiefschlaf (SWS) ist für körperliche Erholung kritisch (NSF: 20%). REM-Schlaf reguliert emotionale Verarbeitung und Kreativität (NSF: 22%).',
                sources: [
                    {
                        label: 'Walker (2017): Why We Sleep',
                        url: 'https://www.amazon.de/Why-We-Sleep-Science-Dreams/dp/0141983760',
                    },
                    {
                        label: 'National Sleep Foundation: Sleep Architecture',
                        url: 'https://www.thensf.org/sleep-faqs/what-are-sleep-stages/',
                    },
                ],
            },
            {
                key: 'sleep_consistency',
                metricName: 'sleep-consistency',
                title: 'Schlaf-Konsistenz (Sleep Consistency)',
                eli5: 'Unregelmäßige Schlafenszeiten bringen deine innere Uhr aus dem Takt — auch bekannt als "Social Jet Lag". Dieser Score misst wie konstant deine Ein- und Aufwachzeiten über 14 Nächte sind. Hoher Score = du schläfst und wachst jeden Tag zur ähnlichen Zeit auf.',
                formula: [
                    ['Zirkuläre Varianz', 'σ² der Einschlaf- und Aufwachzeiten (14 Nächte)'],
                    ['Score', '100 × (1 − σ_gesamt / 3h)  (geclampt 0–100)'],
                ],
                science:
                    'Unregelmäßige Schlaf-/Aufwachzeiten korrelieren mit schlechterer kognitiver Leistung und metabolischen Risiken. Phillips (2017) zeigte an 61 Studierenden, dass zirkuläre Varianz der Schlafzeiten akademische Performance vorhersagt.',
                sources: [
                    {
                        label: 'Phillips AJK et al. (2017): Sci Rep 7:3216',
                        url: 'https://www.nature.com/articles/s41598-017-03171-4',
                    },
                    {
                        label: 'Wittmann M et al. (2006): Social Jetlag',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/16537070/',
                    },
                ],
            },
        ],
    },
    {
        label: 'HRV & Autonomes System',
        articles: [
            {
                key: 'hrv_recovery',
                metricName: 'hrv-recovery',
                title: 'HRV Recovery Trajectory',
                eli5: 'Zeigt wie schnell sich deine HRV nach intensivem Training wieder erholt. Schnelle Erholung = gute Adaptation an das Training. Langsame Erholung = du brauchst mehr Regenerationszeit zwischen den Einheiten.',
                formula: [
                    ['Recovery Speed', 'Steigung der HRV-Kurve nach Training-Tagen (lineare Regression)'],
                    ['n Events', 'Anzahl ausgewerteter Trainingstage im 60-Tage-Fenster'],
                ],
                science:
                    'Erholungsgeschwindigkeit der HRV nach Trainingsbelastung als Adaptationsindikator. Plews et al. (2013) und Stanley et al. (2013) zeigen konsistenten Zusammenhang zwischen HRV-Recovery-Speed und Trainingsadaptation.',
                sources: [
                    {
                        label: 'Plews DJ et al. (2013): Sports Med 43(9)',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/',
                    },
                    {
                        label: 'Stanley J et al. (2013): Med Sci Sports Exerc',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23669878/',
                    },
                ],
            },
            {
                key: 'spo2_trend',
                metricName: 'spo2-trend',
                title: 'SpO₂-Trendanalyse',
                eli5: 'Misst den Sauerstoffgehalt deines Blutes während des Schlafs über 7 Nächte. Werte unter 95% deuten auf Atemprobleme hin. Das ist ein Screening-Signal, kein medizinischer Befund — bei wiederholten niedrigen Werten sollte ein Arzt konsultiert werden.',
                formula: [
                    ['Datenbasis', 'Garmin avg_spo2 letzte 7 Nächte'],
                    ['Apnoe-Flag', 'Wird gesetzt wenn min_spo2 < 90% oder Desaturation-Flag von Garmin'],
                    ['Trend', 'Lineare Regression über 7-Tage-Fenster'],
                ],
                science:
                    'Nächtliche SpO2-Desaturationen (<90%) sind etabliertes Screening-Kriterium für obstruktive Schlafapnoe. AASM Clinical Practice Guidelines 2017 empfehlen Pulsoximetrie als initialen Screening-Test.',
                sources: [
                    {
                        label: 'Kapur VK et al. (2017): J Clin Sleep Med 13(3) [AASM]',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/28162150/',
                    },
                    {
                        label: 'Duce B et al. (2014): J Clin Sleep Med',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/24634631/',
                    },
                ],
            },
        ],
    },
    {
        label: 'Screening & Anomalie-Erkennung',
        articles: [
            {
                key: 'anomaly_hr',
                metricName: 'hr-zscore',
                title: 'Ruhepuls-Anomalie (Z-Score)',
                eli5: 'Wir schauen, ob dein heutiger Ruhepuls ungewöhnlich anders ist als dein eigener Normalwert der letzten 30 Tage. Z=0 heißt: genau wie immer. Z=+2 heißt: heute 2 Standardabweichungen höher als normal. Wenn du sonst immer 44bpm hast, aber heute 52bpm, kann das ein frühes Zeichen für eine Erkältung sein — noch bevor du dich krank fühlst.',
                formula: [
                    ['Baseline', 'Gleitendes 30-Tage-Fenster (min. 7 Messpunkte)'],
                    ['Z-Score', 'Z = (HR_heute − μ₃₀) / σ₃₀'],
                    ['Anomalie', '|Z| > 2.0 = Anomalie (≈ äußerste 5% der Normalverteilung)'],
                ],
                science:
                    'Resting Heart Rate ist ein sensitiver Biomarker des autonomen Gleichgewichts: sympathische Aktivierung durch Übertraining, Infektion oder Schlafmangel erhöht RHR messbar vor klinischen Symptomen. Die |Z| > 2.0-Schwelle entspricht den äußersten ≈ 5% einer Normalverteilung. Ein Ausreißer ist ein statistisches Signal, keine Diagnose — einzelne Werte schwanken naturgemäß; der Trend über mehrere Tage ist aussagekräftiger.',
                sources: [
                    {
                        label: 'Achten & Jeukendrup (2003): Heart Rate Monitoring',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/14561293/',
                    },
                    {
                        label: 'Chandola V et al. (2009): ACM Computing Surveys 41(3)',
                        url: 'https://dl.acm.org/doi/10.1145/1541880.1541882',
                    },
                ],
            },
            {
                key: 'anomaly_spo2',
                metricName: 'spo2-trend',
                title: 'SpO₂-Anomalie (Z-Score)',
                eli5: 'Funktioniert wie der Ruhepuls Z-Score, aber für deinen Sauerstoffgehalt im Blut. Erkennt ungewöhnlich niedrige SpO2-Werte im Vergleich zu deiner eigenen Baseline der letzten 30 Tage.',
                formula: [
                    ['Z-Score', 'Z = (SpO2_heute − μ₃₀) / σ₃₀'],
                    ['Anomalie', '|Z| > 2.0'],
                ],
                science:
                    'Z-Score-Abweichung vom persönlichen SpO2-Mittelwert. Methodisch analog zur HR-Anomalie. Optischer Sensor (Garmin) weniger präzise als klinische Pulsoximetrie.',
                sources: [
                    {
                        label: 'Chandola V et al. (2009): Anomaly Detection Survey',
                        url: 'https://dl.acm.org/doi/10.1145/1541880.1541882',
                    },
                ],
            },
        ],
    },
    {
        label: 'ML-Prognosen',
        articles: [
            {
                key: 'readiness_rf',
                metricName: 'readiness-rf',
                title: 'Readiness-Prognose (Random Forest)',
                eli5: 'Ein Machine-Learning-Modell, das ausschließlich auf DEINEN eigenen Daten trainiert wurde. Es schaut welche Biomarker heute (HRV, Schlaf, Ruhepuls etc.) mit deiner morgigen Readiness korrelieren. Mehr Daten = bessere Prognose. Mindestens 30 Datentage nötig.',
                formula: [
                    ['Modell', 'RandomForestRegressor (100 Bäume, scikit-learn)'],
                    [
                        'Features',
                        'HRV letzte Nacht, Sleep Score, Ruhepuls, Aerobic Effect, Anaerobic Effect, Body Battery, avg_stress, ACWR',
                    ],
                    ['Target', 'Readiness Score nächster Tag (autonomic 60% + cognitive 40%)'],
                    ['Konfidenz', '10./90. Perzentil der Baum-Prognosen'],
                ],
                science:
                    'Personalisierter Random Forest ohne populationsbasierter Normierung. Breiman (2001) zeigt, dass RF durch Ensemble-Mittelung über viele Entscheidungsbäume Overfitting reduziert. Mindestens 30 Trainingspaare nötig. Werte können von Tag zu Tag leicht schwanken (Modell-Rauschen und gleitende Baseline) — auf den Trend achten, nicht auf den Einzelwert.',
                sources: [
                    {
                        label: 'Breiman L (2001): Random Forests — Machine Learning 45(1)',
                        url: 'https://link.springer.com/article/10.1023/A:1010933404324',
                    },
                    {
                        label: 'Plews DJ et al. (2013): HRV Feature Basis',
                        url: 'https://pubmed.ncbi.nlm.nih.gov/23539253/',
                    },
                ],
            },
            {
                key: 'battery_pattern',
                metricName: 'battery-pattern',
                title: 'Battery-Muster (k-Means Clustering)',
                eli5: 'Schaut sich an wie deine Body-Battery-Kurve über den Tag verläuft und vergleicht sie mit historischen Mustern. Erkennt drei Typen: "Stabile hohe Energie", "Erholungstag" (morgens niedrig, steigt) und "Erschöpft" (durchgehend niedrig oder schnell abfallend). Wichtig: Das beschreibt dein historisches Muster der letzten Wochen, nicht nur heute!',
                formula: [
                    ['Features', 'Morgenwert, Abendwert, Tagesrange, Fläche unter Kurve, Anzahl Einbrüche'],
                    ['Modell', 'k-Means (k=3, scikit-learn)'],
                    [
                        'Label-Zuweisung',
                        'Höchste AUC + niedrigster Range → stabil_hoch; Höchstes (abend−morgen) → erholung; Rest → erschöpft',
                    ],
                ],
                science:
                    'k-Means-Clustering auf täglichen Body-Battery-Features. Nur 3 Cluster — "erschöpft" ist das Fallback-Label. Das Label kann auch bei hohem Tageswert erscheinen, wenn das historische Kurvenform-Muster nicht zu den anderen Clustern passt.',
                sources: [
                    {
                        label: 'MacQueen JB (1967): k-Means Proceedings',
                        url: 'https://www.semanticscholar.org/paper/Some-Methods-for-Classification-and-Analysis-of-MacQueen/ac8ab51a8604c76df0b2cd93a3b5e60af0b8b72e',
                    },
                ],
            },
        ],
    },
];

// ── Render ────────────────────────────────────────────────────────────────────

function esc(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function renderFormula(rows) {
    if (!rows?.length) return '';
    const items = rows
        .map(([k, v]) => `<div class="formula-row"><strong>${esc(k)}</strong><span>${esc(v)}</span></div>`)
        .join('');
    return `<div class="formula-table help-formula">${items}</div>`;
}

function renderSources(sources) {
    if (!sources?.length) return '';
    const items = sources
        .map((s) => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.label)}</a></li>`)
        .join('');
    return `<ul class="sources-list">${items}</ul>`;
}

function renderArticle(art) {
    const ev = _ev[art.key] ?? {};
    const typeLabels = {
        recovery: 'Erholung',
        capacity: 'Kapazität',
        trend: 'Verlauf',
        prediction: 'Prognose',
        screening: 'Screening',
    };
    const typeBadge = ev.metric_type
        ? `<span class="metric-type-chip type-${esc(ev.metric_type)}">${esc(typeLabels[ev.metric_type] ?? ev.metric_type)}</span>`
        : '';
    const evCls = ev.level === 'meta' ? 'ev-meta' : ev.level === 'replicated' ? 'ev-rep' : 'ev-model';
    const evShort = ev.level === 'meta' ? 'M' : ev.level === 'replicated' ? 'R' : 'E';
    const evBadge = ev.level
        ? `<span class="ev-badge ${evCls}" title="${esc(ev.label ?? ev.level)}: ${esc(ev.name ?? '')}">${evShort}</span>`
        : '';
    const horizon = ev.time_horizon ? `<span class="metric-horizon">${esc(ev.time_horizon)}</span>` : '';

    const intendedUse = ev.intended_use
        ? `<div class="disclosure-block intended"><strong>Wofür:</strong> ${esc(ev.intended_use)}</div>`
        : '';
    const notFor = ev.not_for
        ? `<div class="disclosure-block not-for"><strong>Nicht geeignet für:</strong> ${esc(ev.not_for)}</div>`
        : '';
    const limitations = ev.limitations
        ? `<div class="disclosure-block limitations"><strong>Einschränkungen:</strong> ${esc(ev.limitations)}</div>`
        : '';

    const methodContent = [
        renderFormula(art.formula),
        art.science ? `<p class="help-science-text">${esc(art.science)}</p>` : '',
        renderSources(art.sources),
    ]
        .filter(Boolean)
        .join('');

    return `<article id="${esc(art.key)}" class="card help-article" data-searchtext="${esc(`${art.title} ${art.eli5} ${art.science ?? ''} ${ev.intended_use ?? ''} ${ev.limitations ?? ''}`.toLowerCase())}">
        <div class="help-article-header">
            ${typeBadge}
            <h2>${esc(art.title)}</h2>
            ${evBadge}
        </div>
        ${horizon}
        ${intendedUse}
        ${notFor}
        ${limitations}
        <p class="help-summary">${esc(art.eli5)}</p>
        ${
            methodContent
                ? `<details class="help-details">
                <summary>Methodik &amp; Quellen</summary>
                ${methodContent}
               </details>`
                : ''
        }
        <div class="help-article-footer">
            <a href="/metrics/${esc(art.metricName)}" class="text-sm" style="color:var(--accent-text)">→ Zur Metrik</a>
            <span class="disclosure-disclaimer" style="flex:1;border:none;padding:0;margin:0">Kein Ersatz für ärztliche Beratung · Keine medizinische Diagnose</span>
        </div>
    </article>`;
}

function renderGroups(groups) {
    return groups
        .map((g) => {
            const articles = g.articles.map(renderArticle).join('');
            return `<h2 class="help-group-heading">${esc(g.label)}</h2>${articles}`;
        })
        .join('');
}

// ── Search ────────────────────────────────────────────────────────────────────

function setupSearch() {
    const input = document.getElementById('help-search');
    const noResults = document.getElementById('help-no-results');
    if (!input) return;

    input.addEventListener('input', () => {
        const q = input.value.trim().toLowerCase();

        // Clear hash-filter when user starts searching
        if (q && _filteredByHash) showAllArticles();

        const articles = document.querySelectorAll('.help-article');
        let visibleCount = 0;
        articles.forEach((art) => {
            const text = art.dataset.searchtext ?? '';
            const visible = !q || text.includes(q);
            art.style.display = visible ? '' : 'none';
            if (visible) visibleCount++;
        });
        // Hide section headings if all articles in them are hidden
        document.querySelectorAll('.help-group-heading').forEach((heading) => {
            let sib = heading.nextElementSibling;
            let anyVisible = false;
            while (sib && !sib.classList.contains('help-group-heading')) {
                if (sib.style.display !== 'none') anyVisible = true;
                sib = sib.nextElementSibling;
            }
            heading.style.display = anyVisible ? '' : 'none';
        });
        if (noResults) noResults.style.display = visibleCount === 0 ? '' : 'none';
    });

    // Auto-focus if ?q= param
    const qParam = new URLSearchParams(location.search).get('q');
    if (qParam) {
        input.value = qParam;
        input.dispatchEvent(new Event('input'));
    }
}

// ── Hash navigation ───────────────────────────────────────────────────────────

// Map metric URL names (e.g. "autonomic") → evidence keys (e.g. "energy_autonomic")
// Needed because metric-detail links use the URL name, articles use the evidence key.
const _metricNameToKey = {};
for (const g of HELP_GROUPS) {
    for (const art of g.articles) {
        if (art.metricName) _metricNameToKey[art.metricName] = art.key;
    }
}

let _filteredByHash = false;

function showAllArticles() {
    document.querySelectorAll('.help-article, .help-group-heading').forEach((el) => {
        el.style.display = '';
    });
    const btn = document.getElementById('help-show-all-btn');
    if (btn) btn.remove();
    _filteredByHash = false;
}

function scrollToHash() {
    const hash = location.hash.slice(1);
    if (!hash) return;
    // Resolve metric URL name → evidence key (e.g. "autonomic" → "energy_autonomic")
    const resolvedKey = _metricNameToKey[hash] ?? hash;
    const target = document.getElementById(resolvedKey);
    if (!target) return;

    // When arriving from a metric page, show only that article
    const allArticles = document.querySelectorAll('.help-article');
    if (allArticles.length > 1) {
        allArticles.forEach((art) => {
            art.style.display = art.id === resolvedKey ? '' : 'none';
        });
        document.querySelectorAll('.help-group-heading').forEach((h) => {
            h.style.display = 'none';
        });
        _filteredByHash = true;

        // Add "show all" link above the article
        if (!document.getElementById('help-show-all-btn')) {
            const btn = document.createElement('button');
            btn.id = 'help-show-all-btn';
            btn.className = 'help-show-all-btn';
            btn.textContent = '← Alle Artikel anzeigen';
            btn.addEventListener('click', () => {
                showAllArticles();
                history.replaceState(null, '', '/help');
            });
            target.parentNode.insertBefore(btn, target);
        }
    }

    target.classList.add('help-highlight');
    target.scrollIntoView({ behavior: 'instant', block: 'start' });
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
    try {
        _ev = await fetch('/api/evidence').then((r) => r.json());
    } catch (_) {}

    const container = document.getElementById('help-articles-container');
    if (container) container.innerHTML = renderGroups(HELP_GROUPS);

    setupSearch();
    scrollToHash();
    window.addEventListener('hashchange', scrollToHash);
}

init();
