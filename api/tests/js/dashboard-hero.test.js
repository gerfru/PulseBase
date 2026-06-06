import { describe, it, expect } from 'vitest';
import { heroRecommendation } from '../../src/static/dashboard-hero.js';

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
