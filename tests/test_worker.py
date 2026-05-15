import errno
from pathlib import Path

import httpx

from tests.fakes import (
    FakeExtractor,
    FakeFetcher,
    FakeInbox,
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
    item = make_item("https://example.com/a")
    inbox = FakeInbox([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    long_md = "# hello\n\n" + ("Lorem ipsum dolor sit amet. " * 20)
    extractor = FakeExtractor({item.url: make_article(long_md)})
    vault = FakeVault(tmp_path)

    run_once(inbox, fetcher, extractor, vault)

    assert len(inbox.clipped) == 1
    clipped_item, clipped_path = inbox.clipped[0]
    assert clipped_item.url == item.url
    assert clipped_path == vault.written[0]
    assert inbox.failed == []
    written = clipped_path.read_text()
    assert "# hello" in written
    assert 'source: "https://example.com/a"' in written


def test_fetch_error_marks_failed(tmp_path: Path):
    item = make_item("https://example.com/b")
    inbox = FakeInbox([item])
    fetcher = FakeFetcher({item.url: httpx.ConnectError("boom")})
    extractor = FakeExtractor({})
    vault = FakeVault(tmp_path)

    run_once(inbox, fetcher, extractor, vault)

    assert inbox.clipped == []
    assert [(i.url, r) for i, r in inbox.failed] == [(item.url, "fetch")]


def test_http_4xx_marks_failed_with_code(tmp_path: Path):
    item = make_item("https://example.com/c")
    inbox = FakeInbox([item])
    err = httpx.HTTPStatusError(
        "404", request=httpx.Request("GET", item.url), response=httpx.Response(404)
    )
    fetcher = FakeFetcher({item.url: err})
    extractor = FakeExtractor({})
    vault = FakeVault(tmp_path)

    run_once(inbox, fetcher, extractor, vault)
    assert [(i.url, r) for i, r in inbox.failed] == [(item.url, "http-404")]


def test_extractor_error_marks_failed(tmp_path: Path):
    item = make_item("https://example.com/d")
    inbox = FakeInbox([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    extractor = FakeExtractor({item.url: ExtractorError("bad html")})
    vault = FakeVault(tmp_path)

    run_once(inbox, fetcher, extractor, vault)
    assert [(i.url, r) for i, r in inbox.failed] == [(item.url, "extractor")]


def test_empty_content_marks_failed(tmp_path: Path):
    item = make_item("https://example.com/e")
    inbox = FakeInbox([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    extractor = FakeExtractor({item.url: make_article(content="")})
    vault = FakeVault(tmp_path)

    run_once(inbox, fetcher, extractor, vault)
    assert [(i.url, r) for i, r in inbox.failed] == [(item.url, "empty")]


def test_run_once_swallows_oserror_from_list_pending(tmp_path: Path):
    """If the inbox read fails (e.g. iCloud EDEADLK), run_once returns cleanly."""

    class BrokenInbox:
        def list_pending(self):
            raise OSError(errno.EDEADLK, "bird lock")

        def mark_clipped(self, *_):  # pragma: no cover - never called
            raise AssertionError

        def mark_failed(self, *_):  # pragma: no cover - never called
            raise AssertionError

    fetcher = FakeFetcher({})
    extractor = FakeExtractor({})
    vault = FakeVault(tmp_path)

    run_once(BrokenInbox(), fetcher, extractor, vault)  # must not raise
    assert vault.written == []


def test_one_item_failing_does_not_block_next(tmp_path: Path):
    item_a = make_item("https://example.com/fail")
    item_b = make_item("https://example.com/ok")
    inbox = FakeInbox([item_a, item_b])
    long_md = "# ok\n\n" + ("Lorem ipsum dolor sit amet. " * 20)
    fetcher = FakeFetcher(
        {
            item_a.url: httpx.ConnectError("boom"),
            item_b.url: _fetch_ok(item_b.url),
        }
    )
    extractor = FakeExtractor({item_b.url: make_article(long_md)})
    vault = FakeVault(tmp_path)

    run_once(inbox, fetcher, extractor, vault)
    assert [(i.url, r) for i, r in inbox.failed] == [(item_a.url, "fetch")]
    assert [i.url for i, _ in inbox.clipped] == [item_b.url]
