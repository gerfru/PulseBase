/* PulseBase — Zentralisierte Chart-Palette (theme-aware)
 * Wird in base.html NACH theme-init.js und vor allen page-scripts geladen,
 * d.h. document.documentElement trägt zum Eval-Zeitpunkt bereits die korrekte
 * .dark-Klasse. Jede Datenfarbe erfüllt >= 3:1 gegen ihren Karten-Hintergrund
 * (Light #ffffff / Dark #1e293b) — WCAG 1.4.11. Verifiziert in tests/js/colors.test.js.
 * RPE_COLORS in activity.js bleibt unverändert (semantische grün→rot Skala, Foster et al.).
 *
 * Hinweis: Charts werden beim Seiten-Load eingefärbt. Ein Theme-Toggle ohne
 * Neuladen färbt bereits gezeichnete Charts erst beim nächsten Load um.
 */

// Dark Mode (Karten-Hintergrund #1e293b) — kräftige Töne auf dunklem Grund.
const _C_DARK = {
    green: '#22c55e', // Erholt, CTL-Fitness, Batterie hoch
    amber: '#f59e0b', // Warnung, Ausdauer-Sport
    red: '#ef4444', // Stress, HR-Anomalie, Gefahr
    orange: '#f97316', // ATL/Ermüdung (bewusst ≠ red: "müde" ≠ "gefährlich")
    blue: '#60a5fa', // Schlaf, neutrale Metriken
    indigo: '#818cf8', // HRV, TSB, primäre Datenlinien
    violet: '#a78bfa', // Kognitiv, Schlaf-Score, Form/TSB
    muted: '#94a3b8', // Referenzlinien, Baselines
    sleepDeep: '#6366f1', // aufgehellt von #4f46e5 (war 2.33:1 auf dunkler Karte)
    sleepRem: '#8b5cf6',
    sleepLight: '#a5b4fc',
    sleepAwake: '#64748b', // war inline #334155 (zu dunkel auf dunkler Karte)
};

// Light Mode (Karten-Hintergrund #ffffff) — abgedunkelte Töne für >= 3:1 auf Weiß.
const _C_LIGHT = {
    green: '#15803d',
    amber: '#b45309',
    red: '#ef4444', // erfüllt bereits 3.76:1 auf Weiß
    orange: '#c2410c',
    blue: '#2563eb',
    indigo: '#4f46e5',
    violet: '#7c3aed',
    muted: '#64748b',
    sleepDeep: '#4f46e5',
    sleepRem: '#7c3aed',
    sleepLight: '#6366f1',
    sleepAwake: '#64748b',
};

// biome-ignore lint/correctness/noUnusedVariables: accessed as global from ES module scripts
const C = document.documentElement.classList.contains('dark') ? _C_DARK : _C_LIGHT;
