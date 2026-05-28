import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock heavy module dependencies so only the utility functions are tested
vi.mock('../../src/static/dashboard-nav.js', () => ({
    currentDays: 7,
    resetOffset: vi.fn(),
    updateNavBar: vi.fn(),
}));
vi.mock('../../src/static/dashboard-loaders.js', () => ({
    load: vi.fn(),
    loadTrainingLoad: vi.fn(),
    loadReadiness: vi.fn(),
    loadMlInsights: vi.fn(),
    loadEnergyMetrics: vi.fn(),
}));

const { fmtSyncAge, showToast } = await import('../../src/static/dashboard-status.js');

beforeEach(() => {
    vi.useRealTimers();
    // Provide the #toast element that showToast requires
    document.body.innerHTML = '<div id="toast"></div>';
});

describe('showToast', () => {
    it('sets message text and show class', () => {
        showToast('Sync abgeschlossen');
        const el = document.getElementById('toast');
        expect(el.textContent).toBe('Sync abgeschlossen');
        expect(el.className).toContain('show');
    });

    it('appends type class when provided', () => {
        showToast('Fehler', 'error');
        const el = document.getElementById('toast');
        expect(el.className).toContain('error');
    });

    it('shows without type class when omitted', () => {
        showToast('Info');
        const el = document.getElementById('toast');
        expect(el.className).toBe('toast show');
    });
});

describe('fmtSyncAge', () => {
    it('returns Gerade eben within the first 2 minutes', () => {
        vi.useFakeTimers({ now: new Date('2024-01-15T12:00:00Z') });
        expect(fmtSyncAge('2024-01-15T11:59:30Z')).toBe('Gerade eben');
        expect(fmtSyncAge('2024-01-15T11:58:40Z')).toBe('Gerade eben');
    });

    it('returns vor Xm for 2–59 minutes ago', () => {
        vi.useFakeTimers({ now: new Date('2024-01-15T12:00:00Z') });
        expect(fmtSyncAge('2024-01-15T11:30:00Z')).toBe('vor 30m');
        expect(fmtSyncAge('2024-01-15T11:02:00Z')).toBe('vor 58m');
        expect(fmtSyncAge('2024-01-15T11:58:00Z')).toBe('vor 2m');
    });

    it('returns vor Xh for 60+ minutes ago', () => {
        vi.useFakeTimers({ now: new Date('2024-01-15T12:00:00Z') });
        expect(fmtSyncAge('2024-01-15T10:00:00Z')).toBe('vor 2h');
        expect(fmtSyncAge('2024-01-15T09:00:00Z')).toBe('vor 3h');
    });
});
