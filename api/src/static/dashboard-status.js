import { currentDays, resetOffset, updateNavBar } from './dashboard-nav.js';
import { load, loadTrainingLoad, loadReadiness, loadMlInsights, loadEnergyMetrics } from './dashboard-loaders.js';

let _toastTimer = null;

export function showToast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `toast show${type ? ` ${type}` : ''}`;
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => el.classList.remove('show'), 3500);
}

let _mlPollTimer = null;

function setMlStatus(text, visible) {
    const el = document.getElementById('ml-status');
    el.textContent = text;
    el.style.display = visible ? '' : 'none';
}

async function pollMlStatus() {
    try {
        const s = await fetch('/api/ml-status').then((r) => r.json());
        if (s.pending) {
            setMlStatus('🤖 ML läuft…', true);
            _mlPollTimer = setTimeout(pollMlStatus, 8000);
        } else {
            const age = s.last_ml_at ? fmtSyncAge(s.last_ml_at) : null;
            setMlStatus(age ? `🤖 Zuletzt analysiert ${age}` : '', !!age);
            // Defensiv-Guard: pollMlStatus läuft ausschließlich über einen gesetzten
            // Timer → der false-Zweig ist hier unerreichbar (toter Schutzcode).
            /* v8 ignore next */
            if (_mlPollTimer) {
                showToast('ML Einblicke aktualisiert');
                loadMlInsights();
                loadEnergyMetrics().catch(() => {});
                loadReadiness().catch(() => {});
            }
            /* v8 ignore next 2 */
            _mlPollTimer = null;
        }
    } catch {
        /* ignorieren */
    }
}

export async function loadMlStatus() {
    try {
        const s = await fetch('/api/ml-status').then((r) => r.json());
        if (s.pending) {
            setMlStatus('🤖 ML läuft…', true);
            _mlPollTimer = setTimeout(pollMlStatus, 8000);
        } else if (s.last_ml_at) {
            setMlStatus(`🤖 Zuletzt analysiert ${fmtSyncAge(s.last_ml_at)}`, true);
        }
    } catch {
        /* ignorieren */
    }
}

export function fmtSyncAge(iso) {
    const mins = Math.round((Date.now() - new Date(iso)) / 60000);
    if (mins < 2) return 'Gerade eben';
    if (mins < 60) return `vor ${mins}m`;
    return `vor ${Math.round(mins / 60)}h`;
}

let _syncPollTimer = null;

async function pollSyncStatus() {
    try {
        const s = await fetch('/api/sync-status').then((r) => r.json());
        if (s.last_sync_at) {
            document.getElementById('sync-last').textContent = fmtSyncAge(s.last_sync_at);
        }
        if (s.pending) {
            _syncPollTimer = setTimeout(pollSyncStatus, 5000);
        } else {
            // Defensiv-Guard: pollSyncStatus läuft ausschließlich über einen gesetzten
            // Timer → der false-Zweig ist hier unerreichbar (toter Schutzcode).
            /* v8 ignore next */
            if (_syncPollTimer) {
                showToast('Sync abgeschlossen');
                resetOffset();
                updateNavBar();
                load(currentDays);
                loadTrainingLoad(currentDays).catch(() => {});
                loadReadiness();
                loadEnergyMetrics().catch(() => {});
                _mlPollTimer = setTimeout(pollMlStatus, 5000);
            }
            /* v8 ignore next 2 */
            _syncPollTimer = null;
        }
    } catch {
        /* Netzwerkfehler ignorieren */
    }
}

export async function loadSyncStatus() {
    try {
        const s = await fetch('/api/sync-status').then((r) => r.json());
        if (s.last_sync_at) {
            document.getElementById('sync-last').textContent = fmtSyncAge(s.last_sync_at);
        }
        if (s.pending) {
            _syncPollTimer = setTimeout(pollSyncStatus, 5000);
        }
    } catch {
        /* ignorieren */
    }
}
