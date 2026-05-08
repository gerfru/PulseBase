const SECTION = document.body.dataset.section;
const GRID    = { color: 'rgba(255,255,255,.06)' };

function fmtDate(s) {
    return new Date(s).toLocaleDateString('de-AT', { day: '2-digit', month: 'short' });
}

function statTile(label, value, sub) {
    return `<div class="stat-tile">
        <div class="stat-label">${label}</div>
        <div class="stat-value" style="font-size:1.45rem">${value}</div>
        ${sub ? `<div style="font-size:.73rem;color:var(--muted);margin-top:3px">${sub}</div>` : ''}
    </div>`;
}

// ── Anomalie ──────────────────────────────────────────────────────────────

function renderAnomaly(today, history) {
    const anomaly = today['anomaly_hr'];
    const hist    = history['anomaly_hr'] || [];
    if (!anomaly && !hist.length) return;

    document.getElementById('anomaly-card').style.display = '';

    const z      = anomaly?.z_score;
    const mean   = anomaly?.baseline_mean;
    const std    = anomaly?.baseline_std;
    const nAnoms = hist.filter(h => h.is_anomaly).length;

    document.getElementById('anomaly-stats').innerHTML = [
        statTile('z-Score heute', z != null ? z.toFixed(2) : '—', anomaly?.is_anomaly ? '⚠ Anomalie' : '✓ Normal'),
        statTile('Baseline Ø', mean != null ? `${Math.round(mean)} bpm` : '—', 'Ruhepuls-Mittelwert'),
        statTile('Baseline σ', std != null ? std.toFixed(1) : '—', 'Standardabweichung'),
        statTile('Anomalien', nAnoms, 'letzte 30 Tage'),
    ].join('');

    if (!hist.length) return;

    const labels = hist.map(h => fmtDate(h.date));
    const vals   = hist.map(h => h.z_score ?? null);
    const colors = hist.map(h => h.is_anomaly ? 'rgba(239,68,68,.80)' : 'rgba(99,102,241,.70)');

    new Chart(document.getElementById('anomaly-chart'), {
        type: 'bar',
        data: { labels, datasets: [{ label: 'z-Score', data: vals, backgroundColor: colors, borderRadius: 3 }] },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => `z = ${ctx.parsed.y?.toFixed(2)}` } },
            },
            scales: {
                y: { title: { display: true, text: 'z-Score' }, grid: GRID },
                x: { grid: GRID },
            },
        },
    });
}

// ── Readiness ─────────────────────────────────────────────────────────────

function renderReadiness(today, history) {
    const rf    = today['readiness_rf'];
    const hist  = history['readiness_rf'] || [];
    const mmeta = today['model_meta_rf'];

    if (!rf && !hist.length && !mmeta) return;

    document.getElementById('rf-card').style.display = '';

    const score  = rf?.value;
    const cls    = score >= 80 ? 'badge-balanced' : score >= 50 ? 'badge-unbalanced' : 'badge-poor';
    const avg    = hist.length ? Math.round(hist.reduce((s, h) => s + h.value, 0) / hist.length) : null;
    const avgCls = avg >= 80 ? 'badge-balanced' : avg >= 50 ? 'badge-unbalanced' : 'badge-poor';

    document.getElementById('rf-stats').innerHTML = [
        statTile('Prognose morgen', score != null ? `<span class="badge ${cls}" style="font-size:1.2rem">${Math.round(score)}</span>` : '—'),
        statTile('Ø letzte 30T',    avg   != null ? `<span class="badge ${avgCls}" style="font-size:1.2rem">${avg}</span>` : '—', 'Readiness 0–100'),
        statTile('Trainings-Rows',  mmeta?.n_rows ?? '—', 'für RF-Modell genutzt'),
        statTile('Features',        mmeta?.features?.length ?? '—', mmeta?.features?.join(', ') ?? ''),
    ].join('');

    if (hist.length >= 2) {
        new Chart(document.getElementById('rf-chart'), {
            type: 'line',
            data: {
                labels: hist.map(h => fmtDate(h.date)),
                datasets: [{
                    label: 'Readiness',
                    data: hist.map(h => h.value),
                    borderColor: 'rgba(99,102,241,1)',
                    backgroundColor: 'rgba(99,102,241,.12)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 3,
                }],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { min: 0, max: 100, title: { display: true, text: 'Readiness' }, grid: GRID },
                    x: { grid: GRID },
                },
            },
        });
    }

    if (mmeta?.importances && Object.keys(mmeta.importances).length) {
        document.getElementById('rf-importance').style.display = '';

        const feats  = Object.keys(mmeta.importances);
        const imps   = feats.map(f => mmeta.importances[f]);
        const colors = ['rgba(99,102,241,.75)', 'rgba(245,158,11,.75)', 'rgba(16,185,129,.75)'];

        new Chart(document.getElementById('importance-chart'), {
            type: 'bar',
            data: {
                labels: feats,
                datasets: [{
                    label: 'Importance',
                    data: imps,
                    backgroundColor: colors.slice(0, feats.length),
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: ctx => `${(ctx.parsed.x * 100).toFixed(1)} %` } },
                },
                scales: {
                    x: { min: 0, max: 1, ticks: { callback: v => `${(v * 100).toFixed(0)} %` }, grid: GRID },
                    y: { grid: { display: false } },
                },
            },
        });

        const trainedAt = mmeta.trained_at
            ? new Date(mmeta.trained_at).toLocaleDateString('de-AT')
            : '—';
        document.getElementById('rf-meta').innerHTML =
            `<div style="font-size:.8rem;color:var(--muted)">Modell trainiert am ${trainedAt} · `
            + `RandomForestRegressor, 100 Bäume · `
            + `${mmeta.n_rows} Trainings-Rows</div>`;
    }
}

// ── Korrelationen ─────────────────────────────────────────────────────────

function renderCorrelations(today) {
    const CORR_META = {
        'correlation_sleep_hrv': {
            label:    'Schlaf → HRV (nächster Tag)',
            desc:     'Besserer Schlaf geht typischerweise mit einer höheren HRV am nächsten Morgen einher.',
            expected: 'positiv',
        },
        'correlation_sleep_rhr': {
            label:    'Schlaf → Ruhepuls (nächster Tag)',
            desc:     'Schlechter Schlaf erhöht typischerweise den Ruhepuls am Folgetag.',
            expected: 'negativ',
        },
        'correlation_bb_rhr': {
            label:    'Body Battery → Ruhepuls (nächster Tag)',
            desc:     'Hohe Body Battery (gute Erholung) korreliert mit niedrigerem Ruhepuls am nächsten Tag.',
            expected: 'negativ',
        },
    };

    const items = [];
    for (const [key, meta] of Object.entries(CORR_META)) {
        const corr = today[key];
        if (!corr || corr.r === null) continue;

        const absR     = Math.abs(corr.r);
        const dir      = corr.r >= 0 ? 'positiv' : 'negativ';
        const strength = absR >= 0.6 ? 'starker' : absR >= 0.3 ? 'moderater' : 'schwacher';
        const barColor = corr.r >= 0 ? 'rgba(99,102,241,.75)' : 'rgba(245,158,11,.75)';
        const dirMatch = dir === meta.expected;

        items.push(`<div class="corr-row">
            <div class="corr-label">${meta.label}</div>
            <div class="corr-bar-wrap">
                <div class="corr-bar" style="width:${absR * 100}%;background:${barColor}"></div>
            </div>
            <div class="corr-r">r = ${corr.r.toFixed(2)}</div>
            <div class="corr-meta">${strength} ${dir}er Zusammenhang · n = ${corr.n} Nächte · ${dirMatch ? '✓ erwartete Richtung' : '↔ unerwartete Richtung'}</div>
            <div class="corr-desc">${meta.desc}</div>
        </div>`);
    }

    if (!items.length) return;
    document.getElementById('corr-card').style.display = '';
    document.getElementById('corr-items').innerHTML = items.join('');
}

// ── Body Battery Muster ───────────────────────────────────────────────────

function renderBatteryPattern(today) {
    const bp = today['battery_pattern'];
    if (!bp || !bp.pattern) return;

    document.getElementById('bp-card').style.display = '';

    const BP_LABELS = { stabil_hoch: 'Hohe & stabile Energie', erholung: 'Erholung', erschoepft: 'Erschöpft / hohe Belastung' };
    const BP_ICONS  = { stabil_hoch: '⚡', erholung: '🔄', erschoepft: '📉' };
    const feat = bp.features || {};

    const rows = [
        ['Morgen (06–09h)',  feat.morning_avg?.toFixed(1) ?? '—', 'Startenergie nach Schlaf'],
        ['Abend (20–23h)',   feat.evening_avg?.toFixed(1) ?? '—', 'Endenergie des Tages'],
        ['Tagesreichweite',  feat.daily_range?.toFixed(1) ?? '—', 'max − min (Energieschwankung)'],
        ['Ø Niveau (AUC)',   feat.auc?.toFixed(1) ?? '—',         'Gesamtenergieniveau des Tages'],
        ['Einbrüche',        feat.n_dips ?? '—',                  'Abfälle > 10 Punkte (Belastungsspitzen)'],
    ].map(([label, val, sub]) =>
        `<tr>
            <td class="kv-label" style="padding:var(--sp-2) var(--sp-3) var(--sp-2) 0;width:38%">${label}</td>
            <td style="font-weight:700;padding:var(--sp-2) var(--sp-3) var(--sp-2) 0;width:18%">${val}</td>
            <td class="kv-label" style="font-size:.75rem">${sub}</td>
        </tr>`
    ).join('');

    document.getElementById('bp-content').innerHTML = `
        <div style="display:flex;align-items:center;gap:var(--sp-4);margin-bottom:var(--sp-5)">
            <span style="font-size:2.8rem;line-height:1">${BP_ICONS[bp.pattern] ?? '•'}</span>
            <div>
                <div style="font-size:1.15rem;font-weight:700;color:var(--text)">${BP_LABELS[bp.pattern] ?? bp.pattern}</div>
                <div style="font-size:.82rem;color:var(--muted);margin-top:3px">Cluster ${bp.cluster} · k-Means auf 5 Body-Battery-Features</div>
            </div>
        </div>
        <table class="bp-feature-table">
            <thead>
                <tr>
                    <th class="stat-label" style="text-align:left;padding-bottom:var(--sp-2)">Feature</th>
                    <th class="stat-label" style="text-align:left;padding-bottom:var(--sp-2)">Wert heute</th>
                    <th class="stat-label" style="text-align:left;padding-bottom:var(--sp-2)">Bedeutung</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;
}

// ── Init ──────────────────────────────────────────────────────────────────

async function loadPage() {
    const [today, history] = await Promise.all([
        fetch('/api/ml-insights').then(r => r.json()),
        fetch('/api/ml-history?days=30').then(r => r.json()),
    ]);

    if (SECTION === 'anomaly')      renderAnomaly(today, history);
    else if (SECTION === 'readiness')   renderReadiness(today, history);
    else if (SECTION === 'correlations') renderCorrelations(today);
    else if (SECTION === 'battery')     renderBatteryPattern(today);
}

loadPage().catch(console.error);
