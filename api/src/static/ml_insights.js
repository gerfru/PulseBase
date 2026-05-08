const SECTION = document.body.dataset.section;
const GRID    = { color: 'rgba(255,255,255,.06)' };

function infoBox(title, html) {
    return `<div class="ml-info">
        <div class="ml-info-title">💡 ${title}</div>
        ${html}
    </div>`;
}

function scaleRow(key, desc) {
    return `<div class="ml-info-scale-row">
        <span class="ml-info-scale-key">${key}</span>
        <span>${desc}</span>
    </div>`;
}

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

    document.getElementById('anomaly-card').insertAdjacentHTML('beforeend', infoBox(
        'Was bedeuten diese Zahlen?',
        `<p>Dein Ruhepuls schwankt jeden Tag ein bisschen — das ist normal.
        Der <strong>z-Score</strong> misst, wie ungewöhnlich der heutige Wert im Vergleich
        zu deinen letzten 30 Tagen ist. Null bedeutet: genau wie immer.</p>
        <div class="ml-info-scale">
            ${scaleRow('0', 'Perfekt normal — genau dein Durchschnitt')}
            ${scaleRow('±1', 'Leicht abweichend — völlig okay, passiert oft')}
            ${scaleRow('±2', 'Deutlich abweichend — passiert nur ~5× pro 100 Tagen')}
            ${scaleRow('±3', 'Stark abweichend — selten, möglicher Hinweis auf Stress, Krankheit oder Überbelastung')}
        </div>
        <p><strong>Baseline Ø</strong> ist dein persönlicher Normalwert (Durchschnitt der letzten 30 Tage).
        <strong>Baseline σ</strong> zeigt deine typische Schwankungsbreite — je kleiner, desto stabiler bist du normalerweise.</p>`
    ));
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

    document.getElementById('rf-card').insertAdjacentHTML('beforeend', infoBox(
        'Wie funktioniert die Prognose?',
        `<p>Das Modell schaut sich deine vergangenen Schlaf- und Pulswerte an und lernt,
        wie sich diese auf deine Erholung auswirken. Aus diesem Muster schätzt es,
        wie fit du <strong>morgen</strong> sein wirst — auf einer Skala von 0 bis 100.</p>
        <div class="ml-info-scale">
            ${scaleRow('80 – 100', 'Top-Form — intensive Einheiten sind kein Problem')}
            ${scaleRow('50 – 79', 'Gut erholt — moderates Training passt')}
            ${scaleRow('0 – 49', 'Erholung empfohlen — lieber ruhig angehen')}
        </div>
        <p><strong>Feature Importance</strong> zeigt, welche Werte den größten Einfluss
        auf die Prognose haben — zum Beispiel: „Schlaf zählt 60 %, Ruhepuls 40 %."
        Das Modell lernt diese Gewichtung selbst aus deinen echten Daten.</p>`
    ));
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

    document.getElementById('corr-card').insertAdjacentHTML('beforeend', infoBox(
        'Was ist r und was bedeutet der Balken?',
        `<p>Der <strong>r-Wert</strong> misst, ob zwei Dinge zusammenhängen —
        auf einer Skala von −1 bis +1.</p>
        <div class="ml-info-scale">
            ${scaleRow('+1', 'Perfekter Zusammenhang: steigt A, steigt auch B immer')}
            ${scaleRow('0', 'Kein Zusammenhang: A und B haben nichts miteinander zu tun')}
            ${scaleRow('−1', 'Gegenteiliger Zusammenhang: steigt A, fällt B immer')}
        </div>
        <p>Der <strong>Balken</strong> zeigt die Stärke (je länger, desto stärker).
        Die Farbe zeigt die Richtung: lila = positiv, orange = negativ.</p>
        <div class="ml-info-scale">
            ${scaleRow('|r| > 0,6', 'Starker Zusammenhang — gut erkennbares Muster')}
            ${scaleRow('|r| 0,3–0,6', 'Moderater Zusammenhang — Tendenz vorhanden')}
            ${scaleRow('|r| < 0,3', 'Schwacher oder kein Zusammenhang')}
        </div>
        <p>Wichtig: Zusammenhang bedeutet nicht Ursache. Schlechter Schlaf
        <em>geht einher</em> mit höherem Puls — ob einer den anderen verursacht,
        sagt r nicht.</p>`
    ));
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
        </table>
        ${infoBox('Wie wird das Muster erkannt?',
            `<p>Deine Body Battery zeigt über den Tag, wie viel Energie du hast — von 100 (voll geladen) bis 5 (leer).
            Das System schaut sich 5 Kennzahlen deiner heutigen Kurve an und vergleicht sie
            mit all deinen bisherigen Tagen. Dann ordnet es den Tag einem von 3 Mustern zu:</p>
            <div class="ml-info-scale">
                ${scaleRow('⚡ Hohe & stabile Energie', 'Morgens hoch gestartet, abends noch viel übrig — guter Erholungstag')}
                ${scaleRow('🔄 Erholung', 'Mittleres Niveau, Körper lädt sich auf — normaler Alltag')}
                ${scaleRow('📉 Erschöpft', 'Stark abgefallen, viele Einbrüche — Belastung oder zu wenig Schlaf')}
            </div>
            <p><strong>Tagesreichweite</strong> = höchster minus niedrigster Wert des Tages.
            Große Reichweite = viele Belastungsspitzen. <strong>AUC</strong> (Area under curve) =
            vereinfacht das durchschnittliche Energieniveau über den ganzen Tag.</p>`
        )}`;
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
