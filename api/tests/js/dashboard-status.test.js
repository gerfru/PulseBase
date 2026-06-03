import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock heavy module dependencies so only the utility functions are tested
vi.mock('../../src/static/dashboard-nav.js', () => ({
    currentDays: 7,
    resetOffset: vi.fn(),
    updateNavBar: vi.fn(),
}));
vi.mock('../../src/static/dashboard-loaders.js', () => ({
    load: vi.fn(),
    loadTrainingLoad: vi.fn().mockResolvedValue(undefined),
    loadReadiness: vi.fn(),
    loadMlInsights: vi.fn(),
    loadEnergyMetrics: vi.fn().mockResolvedValue(undefined),
}));

const { fmtSyncAge, showToast, loadSyncStatus, loadMlStatus } = await import(
    '../../src/static/dashboard-status.js'
);

beforeEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    // Provide DOM elements required by the module
    document.body.innerHTML =
        '<div id="toast"></div>' +
        '<span id="sync-last"></span>' +
        '<div id="ml-status"></div>';
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

describe('loadSyncStatus', () => {
    it('updates sync-last text when last_sync_at is present', async () => {
        vi.useFakeTimers({ now: new Date('2024-01-15T12:10:00Z') });
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ last_sync_at: '2024-01-15T12:00:00Z', pending: false }),
        });
        await loadSyncStatus();
        expect(document.getElementById('sync-last').textContent).toBe('vor 10m');
    });

    it('schedules poll when sync is pending', async () => {
        vi.useFakeTimers();
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ last_sync_at: null, pending: true }),
        });
        await loadSyncStatus();
        expect(global.fetch).toHaveBeenCalledOnce();
        vi.clearAllTimers();
    });

    it('does not throw when fetch fails', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('network error'));
        await expect(loadSyncStatus()).resolves.toBeUndefined();
    });
});

describe('loadMlStatus', () => {
    it('shows ml-status with age when not pending and last_ml_at present', async () => {
        vi.useFakeTimers({ now: new Date('2024-01-15T12:10:00Z') });
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ last_ml_at: '2024-01-15T12:00:00Z', pending: false }),
        });
        await loadMlStatus();
        const el = document.getElementById('ml-status');
        expect(el.style.display).not.toBe('none');
        expect(el.textContent).toContain('vor 10m');
    });

    it('leaves ml-status unchanged when not pending and no last_ml_at', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ pending: false }),
        });
        const el = document.getElementById('ml-status');
        el.textContent = '';
        await loadMlStatus();
        expect(el.textContent).toBe('');
        expect(el.style.display).toBe('');
    });

    it('shows loading text and schedules poll when pending', async () => {
        vi.useFakeTimers();
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ pending: true }),
        });
        await loadMlStatus();
        expect(document.getElementById('ml-status').textContent).toBe('🤖 ML läuft…');
        vi.clearAllTimers();
    });

    it('does not throw on fetch error', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('network'));
        await expect(loadMlStatus()).resolves.toBeUndefined();
    });
});

describe('pollMlStatus (via loadMlStatus timer)', () => {
    it('shows toast and triggers reload when poll finds pending=false', async () => {
        vi.useFakeTimers();
        const { loadMlInsights } = await import('../../src/static/dashboard-loaders.js');

        global.fetch = vi.fn()
            .mockResolvedValueOnce({
                json: () => Promise.resolve({ pending: true }),
            })
            .mockResolvedValue({
                json: () =>
                    Promise.resolve({ pending: false, last_ml_at: '2024-01-15T11:00:00Z' }),
            });

        await loadMlStatus();
        // Advance past the 8 s poll interval, flush all micro-tasks
        await vi.advanceTimersByTimeAsync(8001);

        expect(document.getElementById('toast').textContent).toBe('ML Einblicke aktualisiert');
        expect(loadMlInsights).toHaveBeenCalled();
        vi.clearAllTimers();
    });

    it('continues polling while still pending', async () => {
        vi.useFakeTimers();
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ pending: true }),
        });

        await loadMlStatus();
        await vi.advanceTimersByTimeAsync(8001);
        // A second poll should have been scheduled
        expect(global.fetch).toHaveBeenCalledTimes(2);
        vi.clearAllTimers();
    });
});

describe('pollSyncStatus reschedules when still pending', () => {
    it('fetches again when pending=true during poll', async () => {
        vi.useFakeTimers();
        global.fetch = vi.fn()
            .mockResolvedValueOnce({
                json: () => Promise.resolve({ pending: true }),
            })
            .mockResolvedValueOnce({
                json: () => Promise.resolve({ pending: true, last_sync_at: null }),
            })
            .mockResolvedValue({
                json: () =>
                    Promise.resolve({ pending: false, last_sync_at: '2024-01-15T12:00:00Z' }),
            });

        await loadSyncStatus();
        // First poll fires → pending=true → reschedules
        await vi.advanceTimersByTimeAsync(5001);
        expect(global.fetch).toHaveBeenCalledTimes(2);
        vi.clearAllTimers();
    });
});

describe('pollSyncStatus (via loadSyncStatus timer)', () => {
    it('shows toast when poll finds pending=false', async () => {
        vi.useFakeTimers();
        global.fetch = vi.fn()
            .mockResolvedValueOnce({
                json: () => Promise.resolve({ pending: true }),
            })
            .mockResolvedValue({
                json: () =>
                    Promise.resolve({ pending: false, last_sync_at: '2024-01-15T11:50:00Z' }),
            });

        await loadSyncStatus();
        await vi.advanceTimersByTimeAsync(5001);

        expect(document.getElementById('toast').textContent).toBe('Sync abgeschlossen');
        vi.clearAllTimers();
    });

    it('updates sync-last timestamp when last_sync_at arrives during poll', async () => {
        vi.useFakeTimers({ now: new Date('2024-01-15T12:05:00Z') });
        global.fetch = vi.fn()
            .mockResolvedValueOnce({
                json: () => Promise.resolve({ pending: true }),
            })
            .mockResolvedValue({
                json: () =>
                    Promise.resolve({ pending: false, last_sync_at: '2024-01-15T12:00:00Z' }),
            });

        await loadSyncStatus();
        await vi.advanceTimersByTimeAsync(5001);

        expect(document.getElementById('sync-last').textContent).toBe('vor 5m');
        vi.clearAllTimers();
    });
});
