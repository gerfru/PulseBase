import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
    currentDays,
    currentOffset,
    resetOffset,
    setCurrentDays,
    incrementOffset,
    getEndDate,
    updateNavBar,
    setTab,
    TABS,
    CHART_HASHES,
} from '../../src/static/dashboard-nav.js';
import { charts } from '../../src/static/dashboard-utils.js';

// Reset module state before each test since currentDays/currentOffset are module-level lets
beforeEach(() => {
    resetOffset();
    setCurrentDays(7);
    vi.useRealTimers();
});

describe('resetOffset', () => {
    it('sets currentOffset to 0', () => {
        incrementOffset(3);
        resetOffset();
        expect(currentOffset).toBe(0);
    });
});

describe('setCurrentDays', () => {
    it('updates currentDays', () => {
        setCurrentDays(30);
        expect(currentDays).toBe(30);
    });
});

describe('incrementOffset', () => {
    it('increments from 0', () => {
        incrementOffset(1);
        expect(currentOffset).toBe(1);
    });

    it('cannot go below 0 (lower bound)', () => {
        incrementOffset(-1);
        expect(currentOffset).toBe(0);
    });

    it('accumulates correctly', () => {
        incrementOffset(1);
        incrementOffset(1);
        expect(currentOffset).toBe(2);
        incrementOffset(-1);
        expect(currentOffset).toBe(1);
    });

    it('clamps to 0 when decrement would go negative', () => {
        incrementOffset(1);
        incrementOffset(-5);
        expect(currentOffset).toBe(0);
    });
});

describe('getEndDate', () => {
    it('returns null when offset is 0', () => {
        expect(getEndDate()).toBeNull();
    });

    it('returns a YYYY-MM-DD string when offset > 0', () => {
        vi.useFakeTimers({ now: new Date('2024-01-15T12:00:00Z') });
        setCurrentDays(7);
        incrementOffset(1);
        const result = getEndDate();
        expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(result).toBe('2024-01-08');
    });

    it('accounts for currentDays in offset calculation', () => {
        vi.useFakeTimers({ now: new Date('2024-02-29T12:00:00Z') });
        setCurrentDays(14);
        incrementOffset(1);
        const result = getEndDate();
        expect(result).toBe('2024-02-15');
    });
});

describe('updateNavBar', () => {
    it('writes the date range to #nav-range', () => {
        document.body.innerHTML = `
            <span id="nav-range"></span>
            <button id="nav-forward"></button>
        `;
        vi.useFakeTimers({ now: new Date('2024-01-15T12:00:00Z') });
        setCurrentDays(7);
        updateNavBar();
        const text = document.getElementById('nav-range').textContent;
        expect(text).toMatch(/09\.01/); // start: 2024-01-09
        expect(text).toMatch(/15\.01/); // end:   2024-01-15
    });

    it('disables forward button when offset is 0', () => {
        document.body.innerHTML = `
            <span id="nav-range"></span>
            <button id="nav-forward"></button>
        `;
        resetOffset();
        updateNavBar();
        expect(document.getElementById('nav-forward').disabled).toBe(true);
    });
});

describe('setTab', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div class="tab-panel" id="tab-training"></div>
            <div class="tab-panel" id="tab-verlauf" style="display:none"></div>
            <div class="tab-panel" id="tab-erholung" style="display:none"></div>
            <button class="tab-btn" data-tab="training" class="active"></button>
            <button class="tab-btn" data-tab="verlauf"></button>
            <button class="tab-btn" data-tab="erholung"></button>
        `;
    });

    it('shows the selected tab panel', () => {
        setTab('verlauf');
        expect(document.getElementById('tab-verlauf').style.display).toBe('');
    });

    it('hides all other tab panels', () => {
        setTab('erholung');
        expect(document.getElementById('tab-training').style.display).toBe('none');
        expect(document.getElementById('tab-verlauf').style.display).toBe('none');
    });

    it('sets active class on the matching tab button', () => {
        setTab('verlauf');
        const btns = document.querySelectorAll('.tab-btn');
        const activeBtn = [...btns].find((b) => b.dataset.tab === 'verlauf');
        expect(activeBtn.classList.contains('active')).toBe(true);
    });

    it('calls resize() on all registered charts after 50 ms', async () => {
        const mockChart = { resize: vi.fn() };
        charts['nav-resize-test'] = mockChart;

        vi.useFakeTimers();
        setTab('training');
        await vi.advanceTimersByTimeAsync(51);

        expect(mockChart.resize).toHaveBeenCalledOnce();
        delete charts['nav-resize-test'];
    });
});

describe('TABS', () => {
    it('contains the three expected tab names', () => {
        expect(TABS).toEqual(['training', 'verlauf', 'erholung']);
    });
});

describe('CHART_HASHES', () => {
    it('maps chart hashes to [tab, chartId] tuples', () => {
        expect(CHART_HASHES.sleep).toEqual(['erholung', 'sleep-chart']);
        expect(CHART_HASHES.hrv).toEqual(['erholung', 'hrv-trend-chart']);
        expect(CHART_HASHES.battery).toEqual(['verlauf', 'battery-chart']);
        expect(CHART_HASHES.training).toEqual(['training', 'training-load-chart']);
    });
});
