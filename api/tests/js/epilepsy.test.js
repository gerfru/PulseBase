import { describe, it, expect, vi, beforeEach } from 'vitest';

// All DOM elements needed by module-level side effects AND tested functions.
// logSeizure() uses #duration and #notes (not #seizure-duration / #seizure-notes).
document.body.innerHTML =
    '<div id="severity-chips"></div>' +
    '<div id="risk-dot"></div>' +
    '<span id="risk-label"></span>' +
    '<span id="risk-detail"></span>' +
    '<div id="risk-flags"></div>' +
    '<div id="event-list"></div>' +
    '<button id="log-submit"></button>' +
    '<input id="occurred-at" />' +
    '<select id="seizure-type"><option value="unknown">Unbekannt</option><option value="focal">Fokal</option></select>' +
    '<input id="duration" />' +
    '<input id="notes" />' +
    '<span id="log-msg" style="display:none"></span>';

vi.stubGlobal('alert', vi.fn());
vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
        json: vi.fn().mockResolvedValue({ level: 'ok', flags: [], sleep_debt_h: 0 }),
    }),
);

const {
    esc,
    renderRiskFlags,
    renderSeverityChips,
    _resetSelectedSeverity,
    formatDuration,
    formatDate,
    loadRisk,
    loadEvents,
    logSeizure,
} = await import('../../src/static/epilepsy.js');

function mockFetch(response) {
    vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue(response) }),
    );
}

beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    _resetSelectedSeverity();
    document.getElementById('severity-chips').innerHTML = '';
    document.getElementById('risk-flags').innerHTML = '';
    document.getElementById('event-list').innerHTML = '';
    document.getElementById('occurred-at').value = '';
    document.getElementById('seizure-type').value = 'unknown';
    document.getElementById('duration').value = '';
    document.getElementById('notes').value = '';
    document.getElementById('log-msg').style.display = 'none';
});

// ── esc ──────────────────────────────────────────────────────────────────────

describe('esc', () => {
    it('returns empty string for null and undefined', () => {
        expect(esc(null)).toBe('');
        expect(esc(undefined)).toBe('');
    });
    it('encodes all HTML special characters', () => {
        expect(esc('<b>&"test"</b>')).toBe('&lt;b&gt;&amp;&quot;test&quot;&lt;/b&gt;');
    });
    it('leaves plain strings unchanged', () => {
        expect(esc('hello world')).toBe('hello world');
    });
});

// ── formatDuration ────────────────────────────────────────────────────────────

describe('formatDuration', () => {
    it('returns null for falsy values', () => {
        expect(formatDuration(0)).toBeNull();
        expect(formatDuration(null)).toBeNull();
        expect(formatDuration(undefined)).toBeNull();
    });
    it('returns seconds for values under 60', () => {
        expect(formatDuration(45)).toBe('45s');
        expect(formatDuration(1)).toBe('1s');
    });
    it('returns min+sec for values 60 and above', () => {
        expect(formatDuration(60)).toBe('1min 0s');
        expect(formatDuration(90)).toBe('1min 30s');
        expect(formatDuration(125)).toBe('2min 5s');
    });
});

// ── formatDate ────────────────────────────────────────────────────────────────

describe('formatDate', () => {
    it('returns a formatted date string with day.month.year', () => {
        const result = formatDate('2024-03-15T10:30:00Z');
        expect(result).toMatch(/\d{2}\.\d{2}\.\d{4}/);
    });
});

// ── renderRiskFlags ───────────────────────────────────────────────────────────

describe('renderRiskFlags', () => {
    it('renders label and detail via textContent', () => {
        const container = document.createElement('div');
        renderRiskFlags(container, [{ color: 'amber', label: 'Schlechter Schlaf', detail: '7h unter Soll' }]);
        const spans = container.querySelectorAll('span');
        expect(spans[0].textContent).toBe('Schlechter Schlaf');
        expect(spans[1].textContent).toBe('7h unter Soll');
    });

    it('does not inject HTML from label or detail (XSS prevention)', () => {
        const container = document.createElement('div');
        renderRiskFlags(container, [
            { color: 'ok', label: '<script>alert(1)</script>', detail: '<img onerror="alert(1)">' },
        ]);
        const row = container.querySelector('div');
        expect(row.innerHTML).toContain('&lt;script&gt;');
        expect(row.innerHTML).toContain('&lt;img');
        const spans = container.querySelectorAll('span');
        expect(spans[0].textContent).toBe('<script>alert(1)</script>');
        expect(spans[1].textContent).toBe('<img onerror="alert(1)">');
    });

    it('applies correct Tailwind color class per flag color', () => {
        const container = document.createElement('div');
        renderRiskFlags(container, [
            { color: 'ok', label: 'A', detail: '' },
            { color: 'amber', label: 'B', detail: '' },
            { color: 'red', label: 'C', detail: '' },
            { color: 'unknown', label: 'D', detail: '' },
        ]);
        const rows = container.querySelectorAll('div');
        expect(rows[0].className).toContain('emerald');
        expect(rows[1].className).toContain('amber');
        expect(rows[2].className).toContain('red');
        expect(rows[3].className).toContain('slate');
    });

    it('clears existing content before rendering', () => {
        const container = document.createElement('div');
        container.innerHTML = '<p>stale</p>';
        renderRiskFlags(container, []);
        expect(container.children.length).toBe(0);
    });
});

// ── renderSeverityChips ───────────────────────────────────────────────────────

describe('renderSeverityChips', () => {
    it('renders 5 chip buttons plus a label', () => {
        renderSeverityChips();
        const buttons = document.getElementById('severity-chips').querySelectorAll('button');
        expect(buttons.length).toBe(5);
    });

    it('shows "Keine Angabe" label when no severity selected', () => {
        renderSeverityChips();
        const label = document.getElementById('severity-chips').querySelector('span');
        expect(label.textContent).toBe('Keine Angabe');
    });

    it('selects a severity on chip click and shows its label', () => {
        renderSeverityChips();
        document.getElementById('severity-chips').querySelectorAll('button')[0].click();
        const label = document.getElementById('severity-chips').querySelector('span');
        expect(label.textContent).toBe('Sehr leicht');
    });

    it('deselects severity on second click of the same chip', () => {
        renderSeverityChips();
        document.getElementById('severity-chips').querySelectorAll('button')[0].click();
        document.getElementById('severity-chips').querySelectorAll('button')[0].click();
        const label = document.getElementById('severity-chips').querySelector('span');
        expect(label.textContent).toBe('Keine Angabe');
    });
});

// ── loadRisk ─────────────────────────────────────────────────────────────────

describe('loadRisk', () => {
    it('sets label text for known risk level', async () => {
        mockFetch({ level: 'amber', flags: [], sleep_debt_h: 1.5 });
        await loadRisk();
        expect(document.getElementById('risk-label').textContent).toBe('Leicht erhöhtes Risiko');
    });

    it('falls back to raw level text for unknown level', async () => {
        mockFetch({ level: 'unknown_level', flags: [], sleep_debt_h: 0 });
        await loadRisk();
        expect(document.getElementById('risk-label').textContent).toBe('unknown_level');
        // jsdom converts hex to rgb
        expect(document.getElementById('risk-dot').style.background).toBe('rgb(148, 163, 184)');
    });

    it('handles missing flags field gracefully', async () => {
        mockFetch({ level: 'ok', sleep_debt_h: 0 }); // no flags key
        await loadRisk();
        expect(document.getElementById('risk-flags').children.length).toBe(0);
    });

    it('renders flags via renderRiskFlags', async () => {
        mockFetch({
            level: 'red',
            flags: [{ color: 'red', label: 'Kritisch', detail: 'Hoch' }],
            sleep_debt_h: 3,
        });
        await loadRisk();
        expect(document.getElementById('risk-flags').children.length).toBe(1);
    });
});

// ── loadEvents ────────────────────────────────────────────────────────────────

describe('loadEvents', () => {
    it('shows empty message when no events', async () => {
        mockFetch([]);
        await loadEvents();
        expect(document.getElementById('event-list').innerHTML).toContain('Noch keine Einträge');
    });

    it('renders events with all fields (duration, severity, notes, known type)', async () => {
        mockFetch([{
            occurred_at: '2024-03-15T10:30:00Z',
            type: 'focal',
            duration_seconds: 90,
            severity: 3,
            notes: 'Test note',
        }]);
        await loadEvents();
        const html = document.getElementById('event-list').innerHTML;
        expect(html).toContain('Fokal');
        expect(html).toContain('1min 30s');
        expect(html).toContain('●●●○○');
        expect(html).toContain('Test note');
    });

    it('renders event without duration, severity, notes and escapes unknown type', async () => {
        mockFetch([{
            occurred_at: '2024-03-15T10:30:00Z',
            type: '<custom>',
            duration_seconds: null,
            severity: null,
            notes: null,
        }]);
        await loadEvents();
        const html = document.getElementById('event-list').innerHTML;
        expect(html).toContain('&lt;custom&gt;');
        expect(html).not.toContain('min');
        expect(html).not.toContain('●');
    });
});

// ── logSeizure ────────────────────────────────────────────────────────────────

describe('logSeizure', () => {
    it('alerts when occurred-at is empty', async () => {
        document.getElementById('occurred-at').value = '';
        await logSeizure();
        expect(window.alert).toHaveBeenCalledWith('Bitte Datum und Uhrzeit angeben.');
    });

    it('alerts on failed POST response', async () => {
        document.getElementById('occurred-at').value = '2024-03-15T10:30';
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({ ok: false, json: vi.fn().mockResolvedValue({}) }),
        );
        await logSeizure();
        expect(window.alert).toHaveBeenCalledWith('Fehler beim Speichern.');
    });

    it('resets form and shows success message on valid POST', async () => {
        document.getElementById('occurred-at').value = '2024-03-15T10:30';
        document.getElementById('seizure-type').value = 'focal';
        document.getElementById('duration').value = '90';
        document.getElementById('notes').value = 'Note';
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue([]) }),
        );
        vi.useFakeTimers();
        await logSeizure();
        expect(document.getElementById('occurred-at').value).toBe('');
        expect(document.getElementById('seizure-type').value).toBe('unknown');
        expect(document.getElementById('duration').value).toBe('');
        expect(document.getElementById('notes').value).toBe('');
        expect(document.getElementById('log-msg').style.display).toBe('inline');
        vi.runAllTimers();
        expect(document.getElementById('log-msg').style.display).toBe('none');
    });
});
