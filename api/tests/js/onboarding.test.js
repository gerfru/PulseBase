import { describe, it, expect, vi, beforeEach } from 'vitest';

const { initOnboardingHint } = await import('../../src/static/onboarding.js');

function render() {
    document.body.innerHTML =
        '<div id="onboarding-hint" class="is-hidden">' +
        '<button id="onboarding-hint-close"></button>' +
        '</div>';
}

const isHidden = () => document.getElementById('onboarding-hint').classList.contains('is-hidden');

beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    render();
});

describe('initOnboardingHint', () => {
    it('shows the hint when not previously dismissed', () => {
        initOnboardingHint();
        expect(isHidden()).toBe(false);
    });

    it('keeps the hint hidden when already dismissed', () => {
        localStorage.setItem('pb-onboarding-dismissed', '1');
        initOnboardingHint();
        expect(isHidden()).toBe(true);
    });

    it('hides the hint and persists dismissal on close click', () => {
        initOnboardingHint();
        document.getElementById('onboarding-hint-close').click();
        expect(isHidden()).toBe(true);
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
        expect(isHidden()).toBe(false);
        spy.mockRestore();
    });

    it('swallows errors when persisting the dismissal fails', () => {
        const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        initOnboardingHint();
        expect(() => document.getElementById('onboarding-hint-close').click()).not.toThrow();
        expect(isHidden()).toBe(true);
        spy.mockRestore();
    });
});
