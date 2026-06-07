import { describe, it, expect, vi, beforeEach } from 'vitest';

const { initOnboardingHint } = await import('../../src/static/onboarding.js');

function render() {
    document.body.innerHTML =
        '<div id="onboarding-hint" style="display:none">' +
        '<button id="onboarding-hint-close"></button>' +
        '</div>';
}

beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    render();
});

describe('initOnboardingHint', () => {
    it('shows the hint when not previously dismissed', () => {
        initOnboardingHint();
        expect(document.getElementById('onboarding-hint').style.display).toBe('');
    });

    it('keeps the hint hidden when already dismissed', () => {
        localStorage.setItem('pb-onboarding-dismissed', '1');
        initOnboardingHint();
        expect(document.getElementById('onboarding-hint').style.display).toBe('none');
    });

    it('hides the hint and persists dismissal on close click', () => {
        initOnboardingHint();
        document.getElementById('onboarding-hint-close').click();
        expect(document.getElementById('onboarding-hint').style.display).toBe('none');
        expect(localStorage.getItem('pb-onboarding-dismissed')).toBe('1');
    });

    it('does nothing when the hint element is absent', () => {
        document.body.innerHTML = '';
        expect(() => initOnboardingHint()).not.toThrow();
    });

    it('shows the hint when localStorage access throws', () => {
        const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        initOnboardingHint();
        expect(document.getElementById('onboarding-hint').style.display).toBe('');
        spy.mockRestore();
    });

    it('swallows errors when persisting the dismissal fails', () => {
        const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        initOnboardingHint();
        expect(() => document.getElementById('onboarding-hint-close').click()).not.toThrow();
        expect(document.getElementById('onboarding-hint').style.display).toBe('none');
        spy.mockRestore();
    });
});
