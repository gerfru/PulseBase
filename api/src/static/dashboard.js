import './chart-utils.js';
import {
    currentDays,
    getEndDate,
    updateNavBar,
    setCurrentDays,
    incrementOffset,
    resetOffset,
    setTab,
    TABS,
    CHART_HASHES,
} from './dashboard-nav.js';
import { loadEvidence, buildMlTabs } from './dashboard-hero.js';
import { load, loadReadiness, loadMlInsights, loadEnergyMetrics, loadTrainingLoad } from './dashboard-loaders.js';
import { showToast, loadMlStatus, loadSyncStatus } from './dashboard-status.js';

function shiftPeriod(delta) {
    incrementOffset(delta);
    updateNavBar();
    load(currentDays, getEndDate()).catch(() => {});
    loadTrainingLoad(currentDays).catch(() => {});
}

function setDays(days) {
    setCurrentDays(days);
    resetOffset();
    document.querySelectorAll('.time-btn').forEach((b) => {
        const active = +b.dataset.days === days;
        b.classList.toggle('active', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    updateNavBar();
    load(days);
    loadTrainingLoad(days).catch(() => {});
}

document.querySelectorAll('.time-btn').forEach((btn) => {
    btn.addEventListener('click', () => setDays(+btn.dataset.days));
});
const _tabBtns = [...document.querySelectorAll('.tab-btn')];
_tabBtns.forEach((btn, i) => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
    // ARIA Tabs-Pattern: Pfeil-/Pos1-/Ende-Navigation zwischen Tabs
    btn.addEventListener('keydown', (e) => {
        let next = null;
        if (e.key === 'ArrowRight') next = _tabBtns[(i + 1) % _tabBtns.length];
        else if (e.key === 'ArrowLeft') next = _tabBtns[(i - 1 + _tabBtns.length) % _tabBtns.length];
        else if (e.key === 'Home') next = _tabBtns[0];
        else if (e.key === 'End') next = _tabBtns[_tabBtns.length - 1];
        if (next) {
            e.preventDefault();
            setTab(next.dataset.tab);
            next.focus();
        }
    });
});
document
    .getElementById('formula-dialog-close')
    .addEventListener('click', () => document.getElementById('formula-dialog').close());
document.getElementById('nav-back').addEventListener('click', () => shiftPeriod(1));
document.getElementById('nav-forward').addEventListener('click', () => shiftPeriod(-1));
document.getElementById('activities-container').addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-id]');
    if (tr) location.href = `/activity/${tr.dataset.id}`;
});

updateNavBar();
const _hash = location.hash.slice(1);
if (TABS.includes(_hash)) {
    setTab(_hash);
} else if (CHART_HASHES[_hash]) {
    const [_tab, _chartId] = CHART_HASHES[_hash];
    setTab(_tab);
    setTimeout(() => {
        document.getElementById(_chartId)?.closest('.card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 200);
} else {
    setTab('training');
}
loadEvidence().catch(() => {});
load(currentDays).catch(() => showToast('Dashboard konnte nicht geladen werden', 'error'));
loadTrainingLoad().catch(() => {});
loadReadiness().catch(() => showToast('Readiness-Score konnte nicht geladen werden', 'error'));
loadMlInsights()
    .then(() => buildMlTabs())
    .catch(() => {});
loadEnergyMetrics().catch(() => {});
loadSyncStatus();
loadMlStatus();
