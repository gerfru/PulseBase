"""
Scientific evidence catalog for PulseBase metrics.

Evidence levels:
  meta       — at least one meta-analysis or clinical practice guideline standard
  replicated — multiple independent studies, consistent findings, no formal meta
  model      — PulseBase-specific calibration, literature-informed, not externally benchmarked
"""

EVIDENCE: dict[str, dict] = {
    # ── Training Load ─────────────────────────────────────────────────────────
    "energy_physical": {
        "level": "meta",
        "label": "Meta-Analyse",
        "name": "TRIMP / ATL · CTL · TSB",
        "summary": (
            "Banister TRIMP (Training Impulse) ist der am häufigsten validierte "
            "Ansatz zur Quantifizierung von Trainingsbelastung. ATL/CTL-Modell "
            "über tausende Studien und Meta-Analysen hinweg bestätigt."
        ),
        "refs": [
            "Banister EW (1975). A systems model of training for athletic performance.",
            "Morton RH et al. (1990). J Appl Physiol 69(3):1171–1177",
            "Edwards S (1993). The Heart Rate Monitor Book. Polar Electro",
            "Hellard P et al. (2006). J Strength Cond Res 20(1):113–119 [Meta]",
        ],
        "limitations": (
            "Individuelle HR-Reserven variieren. Kein direkter EPOC-Nachweis; "
            "TRIMP ist ein Proxy, kein Goldstandard für metabolischen Aufwand."
        ),
    },
    "training_monotony": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "Training Monotony & Strain",
        "summary": (
            "Foster (1998) zeigte, dass hohe Training Monotony (>2.0) mit "
            "erhöhter Infektanfälligkeit und Übertrainings-Symptomen korreliert. "
            "Mehrfach repliziert in Ausdauer- und Teamsport-Settings."
        ),
        "refs": [
            "Foster C (1998). Med Sci Sports Exerc 30(7):1164–1168",
            "Halson SL (2014). Curr Opin Clin Nutr Metab Care 17(5):454–459",
        ],
        "limitations": (
            "Optimale Monotony-Schwellenwerte sind nicht universell. "
            "Formel setzt TRIMP-Konsistenz voraus — bei fehlenden Tagen unzuverlässig."
        ),
    },
    "training_effect_custom": {
        "level": "meta",
        "label": "Meta-Analyse",
        "name": "Aerober Trainingseffekt (TRIMP-basiert)",
        "summary": (
            "Skalierung des TRIMP auf Trainingseffekt 0–5 via atan gegen persönliche "
            "CTL-Baseline. Methode basiert auf Banister-Modell (Konsens) und "
            "EPOC-Proxy-Validierung über Esteve-Lanao et al."
        ),
        "refs": [
            "Morton RH et al. (1990). J Appl Physiol 69(3):1171–1177",
            "Esteve-Lanao J et al. (2005). Med Sci Sports Exerc 37(10):1807–1813",
            "Plews DJ et al. (2014). Int J Sports Physiol Perform 9(4):726–730",
        ],
        "limitations": (
            "atan-Skalierung und CTL-Referenzpunkt sind PulseBase-spezifisch, "
            "nicht aus Studien direkt abgeleitet."
        ),
    },
    # ── HRV & Autonomic ───────────────────────────────────────────────────────
    "energy_autonomic": {
        "level": "meta",
        "label": "Meta-Analyse",
        "name": "Autonome Energie (HRV-Baseline)",
        "summary": (
            "HRV als Marker für autonomes Gleichgewicht und Erholungsstatus ist "
            "klinischer Goldstandard seit Task Force 1996. Z-Score gegen persönliche "
            "Baseline ist methodisch stärker als absolute HRV-Normwerte."
        ),
        "refs": [
            "Task Force ESC/NASPE (1996). Eur Heart J 17(3):354–381 [Klinischer Standard]",
            "Plews DJ et al. (2013). Sports Med 43(9):773–781 [Meta, Athleten]",
            "Buchheit M (2014). Int J Sports Physiol Perform 9(4):558–570",
        ],
        "limitations": (
            "Optischer HRV-Sensor (Garmin) ist weniger präzise als EKG-basierte Messung. "
            "Tagesgranularität statt morgendlicher Ruhemessung reduziert Signalqualität."
        ),
    },
    "hrv_recovery": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "HRV Recovery Trajectory",
        "summary": (
            "Erholungsgeschwindigkeit der HRV nach Trainingsbelastung als "
            "Adaptationsindikator. Mehrere Studien zeigen konsistenten Zusammenhang "
            "zwischen HRV-Recovery-Speed und Trainingsadaptation."
        ),
        "refs": [
            "Plews DJ et al. (2013). Sports Med 43(9):773–781",
            "Stanley J et al. (2013). Med Sci Sports Exerc 45(12):2318–2324",
            "Aubert AE et al. (2003). Sports Med 33(12):889–919",
        ],
        "limitations": (
            "Recovery-Trajektorie hängt von Datendichte ab; wenige Trainingseinheiten "
            "pro Woche reduzieren die Aussagekraft."
        ),
    },
    # ── Sleep ─────────────────────────────────────────────────────────────────
    "energy_cognitive": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "Kognitive Energie (Schlafschuld-Modell)",
        "summary": (
            "Kognitive Leistungsfähigkeit degradiert proportional zur akkumulierten "
            "Schlafschuld. Van Dongen (2003) zeigte lineare Verschlechterung bei "
            "chronischer Schlafeinschränkung. Mechanismus physiologisch gut belegt."
        ),
        "refs": [
            "Van Dongen HPA et al. (2003). Sleep 26(2):117–126",
            "Walker MP (2017). Why We Sleep. Scribner.",
            "Dinges DF et al. (1997). Sleep 20(4):267–277",
        ],
        "limitations": (
            "Spezifische Gewichtung und Erholungsformel sind PulseBase-eigene Kalibrierung. "
            "Individuelle Schlafbedürfnisse variieren (7–9h ist Populationsdurchschnitt)."
        ),
    },
    "sleep_consistency": {
        "level": "meta",
        "label": "Meta-Analyse",
        "name": "Sleep Consistency Score",
        "summary": (
            "Unregelmäßige Schlaf-/Aufwachzeiten korrelieren mit schlechterer "
            "kognitiver Leistung, metabolischen Risiken und Social Jet Lag. "
            "Phillips (2017) zeigte an 61 Studierenden, dass zirkuläre Varianz "
            "der Schlafzeiten akademische Performance vorhersagt."
        ),
        "refs": [
            "Phillips AJK et al. (2017). Sci Rep 7:3216",
            "Wittmann M et al. (2006). Curr Biol 16(6):R187–188",
            "West AC et al. (2019). Nat Commun 10:5381",
        ],
        "limitations": (
            "Garmin-Schlafphasen aus Akzelerometer; EEG-Goldstandard nicht verfügbar. "
            "Schlafzeit-Erkennung kann um 15–30 min abweichen."
        ),
    },
    # ── Body / SpO2 ───────────────────────────────────────────────────────────
    "spo2_trend": {
        "level": "meta",
        "label": "Meta-Analyse",
        "name": "SpO2-Trendanalyse",
        "summary": (
            "Nächtliche SpO2-Desaturationen (<90%) sind etabliertes Screening-Kriterium "
            "für obstruktive Schlafapnoe. AASM Clinical Practice Guidelines 2017 "
            "empfehlen Pulsoximetrie als initialen Screening-Test."
        ),
        "refs": [
            "Kapur VK et al. (2017). J Clin Sleep Med 13(3):479–504 [AASM Leitlinie]",
            "Duce B et al. (2014). J Clin Sleep Med 10(3):343–347",
        ],
        "limitations": (
            "Optische Pulsoximetrie (Garmin) ist weniger präzise als klinische Geräte. "
            "Kein Ersatz für formale Polysomnographie-Diagnose. "
            "Apnoe-Flag ist Screening-Hinweis, kein Befund."
        ),
    },
    "body_battery_custom": {
        "level": "model",
        "label": "Eigenmodell",
        "name": "Body Battery Custom",
        "summary": (
            "Fresh-State-Energiemodell (v2, Mai 2026): Tagesenergie als "
            "physiologischer Snapshot — 70 % aktuelle Physiologie + 30 % Trägheit "
            "vom Vortag. Schlafphasen (Tiefschlaf-Ziel 20 %, REM-Ziel 25 %) sind "
            "primäres Erholungssignal, HRV vs. 30-Tage-Baseline sekundär. "
            "Ersetzt das frühere Banister-Akkumulationsmodell, das bei Ruhe "
            "Plateaus bei 100 produzierte (Sci Rep 2025: FFM hat fundamentale "
            "statistische Mängel). Composite-Aggregation bleibt heuristisch — "
            "kein Hersteller veröffentlicht klinisch validierte Formel."
        ),
        "refs": [
            "Walker M (2017). Why We Sleep — sleep stage targets (Deep ~20 %, REM ~25 %).",
            "Dijk DJ, Czeisler CA (1995). J Neurosci 15(5):3526–3538 — SWS/REM physiology.",
            "Plews DJ et al. (2013). Sports Med 43(9):773–781 — HRV vs. baseline.",
            "Kellmann M, Kallus KW (2001). Recovery-Stress Questionnaire for Athletes.",
            "Statistical flaws of the fitness-fatigue model. Sci Rep (2025) doi:10.1038/s41598-025-88153-7.",
        ],
        "limitations": (
            "Kein externer Benchmark. Gewichtungen (70/30, 35/25) sind "
            "heuristische Kalibrierungen, nicht gegen Goldstandard-Biomarker "
            "validiert. Schlafphasen-Messung per Akzelerometer+HRV (Garmin) "
            "nur mäßig mit PSG-Referenzmessungen korreliert."
        ),
    },
    "stress_score_custom": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "Stress-Score (HRV-basiert)",
        "summary": (
            "Sympatho-vagale Balance als Stress-Proxy via HRV-Baseline-Abweichung. "
            "Mehrere Studien bestätigen inversen Zusammenhang zwischen HRV und "
            "wahrgenommenem Stress. Tagesgranularität ist eine Limitation."
        ),
        "refs": [
            "Pumprla J et al. (2002). Int J Cardiol 84(1):1–14",
            "Shaffer F, Ginsberg JP (2017). Front Public Health 5:258",
            "Järvelin-Pasanen S et al. (2018). Electronics 10(2):119",
        ],
        "limitations": (
            "Kein intraday HRV-Zugriff → Tageswert statt stündlicher Auflösung. "
            "Garmins Stress-Score zeigt Stundenverläufe; unser Score nur einen Tageswert."
        ),
    },
    # ── Running ───────────────────────────────────────────────────────────────
    "running_economy": {
        "level": "meta",
        "label": "Meta-Analyse",
        "name": "Laufökonomie-Score",
        "summary": (
            "Bodenkonatktzeit, vertikale Oszillation und vertikales Verhältnis sind "
            "meta-analytisch als valide Laufökonomie-Indikatoren bestätigt. "
            "Moore (2016) systematischer Review: GCT und VO sind die stärksten Prädiktoren."
        ),
        "refs": [
            "Moore IS (2016). Sports Med 46(6):793–807 [Systematischer Review]",
            "Cavanagh PR, Kram R (1985). Med Sci Sports Exerc 17(3):326–331",
            "Fletcher JR et al. (2009). Eur J Appl Physiol 86(5):411–418",
        ],
        "limitations": (
            "Normwerte aus Studienpopulationen; individuelle Optima können abweichen. "
            "Z-Score gegen eigene Baseline ist personalisiert aber nicht extern validiert."
        ),
    },
    # ── ML Models ─────────────────────────────────────────────────────────────
    "readiness_rf": {
        "level": "model",
        "label": "Eigenmodell",
        "name": "Readiness RF (Random Forest)",
        "summary": (
            "Personalisierter Random Forest trainiert auf deinen eigenen Daten. "
            "Sagt morgige Readiness auf Basis heutiger Biomarker voraus. "
            "Kein populationsbasierter Goldstandard — Modell verbessert sich mit mehr Daten."
        ),
        "refs": [
            "Breiman L (2001). Machine Learning 45(1):5–32 [RF Grundlage]",
            "Plews DJ et al. (2013). Sports Med 43(9):773–781 [Feature-Basis]",
        ],
        "limitations": (
            "Kein externer Benchmark. Mindestens 30 Trainingstage nötig. "
            "Modell ist spezifisch für dich — keine Generalisierbarkeit."
        ),
    },
    # ── Anomaly Detection ─────────────────────────────────────────────────────
    "anomaly_hr": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "Ruhepuls-Anomalie (Z-Score)",
        "summary": (
            "Z-Score-basierte Anomalie-Detektion gegen 30-Tages-Baseline. "
            "Erhöhter Ruhepuls als Erholungsindikator ist gut belegt. "
            "Personalisierte Baseline ist methodisch stärker als absolute Normwerte."
        ),
        "refs": [
            "Chandola V et al. (2009). ACM Computing Surveys 41(3):15",
            "Achten J, Jeukendrup AE (2003). Sports Med 33(7):517–538",
        ],
        "limitations": "Z-Score >2.0 als Schwellenwert ist konventionell, nicht spezifisch validiert.",
    },
    "anomaly_spo2": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "SpO2-Anomalie (Z-Score)",
        "summary": "Z-Score-Abweichung vom persönlichen SpO2-Mittelwert. Methodisch analog zur HR-Anomalie.",
        "refs": [
            "Chandola V et al. (2009). ACM Computing Surveys 41(3):15",
            "Kapur VK et al. (2017). J Clin Sleep Med 13(3):479–504",
        ],
        "limitations": "Optischer Sensor weniger präzise als klinische Pulsoximetrie.",
    },
    "anomaly_sleep_duration": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "Schlafdauer-Anomalie (Z-Score)",
        "summary": "Z-Score-Abweichung von persönlicher Schlafdauer-Baseline.",
        "refs": [
            "Chandola V et al. (2009). ACM Computing Surveys 41(3):15",
            "Van Dongen HPA et al. (2003). Sleep 26(2):117–126",
        ],
        "limitations": "Garmin-Schlafzeiten-Erkennung kann um 15–30 min abweichen.",
    },
    "anomaly_steps": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "Schritte-Anomalie (Z-Score)",
        "summary": "Ungewöhnlich niedrige oder hohe Schrittzahlen als Aktivitätsmuster-Signal.",
        "refs": ["Chandola V et al. (2009). ACM Computing Surveys 41(3):15"],
        "limitations": "Schrittzahl allein ist ein grober Aktivitätsproxy ohne Intensitätsinformation.",
    },
    "anomaly_stress": {
        "level": "replicated",
        "label": "Repliziert",
        "name": "Stress-Anomalie (Z-Score)",
        "summary": "Z-Score-Abweichung vom persönlichen Stress-Baseline.",
        "refs": [
            "Chandola V et al. (2009). ACM Computing Surveys 41(3):15",
            "Pumprla J et al. (2002). Int J Cardiol 84(1):1–14",
        ],
        "limitations": "Garmin-Stress basiert auf HRV-Proxies; Tagesgranularität.",
    },
}
