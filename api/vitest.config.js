import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        setupFiles: ['./tests/js/setup.js'],
        include: ['tests/js/**/*.test.js'],
        coverage: {
            provider: 'v8',
            // Gate scope = modules with genuine Vitest unit coverage. These 6 hold
            // a strict 95/90 bar (regressions fail CI). The other ~19 static modules
            // are DOM-heavy loaders covered behaviorally by Playwright E2E, NOT by
            // this gate — deliberately kept honest: adding superficially-tested
            // modules (colors/dashboard-hero/metrics-ml/settings sit at 0–54%) would
            // force lowering the bar, which we don't do. Expanding unit coverage to
            // those modules is tracked separately (review finding M2 "Vollständig").
            include: [
                'src/static/chart-utils.js',
                'src/static/dashboard-utils.js',
                'src/static/dashboard-nav.js',
                'src/static/dashboard-status.js',
                'src/static/epilepsy.js',
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
