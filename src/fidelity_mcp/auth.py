"""Fidelity session management.

Auth strategy (in priority order):
1. FIDELITY_SESSION_COOKIES env var — JSON dict of cookies, useful for CI or
   when the user manually copies cookies from browser DevTools.
2. Cached session file at ~/.fidelity_mcp/session.json — written after a
   successful Playwright login and reused until cookies expire.
3. Interactive Playwright login — opens a headed Chromium window so the user
   can log in (and complete 2FA) manually; FIDELITY_TOTP_SECRET bypasses
   interactive 2FA for TOTP-based accounts.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

SESSION_CACHE_PATH = Path.home() / ".fidelity_mcp" / "session.json"
PORTFOLIO_URL = "https://digital.fidelity.com/ftgw/digital/portfolio/positions"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://digital.fidelity.com/",
}


class FidelitySession:
    """Holds the authenticated Fidelity session cookies."""

    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Loading strategies
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Try all loading strategies in priority order. Returns True if loaded."""
        return self._load_from_env() or self._load_from_cache()

    def _load_from_env(self) -> bool:
        raw = os.environ.get("FIDELITY_SESSION_COOKIES", "")
        if not raw:
            return False
        try:
            self.cookies = json.loads(raw)
            logger.info("Loaded session from FIDELITY_SESSION_COOKIES env var")
            return True
        except json.JSONDecodeError:
            logger.warning("FIDELITY_SESSION_COOKIES is not valid JSON — ignoring")
            return False

    def _load_from_cache(self) -> bool:
        if not SESSION_CACHE_PATH.exists():
            return False
        try:
            data = json.loads(SESSION_CACHE_PATH.read_text())
            self.cookies = data.get("cookies", {})
            if self.cookies:
                logger.info("Loaded cached session from %s", SESSION_CACHE_PATH)
                return True
        except (json.JSONDecodeError, KeyError):
            pass
        return False

    def save(self) -> None:
        SESSION_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SESSION_CACHE_PATH.write_text(json.dumps({"cookies": self.cookies}, indent=2))
        SESSION_CACHE_PATH.chmod(0o600)

    def clear(self) -> None:
        self.cookies = {}
        if SESSION_CACHE_PATH.exists():
            SESSION_CACHE_PATH.unlink()

    # ------------------------------------------------------------------
    # Playwright login (call from CLI, not from the MCP server itself)
    # ------------------------------------------------------------------

    async def login_interactive(
        self,
        username: str,
        password: str,
        totp_secret: str | None = None,
    ) -> None:
        """Open a headed browser, log in to Fidelity, and save the session.

        If *totp_secret* is provided it is used to generate the TOTP code
        automatically; otherwise the user must complete 2FA in the browser.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for interactive login.\n"
                "Install it with:  pip install playwright && playwright install chromium"
            ) from exc

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False, slow_mo=100)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(
                "https://digital.fidelity.com/ftgw/digital/login/full-page",
                wait_until="networkidle",
            )

            # Username step
            user_sel = '[data-testid="userId-input"], input[name="userId-input"], #userId-input'
            await page.locator(user_sel).first.fill(username)
            await page.locator('[data-testid="btn-login"], #fs-login-button').first.click()
            await page.wait_for_timeout(1500)

            # Password step
            pwd_sel = '[data-testid="password"], input[name="password"], #password'
            await page.locator(pwd_sel).first.fill(password)
            await page.locator('[data-testid="btn-login"], #fs-login-button').first.click()
            await page.wait_for_timeout(2000)

            # TOTP 2FA (optional)
            if totp_secret:
                import pyotp

                code = pyotp.TOTP(totp_secret).now()
                try:
                    otp_input = page.locator(
                        'input[name="otpCode"], input[id="otpCode"], [data-testid="otpCode"]'
                    ).first
                    await otp_input.fill(code, timeout=6000)
                    await page.locator('[data-testid="btn-submit"], [type="submit"]').first.click()
                    await page.wait_for_timeout(2000)
                except Exception:
                    logger.warning("TOTP field not found — may not have been required")
            else:
                # Wait for the user to finish 2FA manually (up to 2 minutes)
                print("Complete 2FA in the browser window, then press Enter here...")
                input()

            # Wait for dashboard
            await page.wait_for_url("**/portfolio**", timeout=30_000)

            playwright_cookies = await context.cookies()
            self.cookies = {c["name"]: c["value"] for c in playwright_cookies}
            await browser.close()

        self.save()
        print(f"Session saved to {SESSION_CACHE_PATH}")

    # ------------------------------------------------------------------
    # HTTP client factory
    # ------------------------------------------------------------------

    def http_client(self) -> httpx.Client:
        """Return a configured httpx client using the current session cookies."""
        if not self.cookies:
            raise RuntimeError("No session cookies — run `fidelity-mcp login` first")
        return httpx.Client(
            cookies=self.cookies,
            headers=_BROWSER_HEADERS,
            follow_redirects=True,
            timeout=30.0,
        )

    def is_authenticated(self) -> bool:
        """Quick check — does the portfolio page return 200 (not a login redirect)?"""
        if not self.cookies:
            return False
        try:
            with self.http_client() as client:
                r = client.get(PORTFOLIO_URL)
                return r.status_code == 200 and "login" not in str(r.url)
        except Exception:
            return False
