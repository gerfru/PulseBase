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

const { fmtSyncAge, showToast, loadSyncStatus, triggerSync } = await import(
    '../../src/static/dashboard-status.js'
);

beforeEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    // Provide DOM elements required by the module
    document.body.innerHTML =
        '<div id="toast"></div>' +
        '<span id="sync-last"></span>' +
        '<button id="sync-btn">↻ Sync</button>' +
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

    it('sets sync-loading and schedules poll when sync is pending', async () => {
        vi.useFakeTimers();
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ last_sync_at: null, pending: true }),
        });
        await loadSyncStatus();
        expect(document.getElementById('sync-btn').classList.contains('sync-loading')).toBe(true);
        vi.clearAllTimers();
    });

    it('does not throw when fetch fails', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('network error'));
        await expect(loadSyncStatus()).resolves.toBeUndefined();
    });
});

describe('triggerSync', () => {
    it('shows error toast when API returns non-ok response', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            json: () => Promise.resolve({ error: { message: 'Sync fehlgeschlagen' } }),
        });
        await triggerSync();
        expect(document.getElementById('toast').textContent).toBe('Sync fehlgeschlagen');
    });

    it('sets sync-loading and schedules poll on success', async () => {
        vi.useFakeTimers();
        global.fetch = vi.fn().mockResolvedValue({ ok: true });
        await triggerSync();
        expect(document.getElementById('sync-btn').classList.contains('sync-loading')).toBe(true);
        vi.clearAllTimers();
    });

    it('shows connection error toast when fetch throws', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('network'));
        await triggerSync();
        expect(document.getElementById('toast').textContent).toBe('Verbindungsfehler');
    });

    it('does nothing when sync is already loading', async () => {
        document.getElementById('sync-btn').classList.add('sync-loading');
        global.fetch = vi.fn();
        await triggerSync();
        expect(fetch).not.toHaveBeenCalled();
    });
});
