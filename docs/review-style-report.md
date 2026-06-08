# Style Review: PulseBase (Garmin Health Dashboard)
Datum: 2026-06-08
Basis: `/dev:tool-style` (Stack-Detection · `design-tokens.md` · `visual-patterns.md` Anti-Slop-Checklist) · State-of-the-Art-Recherche (NN/g, LogRocket, Dashboard-Trends 2026, „AI-Slop"-Backlash)

## Erkannter Kontext
**CSS-System:** Tailwind CSS v3 (Standalone-CLI, kein PostCSS/Node-Build) + CSS-Custom-Property-Token-Layer (`api/src/static/style.css`)
**Component-Library:** keine (bewusst — eigenes Dashboard, kein Framework)
**Design-Tokens:** vorhanden & reif — `--surface*`, `--text`, `--accent`, `--sp-1…8`, `--text-xs…hero`, `--radius*`; Dark-first mit `html:not(.dark)`-Light-Override
**Rendering:** Jinja2 server-rendered · Vanilla `fetch` + Chart.js · CSP nonce-basiert (keine Inline-Scripts)
**Phase:** Production / Pre-Public-Release

> Hinweis: Befunde aus Code-Lese (21 Templates in `api/src/templates/`, 25 JS-Dateien in `api/src/static/`, `style.css`, `tailwind.config.js`) und Abgleich gegen die kompilierte `tailwind.min.css`. Trend-/Geschmacks-Aussagen sind als solche markiert.

---

## Ampel-Übersicht

| Dimension | Ampel | Befund | Behoben in |
|-----------|-------|--------|-----------|
| 1 · Korrektheit (Purge/Build) | 🔴 | P1: dynamisch gebaute Tailwind-Klassen gepurged → Epilepsie-Risiko-Flags unstyled | #161 |
| 2 · Accessibility (Kontrast) | 🟠 | P2: hartcodierte Chart-Farben umgehen theme-aware Palette → Light-Mode < 3:1 (WCAG 1.4.11) | #161 |
| 3 · Token-Konsistenz (SSoT) | 🟡 | P3: `accent` 3× definiert, Utility 0× genutzt; totes `tailwind-config.js` | #161 |
| 4 · CSS-Hygiene | 🟡 | P4: 6× `!important` auf `.sub-*`-Badges | #161 |
| 5 · Motion / A11y-Fundament | 🟠 | Kein `prefers-reduced-motion`-Guard projektweit; verstreute Timings; Ring-Animation ignorierte Reduced-Motion | #162 |
| 6 · Loading / Perceived Perf | 🟡 | „blank-then-pop"-Flash: Hero kollabiert→expandiert (Layout-Shift) | #163 |

**Gesamtbild:** Das Styling-System ist im Kern **gesund und gut tokenisiert**. Der einzige echte Funktionsbug (P1) traf das sicherheitskritischste Widget (Epilepsie-Risiko). Daneben zwei A11y-Lücken (Light-Mode-Kontrast, fehlender Reduced-Motion-Guard) und Konsistenz-Cleanups. Alle Befunde sind **umgesetzt und gemerged**.

---

## Umsetzungsstatus

| PR | Inhalt | Status |
|----|--------|--------|
| **#161** | Audit P1–P4 (Purge-Bug · Kontrast · accent-SSoT · `!important`) | ✅ **Gemerged** (`fix/styling-audit-p1-p4`, 2026-06-08) |
| **#162** | Motion-Fundament (reduced-motion + Tokens) + Wow-Polish | ✅ **Gemerged** (`feat/motion-foundation`, 2026-06-08) |
| **#163** | Skeleton-Screens (Hero + Aktivitäten, kein Layout-Shift) | ✅ **Gemerged** (`feat/skeleton-screens`, 2026-06-08) |

Verifiziert je PR: Biome sauber · Vitest 188/188 · pytest (Template-Test) · gegen kompilierte CSS geprüft.

---

## ✅ #161 — Audit P1–P4 (Quick-Wins)

### 🔴 P1 — Funktionsbug: dynamisch gebaute Tailwind-Klassen werden gepurged
`epilepsy.js renderRiskFlags` baute Klassen per `${fc}`-Interpolation (`bg-${fc}-500/10` …). Der Tailwind-Content-Scanner sieht nur literale Tokens → `bg-red-500/10`, `bg-slate-500/10`, `text-amber-400` u. a. fehlten in `tailwind.min.css` → **rote (Hochrisiko-) und Fallback-Risiko-Flags rendern ohne Hintergrund/Farbe**. Gegen die kompilierte CSS verifiziert.
**Fix:** statische `FLAG_STYLE`-Map mit vollen Klassenstrings; `make tailwind-build`. *(behebt P1 — Funktionsbug)*

### 🟠 P2 — Light-Mode-Kontrast (WCAG 1.4.11)
Hartcodierte dunkel-getunte `borderColor`-Hex (`#94a3b8`, `#86efac`) in `metrics-energy/garmin/readiness` umgingen die theme-aware `C`-Palette aus `colors.js` → „Wochenø/Garmin"-Referenzlinien im Light-Mode unter der Kontrastgrenze.
**Fix:** `C.muted` / `C.green`. *(behebt P2 — A11y)*

### 🟡 P3 — `accent` Single Source of Truth
`accent: #10b981` war **3×** definiert (`tailwind.config.js`, `--accent` in `style.css`, `static/tailwind-config.js`), die Tailwind-`accent`-Utility **0×** genutzt.
**Fix:** totes `static/tailwind-config.js` (unreferenziert) gelöscht + `colors.accent` aus `tailwind.config.js` entfernt; `--accent`-Token bleibt einzige Quelle. *(behebt P3 — SSoT)*

### 🟡 P4 — `!important`-Cluster
6× `!important` auf `.sub-green/amber/red` ([style.css]) um eine höher-spezifische Regel zu schlagen.
**Fix:** Regeln auf gleiche Spezifität wie `.hero-vital-derived` gescopt (`html.dark` / `html:not(.dark)`), `!important` entfernt — Quellreihenfolge entscheidet. *(behebt P4 — CSS-Hygiene)*

---

## 🔬 State-of-the-Art-Recherche + AI-Anti-Pattern (informierte #162/#163)

Recherche (3 Threads): Dashboard-Design-Trends 2026, Skeleton-vs-Spinner-Evidenz, „AI-Slop"-Backlash. Kernfazit für eine **medizinnahe** App („kein medizinischer Befund"):

- **Function-forward statt Dekoration** [Nicht verifiziert — Trend]: 2026-Konsens „alles entfernen, was keine Entscheidung stützt". Für ein Health-Dashboard ist hohes Ink-to-Data-Ratio selbst das Anti-Pattern.
- **AI-Slop-Signatur vermeiden** [Spekulation]: Purple/Blue-Gradients, übergroßer Hero, Bento-Grid, uniformer 16px-Radius. Differenzierung über **Motion + data-driven Farbe + Typo-Hierarchie**, nicht über mehr Gradients.
- **Skeleton „richtig"** [belegt — NN/g, LogRocket]: schlagen Spinner bei *perceived performance*, ABER nur bei exakter Layout-Spiegelung, 300-ms-Regel (drunter nichts zeigen) und schneller Pulse — sonst schaden sie mehr als ein Spinner.
- **Bewusst NICHT übernommen:** Glassmorphism überall, 3D-Dashboards, „jelly"/tactile-deformable Physics — untergraben in einer Gesundheits-App Trust + A11y + Perf.

---

## ✅ #162 — Motion-Fundament + Wow-Polish

- **Gate A — `prefers-reduced-motion`-Guard (global):** fehlte projektweit komplett. Neutralisiert alle Animationen/Transitions (WCAG 2.3.3) — einziger bewusster `!important`-Ausnahmefall (A11y-Override).
- **Gate B — Motion-Tokens:** `--dur-fast|base|slow`, `--ease-out`, `--ease-spring` im `:root` (Timings waren verstreut) — analog zum bestehenden Spacing-/Typo-Token-System.
- **C — Wow: gestaffelte Karten-Entrance** (`card-in`, `nth-child`-Delay, CSS-only).
- **D — Hero-Ring:** bestehende rAF-Animation linear → cubic-ease-out + expliziter `matchMedia`-Guard (CSS-Gate greift bei JS-`setAttribute` nicht → Endzustand bei Reduced-Motion sofort).
- **Bewusst ausgeklammert:** Chart.js `animation: false` (Bestandsentscheidung), opake Karten (kein Glassmorphism).

---

## ✅ #163 — Skeleton-Screens

- **Hero + Aktivitäten** rendern Skeleton statt `Lade…` — **spiegeln das finale Layout** über dieselben `.hero-grid`-Klassen → **null Layout-Shift** (NN/g).
- **Automatischer Ersatz** ohne JS: `buildHeroCard()`/`renderActivitiesTable()` überschreiben `innerHTML`.
- **300-ms-Regel CSS-only:** `.skeleton` `opacity:0` + `animation-delay:300ms` → bei schnellem `fetch` kein Flash. Reduced-Motion via Gate A automatisch; Platzhalter `aria-hidden`.
- **Test:** deterministischer pytest-Template-Test (`test_pages.py`).
- **Bewusst ausgeklammert:** Chart-Karten — `.chart-wrap` reserviert bereits feste Höhe (kein Shift).

---

## Bewusst offen / nicht umgesetzt

| Punkt | Begründung | Trigger |
|-------|-----------|---------|
| Motion-Token-Migration | Verstreute Timings (`.1s`/`.12s`/`.15s`) noch nicht auf `--dur-*` umgestellt — aus #162 bewusst ausgeklammert (Scope) | Konsistenz-Cleanup-PR |
| Data-driven Accent / Hero | Anti-Slop-Differenzierer (Readiness-Wert als einziges farbgebendes Signal) — größere Design-Exploration | Bei Bedarf |
| Chart-Mikro-Interaktionen | `animation: false` ist Bestandsentscheidung (Perf/Stabilität) — nicht angetastet | Wenn explizit gewünscht |
| Chart-Karten-Skeletons | `.chart-wrap` reserviert Höhe → kein Shift; Shimmer auf ~12 Canvas = Scope-Creep | — |

---

## Verankerung
- **Design-Entscheidungen** (Motion, Reduced-Motion, Skeleton) dauerhaft in `docs/design-decisions.md` (Abschnitt „CSS: Tailwind CLI Build + custom style.css").
- **Detail-Begründung + Verifikation** je Maßnahme in den PR-Beschreibungen #161/#162/#163.

## Quellen (Recherche)
- NN/g — [Skeleton Screens 101](https://www.nngroup.com/articles/skeleton-screens/) · [Skeleton vs Progress vs Spinner](https://www.nngroup.com/videos/skeleton-screens-vs-progress-bars-vs-spinners/)
- LogRocket — [Skeleton loading design](https://blog.logrocket.com/ux-design/skeleton-loading-screen-design/)
- DesignRush — [9 Dashboard Principles 2026](https://www.designrush.com/agency/ui-ux-design/dashboard/trends/dashboard-design-principles) · Canva — [Imperfect by Design 2026](https://www.canva.com/newsroom/news/design-trends-2026/)
- 925studios — [AI Slop Web Design Guide](https://www.925studios.co/blog/ai-slop-web-design-guide)
