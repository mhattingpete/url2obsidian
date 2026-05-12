from collections.abc import Iterable
from pathlib import Path

from url2obsidian.models import Article, FetchResult, Item, ItemMeta
from url2obsidian.protocols import Extractor, Fetcher, RaindropAPI, VaultWriter


class _RaindropImpl:
    def list_unclipped(self) -> Iterable[Item]:
        return []

    def mark_clipped(self, item_id: int, tag: str) -> None:
        pass

    def mark_failed(self, item_id: int, reason: str) -> None:
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
    assert isinstance(_RaindropImpl(), RaindropAPI)
    assert isinstance(_FetcherImpl(), Fetcher)
    assert isinstance(_ExtractorImpl(), Extractor)
    assert isinstance(_VaultImpl(), VaultWriter)
