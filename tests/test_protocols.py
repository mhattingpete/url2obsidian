from collections.abc import Iterable
from pathlib import Path

from url2obsidian.models import Article, FetchResult, Item, ItemMeta
from url2obsidian.protocols import Extractor, Fetcher, Inbox, VaultWriter


class _InboxImpl:
    def list_pending(self) -> Iterable[Item]:
        return []

    def mark_clipped(self, item: Item, clipped_path: Path) -> None:
        pass

    def mark_failed(self, item: Item, reason: str) -> None:
        pass


class _FetcherImpl:
    def fetch(self, url: str) -> FetchResult:
        return FetchResult(url=url, html="", method="httpx", status=200)


class _ExtractorImpl:
    def extract(self, html: str, url: str) -> Article:
        return Article(title="", byline="", content_markdown="", published=None, site_name="")


class _VaultImpl:
    def write(self, article: Article, meta: ItemMeta) -> Path:
        return Path("/tmp/x.md")


def test_implementations_satisfy_protocols():
    assert isinstance(_InboxImpl(), Inbox)
    assert isinstance(_FetcherImpl(), Fetcher)
    assert isinstance(_ExtractorImpl(), Extractor)
    assert isinstance(_VaultImpl(), VaultWriter)
