"""E2E-Accessibility-Tests — axe-core via axe-playwright-python.

Injiziert axe-core in jede kritische Seite und blockiert bei Violations der
Stufen ``critical``/``serious`` (die WCAG-A/AA-relevanten Schweregrade), und
zwar in BEIDEN Farb-Schemata (``light`` + ``dark``) — die App ist dark-primär,
unterstützt aber per ``prefers-color-scheme`` auch hell, also muss beides AA
erfüllen.

Auth erfolgt über einen injizierten, vorsignierten Session-Cookie
(``make_session_cookie``) statt über das rate-limitierte ``/login``-Formular —
das rate-limit-sichere Muster (die Suite teilt ein 10/min-Login-Budget; UI-Logins
hier ließen sonst andere Tests flaken). Siehe test_ml_feedback_e2e.py.

axe deckt die maschinell prüfbaren Kriterien ab (Textalternativen, ARIA,
Landmarks, Farbkontrast, Link-Unterscheidbarkeit). NICHT automatisiert prüfbar
und weiterhin manuell: der echte Screenreader-Durchlauf (VoiceOver/NVDA). Der
Fokus-INDIKATOR-Kontrast (WCAG 1.4.11), den axe nicht zuverlässig misst, wird
separat in ``test_focus_ring_contrast_login_field`` gemessen.
"""

import re

import pytest
from axe_playwright_python.async_playwright import Axe
from playwright.async_api import async_playwright

from tests.e2e.conftest import BASE_URL, make_session_cookie

BLOCKING_IMPACTS = {"critical", "serious"}
SCHEMES = ["light", "dark"]

_axe = Axe()


async def _auth_ctx(pw, user_id: int, secret: str):
    browser = await pw.chromium.launch()
    ctx = await browser.new_context(base_url=BASE_URL)
    await ctx.add_cookies(
        [
            {
                "name": "session",
                "value": make_session_cookie(user_id, secret),
                "url": BASE_URL,
            }
        ]
    )
    return browser, ctx


async def _scan(page, path: str, scheme: str) -> None:
    """axe gegen path im gegebenen Schema; Fail bei critical/serious."""
    await page.emulate_media(color_scheme=scheme)
    await page.goto(path)
    await page.wait_for_load_state("networkidle")
    results = await _axe.run(page)
    blocking = [
        v
        for v in results.response.get("violations", [])
        if v.get("impact") in BLOCKING_IMPACTS
    ]
    if blocking:
        lines = [
            f"  [{v['impact']}] {v['id']}: {v['help']} "
            f"({len(v['nodes'])} Element(e)) — {v['helpUrl']}"
            for v in blocking
        ]
        pytest.fail(
            f"{len(blocking)} blockierende A11y-Violation(s) auf {page.url} ({scheme}):\n"
            + "\n".join(lines)
        )


# ── axe-Scans: öffentliche Seiten (kein Auth) ─────────────────────────────────

PUBLIC_PAGES = [
    "/login",
    "/register",
    "/accessibility",
    "/privacy",
    "/terms",
    "/imprint",
]


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("path", PUBLIC_PAGES)
async def test_a11y_public_pages(page, path, scheme):
    await _scan(page, path, scheme)


# ── axe-Scans: geschützte Seiten (Cookie-Injektion, kein Form-Login) ──────────

AUTHED_PAGES = ["/dashboard", "/settings", "/metrics", "/help"]


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("path", AUTHED_PAGES)
async def test_a11y_authenticated_pages(
    registered_test_user, session_secret, path, scheme
):
    async with async_playwright() as pw:
        browser, ctx = await _auth_ctx(pw, registered_test_user["id"], session_secret)
        try:
            await _scan(await ctx.new_page(), path, scheme)
        finally:
            await browser.close()


@pytest.mark.parametrize("scheme", SCHEMES)
async def test_a11y_epilepsy_page(epilepsy_test_user, session_secret, scheme):
    async with async_playwright() as pw:
        browser, ctx = await _auth_ctx(pw, epilepsy_test_user["id"], session_secret)
        try:
            await _scan(await ctx.new_page(), "/epilepsy", scheme)
        finally:
            await browser.close()


# ── Fokus-Indikator-Kontrast (WCAG 1.4.11) ────────────────────────────────────
# axe' color-contrast-Regel prüft Text/Hintergrund, NICHT den Fokus-Indikator.
# Daher gezielte Messung am Auth-Formularfeld (emerald-400-Ring, PR4-Fix [A-6]):
# Element fokussieren, Ring-Farbe gegen den dahinterliegenden Hintergrund auf
# >= 3:1 prüfen.

_FOCUS_PROBE_JS = """
(selector) => {
    const el = document.querySelector(selector);
    if (!el) return null;
    el.focus();
    const cs = getComputedStyle(el);
    let bg = cs.backgroundColor;
    let node = el;
    while ((bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') && node.parentElement) {
        node = node.parentElement;
        bg = getComputedStyle(node).backgroundColor;
    }
    return {
        boxShadow: cs.boxShadow,
        outlineColor: cs.outlineColor,
        outlineWidth: cs.outlineWidth,
        bg,
    };
}
"""


def _parse_rgb(value: str) -> tuple[float, float, float] | None:
    m = re.search(r"rgba?\(([^)]+)\)", value or "")
    if not m:
        return None
    parts = [float(x.strip()) for x in m.group(1).split(",")[:3]]
    return (parts[0], parts[1], parts[2]) if len(parts) == 3 else None


def _rel_luminance(rgb: tuple[float, float, float]) -> float:
    def chan(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast(c1: tuple[float, float, float], c2: tuple[float, float, float]) -> float:
    l1, l2 = _rel_luminance(c1), _rel_luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _all_rgbs(value: str) -> list[tuple[float, float, float]]:
    out = []
    for m in re.findall(r"rgba?\([^)]+\)", value or ""):
        rgb = _parse_rgb(m)
        if rgb:
            out.append(rgb)
    return out


def _focus_indicator_candidates(info: dict) -> list[tuple[float, float, float]]:
    """Mögliche Indikator-Farben. Tailwinds ``ring`` erzeugt mehrere Box-Shadows
    (weißer ring-offset + farbiger Ring) — daher ALLE sammeln und den Aufrufer
    den kontraststärksten gegen den Hintergrund wählen lassen."""
    candidates: list[tuple[float, float, float]] = []
    if info.get("boxShadow") and info["boxShadow"] != "none":
        candidates += _all_rgbs(info["boxShadow"])
    if info.get("outlineWidth") not in (None, "0px", "0"):
        oc = _parse_rgb(info.get("outlineColor", ""))
        if oc:
            candidates.append(oc)
    return candidates


@pytest.mark.parametrize("scheme", SCHEMES)
async def test_focus_ring_contrast_login_field(page, scheme):
    await page.emulate_media(color_scheme=scheme)
    await page.goto("/login")
    await page.wait_for_load_state("networkidle")
    info = await page.evaluate(_FOCUS_PROBE_JS, "input[name=email]")
    assert info, "Login-Email-Feld nicht gefunden"
    bg = _parse_rgb(info["bg"])
    candidates = _focus_indicator_candidates(info)
    assert candidates, f"Kein sichtbarer Fokus-Indikator ({scheme}): {info}"
    assert bg is not None, f"Hintergrundfarbe nicht parsebar ({scheme}): {info}"
    # Der sichtbare Fokus-Indikator ist die kontraststärkste Shadow-/Outline-Farbe
    # gegen den Hintergrund (ignoriert den weißen ring-offset).
    ratio = max(_contrast(c, bg) for c in candidates)
    assert ratio >= 3.0, (
        f"Fokus-Indikator-Kontrast {ratio:.2f}:1 < 3:1 ({scheme}) "
        f"(Kandidaten {candidates} vs Hintergrund {bg})"
    )
