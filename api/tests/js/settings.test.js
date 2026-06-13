import { describe, it, expect, vi, beforeEach } from 'vitest';

// settings.js attaches listeners at import time, so the DOM must exist first.
document.body.innerHTML =
    '<button id="profile-save"></button>' +
    '<input id="dob" />' +
    '<select id="sex"><option value=""></option></select>' +
    '<input id="weight" type="number" />' +
    '<span id="profile-msg" style="display:none"></span>' +
    '<input type="checkbox" id="epilepsy-toggle" />' +
    '<span id="epilepsy-link"></span>' +
    '<input type="checkbox" id="spo2-toggle" />' +
    '<form id="libre-unlink-form" action="/libre/unlink"></form>' +
    '<button id="libre-unlink-btn"></button>' +
    '<dialog id="libre-confirm"></dialog>' +
    '<button id="libre-confirm-cancel"></button>' +
    '<button id="libre-confirm-ok"></button>';

const dialog = document.getElementById('libre-confirm');
dialog.showModal = vi.fn();
dialog.close = vi.fn();
const submitSpy = vi.fn();
document.getElementById('libre-unlink-form').submit = submitSpy;

vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));

await import('../../src/static/settings.js');

beforeEach(() => {
    vi.clearAllMocks();
});

describe('profile save', () => {
    it('includes weight_kg in the fetch body when a value is entered', async () => {
        document.getElementById('dob').value = '1990-01-01';
        document.getElementById('sex').value = '';
        document.getElementById('weight').value = '75.5';
        document.getElementById('profile-save').click();
        await Promise.resolve();
        const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1].body);
        expect(body.weight_kg).toBeCloseTo(75.5);
    });

    it('sends weight_kg as null when the field is empty', async () => {
        document.getElementById('dob').value = '';
        document.getElementById('sex').value = '';
        document.getElementById('weight').value = '';
        document.getElementById('profile-save').click();
        await Promise.resolve();
        const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1].body);
        expect(body.weight_kg).toBeNull();
    });
});

describe('Libre unlink confirmation', () => {
    it('opens the confirmation dialog instead of submitting immediately', () => {
        document.getElementById('libre-unlink-btn').click();
        expect(dialog.showModal).toHaveBeenCalled();
        expect(submitSpy).not.toHaveBeenCalled();
    });

    it('closes the dialog without submitting on cancel', () => {
        document.getElementById('libre-confirm-cancel').click();
        expect(dialog.close).toHaveBeenCalled();
        expect(submitSpy).not.toHaveBeenCalled();
    });

    it('submits the unlink form on confirm', () => {
        document.getElementById('libre-confirm-ok').click();
        expect(submitSpy).toHaveBeenCalled();
    });
});
