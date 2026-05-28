import { currentDays } from './dashboard-nav.js';

export async function buildWeeklyReview() {
    try {
        const card = document.getElementById('weekly-card');
        if (!card) return;

        const existingReview = card.querySelector('[data-weekly-review]');
        if (existingReview) existingReview.remove();

        const numWeeks = Math.ceil((currentDays / 7) * 2) + 1;
        const weekly = await fetch(`/api/weekly?weeks=${numWeeks}`).then((r) => r.json());
        if (!weekly || weekly.length === 0) return;

        function weekLabel(weekDateStr) {
            const mon = new Date(`${weekDateStr}T00:00:00`);
            const sun = new Date(mon);
            sun.setDate(mon.getDate() + 6);
            const fmt = (d) => `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`;
            const t = new Date(mon);
            t.setDate(t.getDate() + 4 - (t.getDay() || 7));
            const kw = Math.ceil(((t - new Date(t.getFullYear(), 0, 1)) / 86400000 + 1) / 7);
            return `KW ${kw} · ${fmt(mon)} – ${fmt(sun)}`;
        }

        function trendCls(delta) {
            return delta > 0 ? 'wk-up' : delta < 0 ? 'wk-down' : 'wk-flat';
        }
        function trendArrow(delta) {
            return delta > 0 ? '↑' : delta < 0 ? '↓' : '→';
        }

        function kpi(label, value, sub, trendDelta = null) {
            const cls = trendDelta != null ? trendCls(trendDelta) : '';
            const arrow = trendDelta != null ? ` <span class="${cls}">${trendArrow(trendDelta)}</span>` : '';
            return `<div class="wk-kpi">
                <span class="wk-kpi-lbl">${label}</span>
                <span class="wk-kpi-val">${value}${arrow}</span>
                ${sub ? `<span class="wk-kpi-sub">${sub}</span>` : ''}
            </div>`;
        }

        let reviewHtml = '';

        if (currentDays === 7) {
            const [thisWeek, lastWeek] = weekly.slice(-2).reverse();
            if (!thisWeek) return;
            const actDelta = lastWeek ? thisWeek.activity_count - lastWeek.activity_count : null;
            const kmDelta = lastWeek ? thisWeek.total_km - lastWeek.total_km : null;
            const kmPct = lastWeek && lastWeek.total_km > 0 ? ((kmDelta / lastWeek.total_km) * 100).toFixed(0) : null;
            const actSub = lastWeek ? `vs. ${lastWeek.activity_count} Vorwoche` : '';
            const kmSub = kmPct != null ? `${kmPct > 0 ? '+' : ''}${kmPct}%` : '';

            reviewHtml = `<div data-weekly-review class="wk-review">
                <div class="wk-header">${weekLabel(thisWeek.week)}</div>
                <div class="wk-kpis">
                    ${kpi('Aktivitäten', thisWeek.activity_count, actSub, actDelta)}
                    ${kpi('Distanz', `${Math.round(thisWeek.total_km)} km`, kmSub, kmDelta)}
                    ${kpi('Laufen', `${thisWeek.run_km} km`, '', null)}
                    ${kpi('Radfahren', `${thisWeek.ride_km} km`, '', null)}
                </div>
            </div>`;
        } else if (currentDays === 14) {
            const [w2, w1] = weekly.slice(-2).reverse();
            if (!w1 || !w2) return;
            const actDelta = w2.activity_count - w1.activity_count;
            const kmDelta = w2.total_km - w1.total_km;
            const kmPct = w1.total_km > 0 ? ((kmDelta / w1.total_km) * 100).toFixed(0) : 0;

            function kwOnly(weekDateStr) {
                const mon = new Date(`${weekDateStr}T00:00:00`);
                const t = new Date(mon);
                t.setDate(t.getDate() + 4 - (t.getDay() || 7));
                const kw = Math.ceil(((t - new Date(t.getFullYear(), 0, 1)) / 86400000 + 1) / 7);
                return `KW ${kw}`;
            }

            reviewHtml = `<div data-weekly-review class="wk-review">
                <div class="wk-header">14 Tage im Überblick</div>
                <div class="wk-kpis">
                    ${kpi(kwOnly(w1.week), `${w1.activity_count} Akt.`, `${Math.round(w1.total_km)} km`, null)}
                    ${kpi(kwOnly(w2.week), `${w2.activity_count} Akt.`, `${Math.round(w2.total_km)} km`, null)}
                    ${kpi('Δ Aktivitäten', `${actDelta > 0 ? '+' : ''}${actDelta}`, '', actDelta)}
                    ${kpi('Δ Distanz', `${kmPct > 0 ? '+' : ''}${kmPct}%`, '', kmDelta)}
                </div>
            </div>`;
        } else if (currentDays === 30) {
            const actSum = weekly.reduce((s, w) => s + (w.activity_count || 0), 0);
            const kmSum = weekly.reduce((s, w) => s + (w.total_km || 0), 0);
            const wks = weekly.length || 1;

            reviewHtml = `<div data-weekly-review class="wk-review">
                <div class="wk-header">Monat im Überblick</div>
                <div class="wk-kpis">
                    ${kpi('Aktivitäten', actSum, `Ø ${(actSum / wks).toFixed(1)}/Woche`)}
                    ${kpi('Distanz', `${Math.round(kmSum)} km`, `Ø ${Math.round(kmSum / wks)} km/Woche`)}
                </div>
            </div>`;
        } else {
            const actSum = weekly.reduce((s, w) => s + (w.activity_count || 0), 0);
            const kmSum = weekly.reduce((s, w) => s + (w.total_km || 0), 0);
            const wks = weekly.length || 1;

            reviewHtml = `<div data-weekly-review class="wk-review">
                <div class="wk-header">${wks} Wochen im Überblick</div>
                <div class="wk-kpis">
                    ${kpi('Aktivitäten', actSum, `Ø ${(actSum / wks).toFixed(1)}/Woche`)}
                    ${kpi('Distanz', `${Math.round(kmSum)} km`, `Ø ${Math.round(kmSum / wks)} km/Woche`)}
                </div>
            </div>`;
        }

        if (reviewHtml) {
            const chartWrap = card.querySelector('.chart-wrap');
            if (chartWrap) chartWrap.insertAdjacentHTML('beforebegin', reviewHtml);
        }
    } catch (e) {
        console.warn('buildWeeklyReview error:', e);
    }
}
