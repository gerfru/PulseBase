import { vi } from 'vitest';

// Chart.js is loaded as UMD global in browser — mock it for Node/jsdom tests
const ChartMock = vi.fn().mockImplementation(() => ({
    destroy: vi.fn(),
    update: vi.fn(),
}));
ChartMock.defaults = {
    color: '',
    borderColor: '',
    interaction: {},
    elements: { point: {} },
};
global.Chart = ChartMock;

// DOMPurify is loaded as UMD global in browser — pass-through mock for unit tests
global.DOMPurify = { sanitize: (s) => s };

// jsdom does not implement window.matchMedia
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((q) => ({ matches: false, media: q })),
});
