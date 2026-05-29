import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        setupFiles: ['./tests/js/setup.js'],
        include: ['tests/js/**/*.test.js'],
        coverage: {
            provider: 'v8',
            // Only measure coverage for the 4 utility files that have unit tests.
            // DOM-heavy files (loaders, hero, metrics) are covered by Playwright E2E instead.
            include: [
                'src/static/chart-utils.js',
                'src/static/dashboard-utils.js',
                'src/static/dashboard-nav.js',
                'src/static/dashboard-status.js',
            ],
            thresholds: {
                lines: 65,
                functions: 70,
            },
        },
    },
});
