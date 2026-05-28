import { vi } from 'vitest';

// Chart.js is loaded as UMD global in browser — mock it for Node/jsdom tests
global.Chart = {
    defaults: {
        color: '',
        borderColor: '',
        interaction: {},
        elements: { point: {} },
    },
};

// jsdom does not implement window.matchMedia
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((q) => ({ matches: false, media: q })),
});
