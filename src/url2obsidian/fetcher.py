from typing import Protocol

import httpx

from url2obsidian.models import FetchResult

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15 url2obsidian/0.1"
)


class BrowserFetch(Protocol):
    def fetch(self, url: str) -> FetchResult: ...


class TwoTierFetcher:
    def __init__(
        self,
        browser: BrowserFetch,
        min_html_bytes: int = 2048,
        timeout_s: float = 15.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._browser = browser
        self._min = min_html_bytes
        self._http = http_client or httpx.Client(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        )

    def fetch(self, url: str) -> FetchResult:
        try:
            resp = self._http.get(url)
        except httpx.HTTPError:
            return self._browser.fetch(url)

        if 400 <= resp.status_code < 500:
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        looks_like_html = "html" in content_type or "<html" in resp.text[:200].lower()
        if not looks_like_html or len(resp.text) < self._min:
            return self._browser.fetch(url)

        return FetchResult(url=url, html=resp.text, method="httpx", status=resp.status_code)


class PlaywrightBrowser:
    """Real browser fallback. Lazy-imports playwright so unit tests don't need it."""

    def __init__(self, timeout_s: float = 30.0) -> None:
        self._timeout = timeout_s

    def fetch(self, url: str) -> FetchResult:
        from playwright.sync_api import sync_playwright  # lazy

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                ctx = browser.new_context(user_agent=_UA)
                page = ctx.new_page()
                resp = page.goto(url, wait_until="networkidle", timeout=int(self._timeout * 1000))
                html = page.content()
                status = resp.status if resp else 0
            finally:
                browser.close()
        return FetchResult(url=url, html=html, method="playwright", status=status)
