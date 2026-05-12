import httpx
import pytest
import respx

from url2obsidian.fetcher import TwoTierFetcher
from url2obsidian.models import FetchResult


class FakeBrowser:
    def __init__(self, html: str = "<html><body>browser</body></html>") -> None:
        self.calls: list[str] = []
        self._html = html

    def fetch(self, url: str) -> FetchResult:
        self.calls.append(url)
        return FetchResult(url=url, html=self._html, method="playwright", status=200)


@respx.mock
def test_httpx_path_when_response_is_large_html():
    big_html = "<html><body>" + ("x" * 3000) + "</body></html>"
    respx.get("https://example.com/a").mock(return_value=httpx.Response(200, html=big_html))
    browser = FakeBrowser()
    f = TwoTierFetcher(browser=browser, min_html_bytes=2048)
    r = f.fetch("https://example.com/a")
    assert r.method == "httpx"
    assert "xxx" in r.html
    assert browser.calls == []


@respx.mock
def test_fallback_when_response_is_too_small():
    respx.get("https://example.com/spa").mock(
        return_value=httpx.Response(200, html="<html><body>skel</body></html>")
    )
    browser = FakeBrowser(html="<html><body>fully rendered</body></html>")
    f = TwoTierFetcher(browser=browser, min_html_bytes=2048)
    r = f.fetch("https://example.com/spa")
    assert r.method == "playwright"
    assert "fully rendered" in r.html
    assert browser.calls == ["https://example.com/spa"]


@respx.mock
def test_fallback_on_network_error():
    respx.get("https://example.com/down").mock(side_effect=httpx.ConnectError("boom"))
    browser = FakeBrowser()
    f = TwoTierFetcher(browser=browser, min_html_bytes=2048)
    r = f.fetch("https://example.com/down")
    assert r.method == "playwright"


@respx.mock
def test_http_4xx_propagates_without_fallback():
    respx.get("https://example.com/dead").mock(return_value=httpx.Response(404))
    browser = FakeBrowser()
    f = TwoTierFetcher(browser=browser, min_html_bytes=2048)
    with pytest.raises(httpx.HTTPStatusError):
        f.fetch("https://example.com/dead")
    assert browser.calls == []
