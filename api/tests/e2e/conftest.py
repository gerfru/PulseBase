import hashlib
import os
import pathlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta

import asyncpg
import bcrypt
import pytest
from playwright.async_api import async_playwright, BrowserContext, Page

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8001")
TEST_EMAIL = os.getenv("TEST_EMAIL", "")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "")  # pragma: allowlist secret

_run_id = uuid.uuid4().hex[:8]


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


@pytest.fixture
async def isolated_page() -> Page:
    """Function-scoped page in a fresh browser context — for tests that mutate shared
    state (theme class on <html>, URL query params) that would affect other tests
    sharing the session-scoped authenticated_page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        page = await ctx.new_page()
        await page.goto("/login")
        await page.fill("input[name=email]", TEST_EMAIL)
        await page.fill("input[name=password]", TEST_PASSWORD)
        await page.click("button[type=submit]")
        await page.wait_for_url("**/dashboard", timeout=10000)
        yield page
        await browser.close()


def _read_env_api_file() -> dict[str, str]:
    """Read key=value pairs from env/.env.api (for SESSION_SECRET etc.)."""
    env_path = pathlib.Path(__file__).parent.parent.parent.parent / "env" / ".env.api"
    result: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


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
    email = f"delete-test-{_run_id}@e2e.local"
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


async def _make_db_conn() -> asyncpg.Connection:
    env = _read_env_file()
    return await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5434")),
        database=os.getenv("DB_NAME", "garmin_test"),
        user=env.get("DB_USER", "garmin"),
        password=env.get("DB_PASSWORD", ""),  # pragma: allowlist secret
    )


async def _insert_consents(conn: asyncpg.Connection, user_id: int) -> None:
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


@pytest.fixture(scope="session")
def session_secret() -> str:
    """SESSION_SECRET from env/.env.api — used to generate verify/reset tokens in tests."""
    return _read_env_api_file().get("SESSION_SECRET", "")


@pytest.fixture
async def clean_register_email():
    """Ensures register-new@example.com is absent before the test and deleted after."""
    email = "register-new@example.com"
    conn = await _make_db_conn()
    try:
        await conn.execute("DELETE FROM users WHERE email = $1", email)
        yield email
    finally:
        await conn.execute("DELETE FROM users WHERE email = $1", email)
        await conn.close()


@pytest.fixture
async def registered_test_user():
    """Pre-existing verified user — used to trigger duplicate-email error on register."""
    email = "registered@example.com"
    password = "RegisteredTest!2026"  # pragma: allowlist secret
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = await _make_db_conn()
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
            "Registered Test",
            email,
            pw_hash,
        )
        await _insert_consents(conn, user_id)
        yield {"email": email, "password": password, "id": user_id}
    finally:
        await conn.execute("DELETE FROM users WHERE email = $1", email)
        await conn.close()


@pytest.fixture
async def unverified_test_user():
    """Unverified user (email_verified_at = NULL) — used to test the verify-token flow."""
    email = "unverified@e2e.local"
    password = "UnverifiedTest!2026"  # pragma: allowlist secret
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = await _make_db_conn()
    try:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (name, email, password_hash, is_active)
            VALUES ($1, $2, $3, TRUE)
            ON CONFLICT (email) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    email_verified_at = NULL,
                    is_active = TRUE
            RETURNING id
            """,
            "Unverified Test",
            email,
            pw_hash,
        )
        await _insert_consents(conn, user_id)
        yield {"id": user_id, "email": email, "password": password}
    finally:
        await conn.execute("DELETE FROM users WHERE email = $1", email)
        await conn.close()


@pytest.fixture
async def reset_test_user():
    """Verified user with a pre-injected reset token — used to test the password-reset flow."""
    email = f"reset-test-{_run_id}@e2e.local"
    password = "ResetTest!2026Pass"  # pragma: allowlist secret
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = await _make_db_conn()
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
            "Reset Test",
            email,
            pw_hash,
        )
        await _insert_consents(conn, user_id)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
        await conn.execute(
            "UPDATE users SET password_reset_token_hash=$1, password_reset_expires_at=$2 WHERE id=$3",
            token_hash,
            expires_at,
            user_id,
        )
        yield {
            "id": user_id,
            "email": email,
            "password": password,
            "raw_token": raw_token,
        }
    finally:
        await conn.execute("DELETE FROM users WHERE email = $1", email)
        await conn.close()


@pytest.fixture
async def epilepsy_test_user():
    """Verified user with epilepsy_mode=TRUE — used to test the epilepsy page."""
    email = "epilepsy@e2e.local"
    password = "EpilepsyTest!2026"  # pragma: allowlist secret
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = await _make_db_conn()
    try:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (name, email, password_hash, email_verified_at, is_active, epilepsy_mode)
            VALUES ($1, $2, $3, NOW(), TRUE, TRUE)
            ON CONFLICT (email) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    email_verified_at = NOW(),
                    is_active = TRUE,
                    epilepsy_mode = TRUE
            RETURNING id
            """,
            "Epilepsy Test",
            email,
            pw_hash,
        )
        await _insert_consents(conn, user_id)
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
