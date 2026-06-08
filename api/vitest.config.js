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
            include: [
                'src/static/chart-utils.js',
                'src/static/dashboard-utils.js',
                'src/static/dashboard-nav.js',
                'src/static/dashboard-status.js',
                'src/static/epilepsy.js',
                'src/static/metrics-ml.js',
                'src/static/onboarding.js',
            ],
            // Angehoben von 70 nach gezielter Test-Erweiterung. Knapp unter dem
            // erreichten Niveau (statements 99.76 / branches 96.5 / functions 93.75 /
            // lines 100), damit Regressionen auffallen; die verbleibenden Lücken sind
            // bewusst defensive Guards (if(el)/?./.catch) — kein 100%-Ziel (CLAUDE.md).
            thresholds: {
                statements: 95,
                branches: 95,
                functions: 90,
                lines: 95,
            },
        },
    },
});
