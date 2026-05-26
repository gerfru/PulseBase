/* PulseBase — Zentralisierte Chart-Palette
 * Wird in base.html vor allen page-scripts geladen.
 * RPE_COLORS in activity.js bleibt unverändert (semantische grün→rot Skala, Foster et al.).
 */
const C = {
    // Semantische Status-Farben — universell verstanden, unverändert
    green:  '#22c55e',   // Erholt, CTL-Fitness, Batterie hoch
    amber:  '#f59e0b',   // Warnung, Ausdauer-Sport
    red:    '#ef4444',   // Stress, HR-Anomalie, Gefahr
    orange: '#f97316',   // ATL/Ermüdung (bewusst ≠ red: "müde" ≠ "gefährlich")

    // Datenlinie-Farben (von 8 auf 4 konsolidiert, sanftere Töne)
    blue:   '#60a5fa',   // Schlaf, neutrale Metriken (konsolidiert aus #3b82f6 + #06b6d4)
    indigo: '#818cf8',   // HRV, TSB, primäre Datenlinien (aufgehellt von #6366f1)
    violet: '#a78bfa',   // Kognitiv, Schlaf-Score, Form/TSB (aufgehellt von #8b5cf6)
    muted:  '#94a3b8',   // Referenzlinien, Baselines

    // Schlafphasen — 4 distinct Farben für gestapeltes Bar-Chart
    sleepDeep:  '#4f46e5',
    sleepRem:   '#8b5cf6',
    sleepLight: '#a5b4fc',
    // sleepAwake: theme-aware, inline: isDark ? '#334155' : '#e2e8f0'
};
