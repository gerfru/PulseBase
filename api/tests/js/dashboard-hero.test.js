import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
    heroRecommendation,
    submitMlFeedback,
    applyFeedbackState,
    loadMlFeedback,
} from '../../src/static/dashboard-hero.js';

describe('heroRecommendation', () => {
    it('returns empty string for null', () => {
        expect(heroRecommendation(null)).toBe('');
        expect(heroRecommendation(undefined)).toBe('');
    });

    // Threshold 75 for the green/best band
    it('returns the good-recovery suggestion at score 75 (lower threshold)', () => {
        const html = heroRecommendation(75);
        expect(html).toContain('gute Erholung');
        expect(html).toContain('rec-green');
    });

    it('returns the good-recovery suggestion above 75', () => {
        expect(heroRecommendation(100)).toContain('gute Erholung');
        expect(heroRecommendation(80)).toContain('gute Erholung');
        expect(heroRecommendation(76)).toContain('gute Erholung');
    });

    // B-3: wording is a hedged suggestion, not a directive imperative
    it('uses hedged suggestion wording (no imperative)', () => {
        const html = heroRecommendation(80);
        expect(html).toContain('wäre möglich');
        expect(html).not.toContain('Voll belasten');
    });

    it('does NOT return the good-recovery suggestion at score 74 (boundary)', () => {
        const html = heroRecommendation(74);
        expect(html).not.toContain('gute Erholung');
        expect(html).toContain('moderates Training');
        expect(html).toContain('rec-amber');
    });

    it('returns the moderate suggestion for scores 60–74', () => {
        expect(heroRecommendation(74)).toContain('moderates Training');
        expect(heroRecommendation(60)).toContain('moderates Training');
    });

    it('returns the light-training suggestion for scores 40–59', () => {
        expect(heroRecommendation(59)).toContain('eher leicht trainieren');
        expect(heroRecommendation(40)).toContain('eher leicht trainieren');
        expect(heroRecommendation(59)).toContain('rec-amber');
    });

    it('returns the rest suggestion for scores below 40', () => {
        expect(heroRecommendation(39)).toContain('eher ruhen');
        expect(heroRecommendation(0)).toContain('eher ruhen');
        expect(heroRecommendation(0)).toContain('rec-red');
    });

    it('wraps output in a <p> tag with hero-recommendation class', () => {
        const html = heroRecommendation(78);
        expect(html).toMatch(/^<p class="hero-recommendation/);
        expect(html).toContain('</p>');
    });
});

// ── ML-Feedback (👍/👎) — UX-Review [D3-1] ──────────────────────────────────────

function feedbackDom(model) {
    document.body.innerHTML =
        `<button data-fb-model="${model}" data-fb-val="1" aria-pressed="false">👍</button>` +
        `<button data-fb-model="${model}" data-fb-val="0" aria-pressed="false">👎</button>`;
    return {
        up: document.querySelector(`[data-fb-model="${model}"][data-fb-val="1"]`),
        down: document.querySelector(`[data-fb-model="${model}"][data-fb-val="0"]`),
    };
}

describe('ML feedback', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('applyFeedbackState highlights only the matching button', () => {
        const { up, down } = feedbackDom('readiness_rf');
        applyFeedbackState({ readiness_rf: true });
        expect(up.classList.contains('active')).toBe(true);
        expect(up.getAttribute('aria-pressed')).toBe('true');
        expect(down.classList.contains('active')).toBe(false);
        expect(down.getAttribute('aria-pressed')).toBe('false');
    });

    it('applyFeedbackState highlights 👎 when helpful=false', () => {
        const { up, down } = feedbackDom('anomaly_hr');
        applyFeedbackState({ anomaly_hr: false });
        expect(down.classList.contains('active')).toBe(true);
        expect(up.classList.contains('active')).toBe(false);
    });

    it('submitMlFeedback POSTs the correct body and updates the DOM', async () => {
        const { up } = feedbackDom('readiness_rf');
        const fetchMock = vi.fn().mockResolvedValue({ ok: true });
        vi.stubGlobal('fetch', fetchMock);

        await submitMlFeedback('readiness_rf', true);

        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(fetchMock.mock.calls[0][0]).toBe('/api/ml-feedback');
        const opts = fetchMock.mock.calls[0][1];
        expect(opts.method).toBe('POST');
        expect(JSON.parse(opts.body)).toEqual({ model: 'readiness_rf', helpful: true });
        expect(up.getAttribute('aria-pressed')).toBe('true');
    });

    it('submitMlFeedback rejects on a non-ok response', async () => {
        feedbackDom('readiness_rf');
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
        await expect(submitMlFeedback('readiness_rf', true)).rejects.toThrow();
    });

    it('loadMlFeedback fetches state and applies it', async () => {
        const { down } = feedbackDom('anomaly_hr');
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({ json: () => Promise.resolve({ anomaly_hr: false }) }),
        );
        await loadMlFeedback();
        expect(down.classList.contains('active')).toBe(true);
    });

    it('loadMlFeedback swallows fetch errors', async () => {
        feedbackDom('readiness_rf');
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
        await expect(loadMlFeedback()).resolves.toBeUndefined();
    });
});
