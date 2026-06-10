import { esc } from './dashboard-utils.js';

let _mlFeedback = {};

export function feedbackButtons(model) {
    const helpful = Object.hasOwn(_mlFeedback, model) ? _mlFeedback[model] : null;
    const up = helpful === true;
    const down = helpful === false;
    return `<div class="ml-feedback" role="group" aria-label="War diese Einschätzung treffend?">
        <span class="ml-feedback-q">Treffend?</span>
        <button type="button" class="ml-feedback-btn${up ? ' active' : ''}" data-fb-model="${esc(model)}" data-fb-val="1" aria-label="Einschätzung war treffend" aria-pressed="${up}">👍</button>
        <button type="button" class="ml-feedback-btn${down ? ' active' : ''}" data-fb-model="${esc(model)}" data-fb-val="0" aria-label="Einschätzung war nicht treffend" aria-pressed="${down}">👎</button>
    </div>`;
}

export function applyFeedbackState(map) {
    _mlFeedback = map || {};
    document.querySelectorAll('[data-fb-model]').forEach((btn) => {
        const m = btn.dataset.fbModel;
        const isUp = btn.dataset.fbVal === '1';
        const has = Object.hasOwn(_mlFeedback, m);
        const on = has && _mlFeedback[m] === isUp;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
}

export async function loadMlFeedback() {
    try {
        const map = await fetch('/api/ml-feedback').then((r) => r.json());
        applyFeedbackState(map);
    } catch (_) {}
}

export async function submitMlFeedback(model, helpful) {
    const res = await fetch('/api/ml-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, helpful }),
    });
    if (!res.ok) throw new Error('feedback failed');
    applyFeedbackState({ ..._mlFeedback, [model]: helpful });
}
