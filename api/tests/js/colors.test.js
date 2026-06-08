import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it } from 'vitest';

// colors.js ist ein klassisches globales <script> (kein ES-Modul). Wir lesen die
// echte Datei und evaluieren sie via `new Function` mit gesetzter/entfernter
// .dark-Klasse — so wird die reale Theme-Verzweigung getestet.
const SRC = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '../../src/static/colors.js'), 'utf8');

function loadPalette(dark) {
    document.documentElement.classList.toggle('dark', dark);
    // colors.js endet mit `const C = ...`; C im Function-Scope zurückgeben.
    return new Function(`${SRC}\nreturn C;`)();
}

function relLuminance(hex) {
    const ch = (i) => {
        const c = parseInt(hex.slice(i, i + 2), 16) / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * ch(1) + 0.7152 * ch(3) + 0.0722 * ch(5);
}

function contrast(a, b) {
    const l1 = relLuminance(a);
    const l2 = relLuminance(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

const DARK_CARD = '#1e293b';
const LIGHT_CARD = '#ffffff';

afterEach(() => document.documentElement.classList.remove('dark'));

describe('chart palette contrast (WCAG 1.4.11, ≥ 3:1)', () => {
    it('every dark-mode data color meets 3:1 on the dark card', () => {
        const C = loadPalette(true);
        for (const [name, hex] of Object.entries(C)) {
            expect(contrast(hex, DARK_CARD), `dark ${name} (${hex}) on ${DARK_CARD}`).toBeGreaterThanOrEqual(3);
        }
    });

    it('every light-mode data color meets 3:1 on the white card', () => {
        const C = loadPalette(false);
        for (const [name, hex] of Object.entries(C)) {
            expect(contrast(hex, LIGHT_CARD), `light ${name} (${hex}) on ${LIGHT_CARD}`).toBeGreaterThanOrEqual(3);
        }
    });

    it('selects the dark palette only when the dark class is present', () => {
        expect(loadPalette(true).sleepDeep).toBe('#6366f1');
        expect(loadPalette(false).sleepDeep).toBe('#4f46e5');
    });

    it('exposes the same set of color keys in both themes', () => {
        expect(Object.keys(loadPalette(true)).sort()).toEqual(Object.keys(loadPalette(false)).sort());
    });
});
