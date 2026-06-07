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
            thresholds: {
                lines: 70,
                functions: 70,
            },
        },
    },
});
