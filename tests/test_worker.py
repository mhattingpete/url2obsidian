from pathlib import Path

import httpx

from tests.fakes import (
    FakeExtractor,
    FakeFetcher,
    FakeRaindrop,
    FakeVault,
    make_article,
    make_item,
)
from url2obsidian.extractor import ExtractorError
from url2obsidian.models import FetchResult
from url2obsidian.worker import run_once


def _fetch_ok(url: str, html: str = "<html>body</html>") -> FetchResult:
    return FetchResult(url=url, html=html, method="httpx", status=200)


def test_happy_path_marks_clipped(tmp_path: Path):
    item = make_item(rid=1, url="https://example.com/a")
    api = FakeRaindrop([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    long_md = "# hello\n\n" + ("Lorem ipsum dolor sit amet. " * 20)
    extractor = FakeExtractor({item.url: make_article(long_md)})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)

    assert len(api.clipped) == 1
    assert api.clipped[0][0] == 1
    assert api.clipped[0][1].startswith("clipped-")
    assert api.failed == []
    assert vault.written
    written = vault.written[0].read_text()
    assert "# hello" in written
    assert "raindrop_id: 1" in written


def test_fetch_error_marks_failed(tmp_path: Path):
    item = make_item(rid=2, url="https://example.com/b")
    api = FakeRaindrop([item])
    fetcher = FakeFetcher({item.url: httpx.ConnectError("boom")})
    extractor = FakeExtractor({})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)

    assert api.clipped == []
    assert api.failed == [(2, "fetch")]


def test_http_4xx_marks_failed_with_code(tmp_path: Path):
    item = make_item(rid=3, url="https://example.com/c")
    api = FakeRaindrop([item])
    err = httpx.HTTPStatusError(
        "404", request=httpx.Request("GET", item.url), response=httpx.Response(404)
    )
    fetcher = FakeFetcher({item.url: err})
    extractor = FakeExtractor({})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)
    assert api.failed == [(3, "http-404")]


def test_extractor_error_marks_failed(tmp_path: Path):
    item = make_item(rid=4, url="https://example.com/d")
    api = FakeRaindrop([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    extractor = FakeExtractor({item.url: ExtractorError("bad html")})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)
    assert api.failed == [(4, "extractor")]


def test_empty_content_marks_failed(tmp_path: Path):
    item = make_item(rid=5, url="https://example.com/e")
    api = FakeRaindrop([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    extractor = FakeExtractor({item.url: make_article(content="")})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)
    assert api.failed == [(5, "empty")]


def test_one_item_failing_does_not_block_next(tmp_path: Path):
    item_a = make_item(rid=10, url="https://example.com/fail")
    item_b = make_item(rid=11, url="https://example.com/ok")
    api = FakeRaindrop([item_a, item_b])
    long_md = "# ok\n\n" + ("Lorem ipsum dolor sit amet. " * 20)
    fetcher = FakeFetcher(
        {
            item_a.url: httpx.ConnectError("boom"),
            item_b.url: _fetch_ok(item_b.url),
        }
    )
    extractor = FakeExtractor({item_b.url: make_article(long_md)})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)
    assert api.failed == [(10, "fetch")]
    assert [c[0] for c in api.clipped] == [11]
