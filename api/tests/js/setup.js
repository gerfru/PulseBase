import { vi } from 'vitest';

// Chart.js is loaded as UMD global in browser — mock it for Node/jsdom tests.
// Implementation must be a regular (constructable) function, not an arrow:
// vitest 4's spy invokes `new Chart(...)` via the implementation, and arrows
// are not constructors ("is not a constructor").
const ChartMock = vi.fn(function () {
    return { destroy: vi.fn(), update: vi.fn() };
});
ChartMock.defaults = {
    color: '',
    borderColor: '',
    interaction: {},
    elements: { point: {} },
};
ChartMock.register = vi.fn();
global.Chart = ChartMock;

// DOMPurify is loaded as UMD global in browser — pass-through mock for unit tests
global.DOMPurify = { sanitize: (s) => s };

// jsdom does not implement window.matchMedia
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((q) => ({ matches: false, media: q })),
});

// jsdom does not implement Element.prototype.scrollIntoView
if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn();
}
