import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        setupFiles: ['./tests/js/setup.js'],
        include: ['tests/js/**/*.test.js'],
        coverage: {
            provider: 'v8',
            // Gate scope = ES modules with genuine Vitest unit coverage at a strict
            // 95/90 bar (regressions fail CI). metrics-ml.js (the ML metric-card
            // render logic) was added in Wave 15 with full render-path tests.
            // NOT gateable by design: colors.js / help.js / metrics-overview.js /
            // activity.js are global <script> files (no ES exports) loaded as globals,
            // so v8 can't instrument them — colors.js IS tested (WCAG contrast) via
            // file-read+eval but yields 0 instrumented coverage. The remaining
            // DOM/fetch loader modules are covered behaviorally by Playwright E2E.
            // We never lower the bar to gate a superficially-tested module.
            // Wave 16 PR-D: the 5 pure metric-card render modules (metrics-energy/
            // readiness/sleep/garmin/activity) joined the gate with full render-path
            // + fetch tests, mirroring metrics-ml.js (7 → 12 modules).
            include: [
                'src/static/chart-utils.js',
                'src/static/dashboard-utils.js',
                'src/static/dashboard-nav.js',
                'src/static/dashboard-status.js',
                'src/static/epilepsy.js',
                'src/static/metrics-ml.js',
                'src/static/metrics-energy.js',
                'src/static/metrics-readiness.js',
                'src/static/metrics-sleep.js',
                'src/static/metrics-garmin.js',
                'src/static/metrics-activity.js',
                'src/static/onboarding.js',
            ],
            // Knapp unter dem erreichten Niveau (12 Module: statements 99.7 /
            // branches 95.07 / functions 98.25 / lines 100), damit Regressionen
            // auffallen; die verbleibenden Branch-Lücken sind Chart.js-Tick-Callbacks
            // (von der gemockten Chart-Lib nie aufgerufen) — kein 100%-Ziel (CLAUDE.md).
            thresholds: {
                statements: 95,
                branches: 95,
                functions: 90,
                lines: 95,
            },
        },
    },
});
