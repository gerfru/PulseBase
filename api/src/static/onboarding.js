// Onboarding-/Datenlatenz-Hinweis: einmalig sichtbar, per localStorage dismissbar.
// Erklärt neuen Nutzern, dass Trends/ML erst nach Tagen an Daten erscheinen (UX-Review E-1).

const STORAGE_KEY = 'pb-onboarding-dismissed';

function isDismissed() {
    try {
        return localStorage.getItem(STORAGE_KEY) === '1';
    } catch {
        // localStorage kann blockiert sein (Private Mode) — Hinweis dann einfach anzeigen.
        return false;
    }
}

function setDismissed() {
    try {
        localStorage.setItem(STORAGE_KEY, '1');
    } catch {
        /* ignorieren */
    }
}

export function initOnboardingHint() {
    const hint = document.getElementById('onboarding-hint');
    if (!hint || isDismissed()) return;
    hint.style.display = '';
    document.getElementById('onboarding-hint-close')?.addEventListener('click', () => {
        hint.style.display = 'none';
        setDismissed();
    });
}
