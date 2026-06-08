import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        setupFiles: ['./tests/js/setup.js'],
        include: ['tests/js/**/*.test.js'],
        coverage: {
            provider: 'v8',
            // Utility files with unit tests. DOM-heavy loader/metrics files are covered by Playwright E2E.
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
