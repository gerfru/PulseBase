import os
import pathlib
import pytest
import asyncpg
import bcrypt
from playwright.async_api import async_playwright, BrowserContext, Page

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8001")
TEST_EMAIL = os.getenv("TEST_EMAIL", "")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "")  # pragma: allowlist secret


@pytest.fixture(scope="session")
async def browser_context():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        yield ctx
        await browser.close()


@pytest.fixture
async def page(browser_context: BrowserContext) -> Page:
    p = await browser_context.new_page()
    yield p
    await p.close()


@pytest.fixture(scope="session")
async def authenticated_page(browser_context: BrowserContext) -> Page:
    """Session-scoped: login once, share page across tests.
    Tests using this fixture must navigate to their target page explicitly.
    For a completely unauthenticated context use an isolated browser (see test_account_export_unauthenticated_redirects_to_login)."""
    p = await browser_context.new_page()
    await p.goto("/login")
    await p.fill("input[name=email]", TEST_EMAIL)
    await p.fill("input[name=password]", TEST_PASSWORD)
    await p.click("button[type=submit]")
    await p.wait_for_url("**/dashboard", timeout=10000)
    yield p
    await p.close()


def _read_env_file() -> dict[str, str]:
    """Read key=value pairs from env/.env (two levels above api/).

    The unit-test conftest sets DB_USER=test via os.environ.setdefault, which
    poisons os.getenv() for fixtures that need real DB credentials. Reading the
    .env file directly mirrors what `make test-user` does via shell substitution.
    """
    env_path = pathlib.Path(__file__).parent.parent.parent.parent / "env" / ".env"
    result: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


@pytest.fixture
async def delete_test_user():
    """Creates a disposable DB user for the account-delete E2E test.

    Bypasses HTTP registration (email-verification requirement) by inserting
    directly into the test DB — same approach as create_ci_user.py.
    Teardown deletes the user if the test did not already do so.

    Credentials are read from env/.env rather than os.getenv() because the
    unit-test conftest poisons the environment with DB_USER=test.
    """
    env = _read_env_file()
    email = "delete-test@e2e.local"
    password = "DeleteMe!2026Test"  # pragma: allowlist secret
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5434")),
        database=os.getenv("DB_NAME", "garmin_test"),
        user=env.get("DB_USER", "garmin"),
        password=env.get("DB_PASSWORD", ""),  # pragma: allowlist secret
    )
    try:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (name, email, password_hash, email_verified_at, is_active)
            VALUES ($1, $2, $3, NOW(), TRUE)
            ON CONFLICT (email) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    email_verified_at = NOW(),
                    is_active = TRUE
            RETURNING id
            """,
            "Delete Test",
            email,
            pw_hash,
        )
        for consent_type in ("health_data", "terms", "age_16plus"):
            await conn.execute(
                """
                INSERT INTO user_consents
                    (user_id, consent_type, accepted, ip_address_hash, privacy_policy_version)
                VALUES ($1, $2, TRUE, NULL, '1.0')
                ON CONFLICT (user_id, consent_type) DO NOTHING
                """,
                user_id,
                consent_type,
            )
        yield {"email": email, "password": password, "id": user_id}
    finally:
        await conn.execute("DELETE FROM users WHERE email = $1", email)
        await conn.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture a screenshot when an E2E test fails."""
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        page: Page | None = item.funcargs.get(
            "authenticated_page"
        ) or item.funcargs.get("page")
        if page is not None:
            out_dir = pathlib.Path("test-results")
            out_dir.mkdir(exist_ok=True)
            safe_name = item.nodeid.replace("/", "_").replace("::", "__")
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(page.screenshot(path=out_dir / f"{safe_name}.png"))
                else:
                    loop.run_until_complete(
                        page.screenshot(path=out_dir / f"{safe_name}.png")
                    )
            except Exception:
                pass
