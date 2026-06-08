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
    '<h2 id="log-card-title">Anfall erfassen</h2>' +
    '<button id="log-submit"></button>' +
    '<button id="log-cancel" style="display:none"></button>' +
    '<input id="occurred-at" />' +
    '<select id="seizure-type"><option value="unknown">Unbekannt</option><option value="focal">Fokal</option><option value="generalized">Generalisiert</option></select>' +
    '<input id="duration" />' +
    '<input id="notes" />' +
    '<span id="log-msg" style="display:none"></span>' +
    '<span id="log-error" style="display:none"></span>' +
    '<dialog id="seizure-delete-confirm"></dialog>' +
    '<button id="seizure-delete-cancel"></button>' +
    '<button id="seizure-delete-ok"></button>';

// jsdom does not implement <dialog>.showModal/close — stub them.
const _dlg = document.getElementById('seizure-delete-confirm');
_dlg.showModal = vi.fn();
_dlg.close = vi.fn();

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
    _getEditingId,
    formatDuration,
    formatDate,
    loadRisk,
    loadEvents,
    logSeizure,
    enterEditMode,
    cancelEditMode,
    deleteSeizure,
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
    document.getElementById('log-error').style.display = 'none';
    document.getElementById('log-error').textContent = '';
    document.getElementById('log-cancel').style.display = 'none';
    document.getElementById('log-card-title').textContent = 'Anfall erfassen';
    document.getElementById('log-submit').textContent = '';
    cancelEditMode();
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
    it('shows inline error (no alert) when occurred-at is empty', async () => {
        document.getElementById('occurred-at').value = '';
        await logSeizure();
        expect(window.alert).not.toHaveBeenCalled();
        const err = document.getElementById('log-error');
        expect(err.style.display).toBe('inline');
        expect(err.textContent).toBe('Bitte Datum und Uhrzeit angeben.');
    });

    it('shows inline error and keeps form values on failed POST', async () => {
        document.getElementById('occurred-at').value = '2024-03-15T10:30';
        document.getElementById('notes').value = 'Bleibt erhalten';
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({ ok: false, json: vi.fn().mockResolvedValue({}) }),
        );
        await logSeizure();
        expect(window.alert).not.toHaveBeenCalled();
        expect(document.getElementById('log-error').textContent).toContain('fehlgeschlagen');
        // Form is not cleared so the user can retry.
        expect(document.getElementById('notes').value).toBe('Bleibt erhalten');
    });

    it('shows inline error when fetch itself throws', async () => {
        document.getElementById('occurred-at').value = '2024-03-15T10:30';
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
        await logSeizure();
        expect(document.getElementById('log-error').textContent).toContain('fehlgeschlagen');
    });

    it('no-ops gracefully when the error element is absent', async () => {
        const err = document.getElementById('log-error');
        err.remove();
        document.getElementById('occurred-at').value = '';
        await expect(logSeizure()).resolves.toBeUndefined();
        document.body.appendChild(err); // restore for later tests
    });

    it('resets form and shows success message on valid POST', async () => {
        document.getElementById('occurred-at').value = '2024-03-15T10:30';
        document.getElementById('seizure-type').value = 'focal';
        document.getElementById('duration').value = '90';
        document.getElementById('notes').value = 'Note';
        const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue([]) });
        vi.stubGlobal('fetch', fetchMock);
        vi.useFakeTimers();
        await logSeizure();
        // POST to the collection endpoint when not editing.
        expect(fetchMock.mock.calls[0][0]).toBe('/api/seizures');
        expect(fetchMock.mock.calls[0][1].method).toBe('POST');
        expect(document.getElementById('occurred-at').value).toBe('');
        expect(document.getElementById('seizure-type').value).toBe('unknown');
        expect(document.getElementById('duration').value).toBe('');
        expect(document.getElementById('notes').value).toBe('');
        expect(document.getElementById('log-msg').style.display).toBe('inline');
        vi.runAllTimers();
        expect(document.getElementById('log-msg').style.display).toBe('none');
    });
});

// ── enterEditMode / cancelEditMode ─────────────────────────────────────────────

describe('edit mode', () => {
    async function seedOneEvent() {
        mockFetch([{
            id: 42,
            occurred_at: '2024-03-15T10:30:00Z',
            type: 'focal',
            duration_seconds: 90,
            severity: 3,
            notes: 'Vorhandene Notiz',
        }]);
        await loadEvents();
    }

    it('prefills the form and switches to edit mode', async () => {
        await seedOneEvent();
        enterEditMode('42');
        expect(_getEditingId()).toBe(42);
        expect(document.getElementById('seizure-type').value).toBe('focal');
        expect(document.getElementById('duration').value).toBe('90');
        expect(document.getElementById('notes').value).toBe('Vorhandene Notiz');
        expect(document.getElementById('log-card-title').textContent).toBe('Anfall bearbeiten');
        expect(document.getElementById('log-submit').textContent).toBe('Aktualisieren');
        expect(document.getElementById('log-cancel').style.display).toBe('');
    });

    it('does nothing for an unknown id', async () => {
        await seedOneEvent();
        enterEditMode('999');
        expect(_getEditingId()).toBeNull();
    });

    it('PATCHes the item endpoint while editing', async () => {
        await seedOneEvent();
        enterEditMode('42');
        const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue([]) });
        vi.stubGlobal('fetch', fetchMock);
        vi.useFakeTimers();
        await logSeizure();
        expect(fetchMock.mock.calls[0][0]).toBe('/api/seizures/42');
        expect(fetchMock.mock.calls[0][1].method).toBe('PATCH');
        // Edit mode is reset after a successful update.
        expect(_getEditingId()).toBeNull();
        expect(document.getElementById('log-submit').textContent).toBe('Speichern');
    });

    it('cancelEditMode clears the form and exits edit mode', async () => {
        await seedOneEvent();
        enterEditMode('42');
        cancelEditMode();
        expect(_getEditingId()).toBeNull();
        expect(document.getElementById('notes').value).toBe('');
        expect(document.getElementById('log-card-title').textContent).toBe('Anfall erfassen');
        expect(document.getElementById('log-cancel').style.display).toBe('none');
    });

    it('falls back to defaults when editing an event with null fields', async () => {
        mockFetch([{
            id: 50,
            occurred_at: '2024-03-15T10:30:00Z',
            type: null,
            duration_seconds: null,
            severity: null,
            notes: null,
        }]);
        await loadEvents();
        enterEditMode('50');
        expect(document.getElementById('seizure-type').value).toBe('unknown');
        expect(document.getElementById('duration').value).toBe('');
        expect(document.getElementById('notes').value).toBe('');
    });

    it('exits edit mode when the currently edited item is deleted', async () => {
        mockFetch([{
            id: 60,
            occurred_at: '2024-03-15T10:30:00Z',
            type: 'focal',
            duration_seconds: 60,
            severity: 2,
            notes: 'X',
        }]);
        await loadEvents();
        enterEditMode('60');
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({}) })
            .mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue([]) });
        vi.stubGlobal('fetch', fetchMock);
        await deleteSeizure(60);
        expect(_getEditingId()).toBeNull();
    });
});

// ── deleteSeizure ──────────────────────────────────────────────────────────────

describe('deleteSeizure', () => {
    it('DELETEs the item endpoint and reloads', async () => {
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({}) }) // DELETE
            .mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue([]) }); // loadEvents
        vi.stubGlobal('fetch', fetchMock);
        await deleteSeizure(7);
        expect(fetchMock.mock.calls[0][0]).toBe('/api/seizures/7');
        expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
    });

    it('shows inline error on failed DELETE', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({ ok: false, json: vi.fn().mockResolvedValue({}) }),
        );
        await deleteSeizure(7);
        expect(document.getElementById('log-error').textContent).toContain('fehlgeschlagen');
    });

    it('shows inline error when the DELETE request throws', async () => {
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
        await deleteSeizure(7);
        expect(document.getElementById('log-error').textContent).toContain('fehlgeschlagen');
    });

    it('renders edit and delete buttons per event', async () => {
        mockFetch([{
            id: 5,
            occurred_at: '2024-03-15T10:30:00Z',
            type: 'focal',
            duration_seconds: null,
            severity: null,
            notes: null,
        }]);
        await loadEvents();
        const list = document.getElementById('event-list');
        expect(list.querySelector('[data-edit-id="5"]')).not.toBeNull();
        expect(list.querySelector('[data-del-id="5"]')).not.toBeNull();
    });
});

// ── Delegation + confirmation dialog (module-level listeners) ───────────────────

describe('list delegation and delete dialog', () => {
    async function seedOneEvent() {
        mockFetch([{
            id: 11,
            occurred_at: '2024-03-15T10:30:00Z',
            type: 'focal',
            duration_seconds: 60,
            severity: 2,
            notes: 'X',
        }]);
        await loadEvents();
    }

    it('enters edit mode when the edit button is clicked', async () => {
        await seedOneEvent();
        document.querySelector('[data-edit-id="11"]').click();
        expect(_getEditingId()).toBe(11);
    });

    it('opens the confirm dialog when the delete button is clicked', async () => {
        await seedOneEvent();
        const dlg = document.getElementById('seizure-delete-confirm');
        document.querySelector('[data-del-id="11"]').click();
        expect(dlg.showModal).toHaveBeenCalled();
    });

    it('deletes on confirm and closes the dialog', async () => {
        await seedOneEvent();
        const dlg = document.getElementById('seizure-delete-confirm');
        document.querySelector('[data-del-id="11"]').click();
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({}) })
            .mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue([]) });
        vi.stubGlobal('fetch', fetchMock);
        document.getElementById('seizure-delete-ok').click();
        await Promise.resolve();
        await Promise.resolve();
        expect(dlg.close).toHaveBeenCalled();
        expect(fetchMock.mock.calls[0][0]).toBe('/api/seizures/11');
        expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
    });

    it('cancels deletion without a request', async () => {
        await seedOneEvent();
        const dlg = document.getElementById('seizure-delete-confirm');
        document.querySelector('[data-del-id="11"]').click();
        const fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);
        document.getElementById('seizure-delete-cancel').click();
        expect(dlg.close).toHaveBeenCalled();
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it('deletes directly when <dialog> is unsupported (no showModal)', async () => {
        await seedOneEvent();
        const dlg = document.getElementById('seizure-delete-confirm');
        const savedShowModal = dlg.showModal;
        dlg.showModal = undefined;
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({}) })
            .mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue([]) });
        vi.stubGlobal('fetch', fetchMock);
        document.querySelector('[data-del-id="11"]').click();
        await Promise.resolve();
        await Promise.resolve();
        expect(fetchMock.mock.calls[0][0]).toBe('/api/seizures/11');
        expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
        dlg.showModal = savedShowModal;
    });
});

describe('Edit/Delete-Steuerung (Coverage)', () => {
    it('cancelEditMode setzt Formular und Labels auf Erfassen zurück', () => {
        cancelEditMode();
        expect(document.getElementById('log-card-title').textContent).toBe('Anfall erfassen');
        expect(document.getElementById('log-submit').textContent).toBe('Speichern');
        expect(document.getElementById('log-cancel').style.display).toBe('none');
        expect(_getEditingId()).toBeNull();
    });

    it('Löschen-Dialog: Abbrechen schließt ohne Löschung', async () => {
        mockFetch([{ id: 5, occurred_at: '2024-01-15T10:00:00Z', type: 'focal' }]);
        await loadEvents();
        document.querySelector('[data-del-id]').click();
        const dlg = document.getElementById('seizure-delete-confirm');
        expect(dlg.showModal).toHaveBeenCalled();
        document.getElementById('seizure-delete-cancel').click();
        expect(dlg.close).toHaveBeenCalled();
    });

    it('Löschen-Dialog: Bestätigen löscht den vorgemerkten Eintrag', async () => {
        mockFetch([{ id: 9, occurred_at: '2024-01-15T10:00:00Z', type: 'focal' }]);
        await loadEvents();
        document.querySelector('[data-del-id]').click();
        const delFetch = vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue([]) });
        vi.stubGlobal('fetch', delFetch);
        document.getElementById('seizure-delete-ok').click();
        await vi.waitFor(() =>
            expect(delFetch).toHaveBeenCalledWith('/api/seizures/9', { method: 'DELETE' }),
        );
    });
});
