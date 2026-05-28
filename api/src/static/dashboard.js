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
import { loadEvidence } from './dashboard-hero.js';
import { load, loadReadiness, loadMlInsights, loadEnergyMetrics, loadTrainingLoad } from './dashboard-loaders.js';
import { showToast, loadMlStatus, loadSyncStatus, triggerSync } from './dashboard-status.js';

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
        b.classList.toggle('active', +b.dataset.days === days);
    });
    updateNavBar();
    load(days);
    loadTrainingLoad(days).catch(() => {});
}

document.querySelectorAll('.time-btn').forEach((btn) => {
    btn.addEventListener('click', () => setDays(+btn.dataset.days));
});
document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
});
document.getElementById('sync-btn').addEventListener('click', triggerSync);
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
loadMlInsights().catch(() => {});
loadEnergyMetrics().catch(() => {});
loadSyncStatus();
loadMlStatus();
