import { fmtDate, isDark } from './chart-utils.js';
import { _heroData, buildHeroCard } from './dashboard-hero.js';
import { buildWeeklyReview } from './dashboard-weekly.js';
import { makeChart, showEmpty, hideEmpty, sportLabel, fmtDuration, fmtDist, secToH } from './dashboard-utils.js';

export async function load(days, endDate = null) {
    const ed = endDate ? `&end_date=${endDate}` : '';
    const [activities, daily, sleep, hrv, hrvTrend, trainingStatus, mlHistory] = await Promise.all([
        fetch(`/api/activities?days=${days}${ed}`).then(r => r.json()),
        fetch(`/api/daily?days=${days}${ed}`).then(r => r.json()),
        fetch(`/api/sleep?days=${days}${ed}`).then(r => r.json()),
        fetch('/api/hrv').then(r => r.json()),
        fetch(`/api/hrv/trend?days=${days}${ed}`).then(r => r.json()),
        fetch('/api/training-status').then(r => r.json()),
        fetch(`/api/ml-history?days=${days}${ed}`).then(r => r.json()),
    ]);

    _heroData.daily    = daily;
    _heroData.sleep    = sleep;
    _heroData.hrv      = hrv;
    _heroData.hrvTrend = hrvTrend;
    _heroData.trainingStatus = trainingStatus;
    buildHeroCard();

    buildWeeklyReview();

    const actEl = document.getElementById('activities-container');
    if (!activities.length) {
        actEl.innerHTML = '<p class="empty">Noch keine Aktivitäten — Sync läuft täglich um 6 Uhr.</p>';
    } else {
        actEl.innerHTML = `<div class="table-scroll"><table>
            <thead><tr>
                <th>Sport</th><th>Datum</th><th>Dauer</th>
                <th>Distanz</th><th>Kalorien</th><th>Ø HR</th>
            </tr></thead>
            <tbody>${activities.map(a => `<tr data-id="${a.id}" style="cursor:pointer">
                <td class="sport">${sportLabel(a.sport_type)}</td>
                <td>${fmtDate(a.started_at)}</td>
                <td>${fmtDuration(a.duration_seconds)}</td>
                <td>${fmtDist(a.distance_meters)}</td>
                <td>${a.calories ?? '—'}</td>
                <td>${a.avg_hr ? a.avg_hr + ' bpm' : '—'}</td>
            </tr>`).join('')}</tbody>
        </table></div>`;
    }

    {
        const RUN_TYPES   = new Set(['running','trail_running','hiking','walking']);
        const RIDE_TYPES  = new Set(['cycling','indoor_cycling']);
        const dayMap = {};
        for (const a of activities) {
            const key = String(a.started_at).slice(0, 10);
            if (!dayMap[key]) dayMap[key] = { run_km: 0, ride_km: 0, other_h: 0 };
            const km = (a.distance_meters || 0) / 1000;
            const h  = (a.duration_seconds || 0) / 3600;
            const st = a.sport_type || '';
            if (RUN_TYPES.has(st))       dayMap[key].run_km  += km;
            else if (RIDE_TYPES.has(st)) dayMap[key].ride_km += km;
            else                         dayMap[key].other_h += h;
        }

        function _isoDate(dt) {
            return [dt.getFullYear(), String(dt.getMonth()+1).padStart(2,'0'), String(dt.getDate()).padStart(2,'0')].join('-');
        }
        const endDt = endDate
            ? (([y,m,d]) => new Date(y, m-1, d))(endDate.split('-').map(Number))
            : new Date(new Date().toDateString());
        const startDt = new Date(endDt);
        startDt.setDate(startDt.getDate() - days + 1);

        const actLabels = [], runKm = [], rideKm = [], otherH = [];
        for (let dt = new Date(startDt); dt <= endDt; dt.setDate(dt.getDate() + 1)) {
            const key = _isoDate(dt);
            const v = dayMap[key] || { run_km: 0, ride_km: 0, other_h: 0 };
            actLabels.push(fmtDate(key));
            runKm.push(+(v.run_km.toFixed(1)));
            rideKm.push(+(v.ride_km.toFixed(1)));
            otherH.push(+(v.other_h.toFixed(1)));
        }

        const hasRun   = runKm.some(v => v > 0);
        const hasRide  = rideKm.some(v => v > 0);
        const hasOther = otherH.some(v => v > 0);

        if (hasRun || hasRide || hasOther) {
            hideEmpty('weekly');
            const actDatasets = [];
            if (hasRun)   actDatasets.push({ label: 'Ausdauer',  data: runKm,  backgroundColor: 'rgba(129,140,248,.75)', stack: 'km', borderRadius: 3 });
            if (hasRide)  actDatasets.push({ label: 'Radfahren', data: rideKm, backgroundColor: 'rgba(245,158,11,.75)',  stack: 'km', borderRadius: 3 });
            if (hasOther) actDatasets.push({ label: 'Sonstiges', data: otherH, backgroundColor: 'rgba(16,185,129,.65)',  stack: 'st', borderRadius: 3, yAxisID: 'yh' });
            const actScales = hasOther
                ? { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'km' }, position: 'left' }, yh: { stacked: true, title: { display: true, text: 'h' }, position: 'right', grid: { drawOnChartArea: false } } }
                : { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'km' } } };
            makeChart('weekly-chart', 'bar', actLabels, actDatasets, { scales: actScales });
        } else {
            showEmpty('weekly');
        }
    }

    const labels = daily.map(d => fmtDate(d.date));

    if (daily.some(d => d.steps)) {
        hideEmpty('steps');
        makeChart('steps-chart', 'bar', labels,
            [{ label: 'Schritte', data: daily.map(d => d.steps || 0),
               backgroundColor: C.indigo, borderRadius: 4 }]);
    } else { showEmpty('steps'); }

    const bbDays = daily.filter(d => d.body_battery_high != null);
    if (bbDays.length) {
        hideEmpty('battery');
        makeChart('battery-chart', 'line', bbDays.map(d => fmtDate(d.date)), [
            { label: 'Hoch', data: bbDays.map(d => d.body_battery_high),
              borderColor: C.green, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 },
            { label: 'Niedrig', data: bbDays.map(d => d.body_battery_low),
              borderColor: C.orange, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 },
        ]);
    } else { showEmpty('battery'); }

    if (daily.some(d => d.resting_hr)) {
        hideEmpty('hr');
        makeChart('hr-chart', 'line', labels,
            [{ label: 'Ruhepuls', data: daily.map(d => d.resting_hr),
               borderColor: C.red, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 }]);
    } else { showEmpty('hr'); }

    if (daily.some(d => d.avg_stress)) {
        hideEmpty('stress');
        makeChart('stress-chart', 'line', labels,
            [{ label: 'Stress', data: daily.map(d => d.avg_stress),
               borderColor: C.orange, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 }],
            { scales: { y: { beginAtZero: true, max: 100 } } });
    } else { showEmpty('stress'); }

    if (hrvTrend?.some(h => h.hrv_weekly_avg || h.hrv_last_night)) {
        hideEmpty('hrv-trend');
        const datasets = [];
        if (hrvTrend.some(h => h.hrv_last_night)) {
            datasets.push({ label: 'HRV letzte Nacht', data: hrvTrend.map(h => h.hrv_last_night),
               borderColor: C.indigo, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 });
        }
        if (hrvTrend.some(h => h.hrv_weekly_avg)) {
            datasets.push({ label: 'Wochenø', data: hrvTrend.map(h => h.hrv_weekly_avg),
               borderColor: C.sleepLight, backgroundColor: 'transparent', tension: 0.3,
               borderDash: [4, 4], pointRadius: 0 });
        }
        makeChart('hrv-trend-chart', 'line', hrvTrend.map(h => fmtDate(h.date)), datasets);
    } else { showEmpty('hrv-trend'); }

    const sleepSorted = [...sleep].reverse();
    const sleepLabels = sleepSorted.map(s => fmtDate(s.date));
    const customSleepHist = (mlHistory?.sleep_score_custom || []).filter(s => s.value != null);
    if (customSleepHist.length >= 2) {
        hideEmpty('sleep');
        makeChart('sleep-chart', 'line',
            customSleepHist.map(s => fmtDate(s.date)),
            [{ label: 'Score', data: customSleepHist.map(s => s.value),
               borderColor: C.violet, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 }],
            { scales: { y: { min: 0, max: 100 } } });
    } else if (sleepSorted.some(s => s.sleep_score != null)) {
        hideEmpty('sleep');
        makeChart('sleep-chart', 'line', sleepLabels,
            [{ label: 'Score', data: sleepSorted.map(s => s.sleep_score ?? null),
               borderColor: C.violet, backgroundColor: 'transparent', tension: 0.3, pointRadius: 0 }],
            { scales: { y: { min: 0, max: 100 } } });
    } else { showEmpty('sleep'); }

    if (sleepSorted.some(s => s.deep_sleep_seconds)) {
        hideEmpty('sleep-stages');
        makeChart('sleep-stages-chart', 'bar', sleepLabels, [
            { label: 'Tief',   data: sleepSorted.map(s => secToH(s.deep_sleep_seconds)),
              backgroundColor: C.sleepDeep, stack: 'sleep', borderRadius: 2 },
            { label: 'REM',    data: sleepSorted.map(s => secToH(s.rem_sleep_seconds)),
              backgroundColor: C.sleepRem, stack: 'sleep', borderRadius: 2 },
            { label: 'Leicht', data: sleepSorted.map(s => secToH(s.light_sleep_seconds)),
              backgroundColor: C.sleepLight, stack: 'sleep', borderRadius: 2 },
            { label: 'Wach',   data: sleepSorted.map(s => secToH(s.awake_seconds)),
              backgroundColor: isDark ? '#334155' : '#e2e8f0', stack: 'sleep', borderRadius: 2 },
        ], { scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'Stunden' } } } });
    } else { showEmpty('sleep-stages'); }

    const customIntHist = (mlHistory?.intensity_minutes_custom || []).filter(s => s.value != null);
    if (customIntHist.length >= 2) {
        hideEmpty('intensity');
        makeChart('intensity-chart', 'bar',
            customIntHist.map(s => fmtDate(s.date)), [
            { label: 'Moderat', data: customIntHist.map(s => s.moderate_minutes || 0),
              backgroundColor: C.green, stack: 'intensity', borderRadius: 2 },
            { label: 'Intensiv', data: customIntHist.map(s => s.vigorous_minutes || 0),
              backgroundColor: C.blue, stack: 'intensity', borderRadius: 2 },
        ], { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Minuten' } } } });
    } else if (daily.some(d => d.intensity_moderate || d.intensity_vigorous)) {
        hideEmpty('intensity');
        makeChart('intensity-chart', 'bar', labels, [
            { label: 'Moderat', data: daily.map(d => d.intensity_moderate || 0),
              backgroundColor: C.green, stack: 'intensity', borderRadius: 2 },
            { label: 'Intensiv', data: daily.map(d => d.intensity_vigorous || 0),
              backgroundColor: C.blue, stack: 'intensity', borderRadius: 2 },
        ], { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Minuten' } } } });
    } else { showEmpty('intensity'); }

    if (daily.some(d => d.calories_total)) {
        hideEmpty('calories');
        makeChart('calories-chart', 'bar', labels,
            [{ label: 'Kalorien', data: daily.map(d => d.calories_total || 0),
               backgroundColor: C.amber, borderRadius: 4 }]);
    } else { showEmpty('calories'); }
}

export async function loadReadiness() {
    const r = await fetch('/api/readiness').then(res => res.json());
    _heroData.readiness = r;
    buildHeroCard();
}

export async function loadMlInsights() {
    const d = await fetch('/api/ml-insights').then(r => r.json());
    _heroData.ml = d;
    buildHeroCard();
}

export async function loadEnergyMetrics() {
    const d = await fetch('/api/energy').then(r => r.json());
    _heroData.energy = d;
    buildHeroCard();
}

export async function loadTrainingLoad(days = null) {
    const qs   = days != null ? `?lookback_days=${days}` : '';
    const data = await fetch(`/api/training-load${qs}`).then(r => r.json());
    if (!data.history?.length) { showEmpty('training-load'); return; }
    hideEmpty('training-load');

    const history = data.history;
    const forecast = data.forecast || [];
    const n = history.length;
    const allLabels = [...history.map(h => fmtDate(h.date)), ...forecast.map(f => fmtDate(f.date))];

    const trimpData = [...history.map(h => h.trimp), ...forecast.map(() => null)];

    const bridge = i => [...Array(n - 1).fill(null), history.at(-1)?.[i] ?? null, ...forecast.map(f => f[i])];
    const solid  = i => [...history.map(h => h[i]), ...forecast.map(() => null)];

    const datasets = [
        { type: 'bar',  label: 'Tagesimpuls',   data: trimpData,      backgroundColor: 'rgba(129,140,248,.2)', yAxisID: 'ytrimp', borderRadius: 3 },
        { type: 'line', label: 'Ermüdung',      data: solid('atl'),   borderColor: C.orange, backgroundColor: 'transparent', tension: 0.2, pointRadius: 0 },
        { type: 'line', label: 'Ermüdung →',    data: bridge('atl'),  borderColor: C.orange, backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderDash: [4, 4] },
        { type: 'line', label: 'Fitness',        data: solid('ctl'),   borderColor: C.green, backgroundColor: 'transparent', tension: 0.2, pointRadius: 0 },
        { type: 'line', label: 'Fitness →',      data: bridge('ctl'),  borderColor: C.green, backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderDash: [4, 4] },
        { type: 'line', label: 'Form',           data: solid('tsb'),   borderColor: C.violet, backgroundColor: 'transparent', tension: 0.2, pointRadius: 0 },
        { type: 'line', label: 'Form →',         data: bridge('tsb'),  borderColor: C.violet, backgroundColor: 'transparent', tension: 0.2, pointRadius: 0, borderDash: [4, 4] },
    ];

    makeChart('training-load-chart', 'bar', allLabels, datasets, {
        plugins: {
            legend: {
                display: true,
                labels: { filter: item => !item.text.includes('→') },
            },
        },
        scales: {
            x: {},
            y:      { title: { display: true, text: 'TRIMP' }, position: 'left' },
            ytrimp: { position: 'right', grid: { drawOnChartArea: false }, display: false },
        },
    });

    const t = data.today;
    const atlEl = document.getElementById('tl-atl');
    const ctlEl = document.getElementById('tl-ctl');
    const tsbEl = document.getElementById('tl-tsb');
    if (atlEl && t.atl != null) atlEl.textContent = t.atl;
    if (ctlEl && t.ctl != null) ctlEl.textContent = t.ctl;
    if (tsbEl && t.tsb != null) {
        const sign = t.tsb > 0 ? '+' : '';
        tsbEl.textContent = sign + t.tsb;
        tsbEl.style.color = t.tsb > 5 ? 'var(--green)' : t.tsb < -5 ? 'var(--red)' : 'var(--amber)';
    }
}
