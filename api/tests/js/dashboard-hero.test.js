import { describe, it, expect } from 'vitest';
import { heroRecommendation } from '../../src/static/dashboard-hero.js';

describe('heroRecommendation', () => {
    it('returns empty string for null', () => {
        expect(heroRecommendation(null)).toBe('');
        expect(heroRecommendation(undefined)).toBe('');
    });

    // Threshold changed from 80 to 75 — verify the new boundary
    it('returns Voll belasten at score 75 (lower threshold)', () => {
        const html = heroRecommendation(75);
        expect(html).toContain('Voll belasten');
        expect(html).toContain('rec-green');
    });

    it('returns Voll belasten above 75', () => {
        expect(heroRecommendation(100)).toContain('Voll belasten');
        expect(heroRecommendation(80)).toContain('Voll belasten');
        expect(heroRecommendation(76)).toContain('Voll belasten');
    });

    it('does NOT return Voll belasten at score 74 (old threshold would pass, new does not)', () => {
        const html = heroRecommendation(74);
        expect(html).not.toContain('Voll belasten');
        expect(html).toContain('Moderat trainieren');
        expect(html).toContain('rec-amber');
    });

    it('returns Moderat trainieren for scores 60–74', () => {
        expect(heroRecommendation(74)).toContain('Moderat trainieren');
        expect(heroRecommendation(60)).toContain('Moderat trainieren');
    });

    it('returns Leichtes Training for scores 40–59', () => {
        expect(heroRecommendation(59)).toContain('Leichtes Training');
        expect(heroRecommendation(40)).toContain('Leichtes Training');
        expect(heroRecommendation(59)).toContain('rec-amber');
    });

    it('returns Heute ruhen for scores below 40', () => {
        expect(heroRecommendation(39)).toContain('Heute ruhen');
        expect(heroRecommendation(0)).toContain('Heute ruhen');
        expect(heroRecommendation(0)).toContain('rec-red');
    });

    it('wraps output in a <p> tag with hero-recommendation class', () => {
        const html = heroRecommendation(78);
        expect(html).toMatch(/^<p class="hero-recommendation/);
        expect(html).toContain('</p>');
    });
});
