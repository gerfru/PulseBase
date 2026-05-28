import { charts } from './dashboard-utils.js';

export let currentDays = 7;
export let currentOffset = 0;

export function resetOffset() {
    currentOffset = 0;
}
export function setCurrentDays(d) {
    currentDays = d;
}
export function incrementOffset(delta) {
    currentOffset = Math.max(0, currentOffset + delta);
}

export function getEndDate() {
    if (currentOffset === 0) return null;
    const d = new Date();
    d.setDate(d.getDate() - currentOffset * currentDays);
    return d.toISOString().slice(0, 10);
}

export function updateNavBar() {
    const end = new Date();
    end.setDate(end.getDate() - currentOffset * currentDays);
    const start = new Date(end);
    start.setDate(start.getDate() - currentDays + 1);
    const fmt = (d) => `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`;
    const rangeEl = document.getElementById('nav-range');
    const fwdEl = document.getElementById('nav-forward');
    if (rangeEl) rangeEl.textContent = `${fmt(start)} – ${fmt(end)}`;
    if (fwdEl) fwdEl.disabled = currentOffset === 0;
}

export const TABS = ['training', 'verlauf', 'erholung'];

export const CHART_HASHES = {
    sleep: ['erholung', 'sleep-chart'],
    hrv: ['erholung', 'hrv-trend-chart'],
    stress: ['verlauf', 'stress-chart'],
    battery: ['verlauf', 'battery-chart'],
    hr: ['verlauf', 'hr-chart'],
    training: ['training', 'training-load-chart'],
    intensity: ['training', 'intensity-chart'],
};

export function setTab(name) {
    document.querySelectorAll('.tab-panel').forEach((p) => {
        p.style.display = 'none';
    });
    document.getElementById(`tab-${name}`).style.display = '';
    document.querySelectorAll('.tab-btn').forEach((b) => {
        b.classList.toggle('active', b.dataset.tab === name);
    });
    history.replaceState(null, '', `#${name}`);
    setTimeout(
        () =>
            Object.values(charts).forEach((c) => {
                c.resize();
            }),
        50,
    );
}
