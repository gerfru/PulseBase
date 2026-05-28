import { describe, it, expect } from 'vitest';
import { fmtDate, fmtHours } from '../../src/static/chart-utils.js';

describe('fmtDate', () => {
    it('returns — for falsy values', () => {
        expect(fmtDate(null)).toBe('—');
        expect(fmtDate(undefined)).toBe('—');
        expect(fmtDate('')).toBe('—');
    });

    it('formats a mid-month date', () => {
        // Uses local date constructor (no timezone offset) so output is deterministic
        const result = fmtDate('2024-06-15');
        expect(result).toMatch(/15/);
        expect(result).toMatch(/06/);
    });

    it('formats year boundaries', () => {
        expect(fmtDate('2024-01-01')).toMatch(/01/);
        expect(fmtDate('2024-12-31')).toMatch(/12/);
    });

    it('handles numeric date-like strings', () => {
        const result = fmtDate('2024-03-05');
        expect(result).toMatch(/03|3/); // month 03
        expect(result).toMatch(/05|5/); // day 05
    });
});

describe('fmtHours', () => {
    it('returns — for falsy values', () => {
        expect(fmtHours(0)).toBe('—');
        expect(fmtHours(null)).toBe('—');
        expect(fmtHours(undefined)).toBe('—');
    });

    it('formats minutes only when less than 1 hour', () => {
        expect(fmtHours(60)).toBe('1m');
        expect(fmtHours(90)).toBe('1m');
        expect(fmtHours(3540)).toBe('59m');
    });

    it('formats hours and minutes', () => {
        expect(fmtHours(3600)).toBe('1h 0m');
        expect(fmtHours(3661)).toBe('1h 1m');
        expect(fmtHours(7200)).toBe('2h 0m');
        expect(fmtHours(7384)).toBe('2h 3m');
    });
});
