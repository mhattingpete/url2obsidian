from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from url2obsidian.models import Article, FetchResult, Item, ItemMeta


class FakeInbox:
    def __init__(self, items: list[Item]) -> None:
        self.items = items
        self.clipped: list[tuple[Item, Path]] = []
        self.failed: list[tuple[Item, str]] = []

    def list_pending(self) -> Iterable[Item]:
        yield from self.items

    def mark_clipped(self, item: Item, clipped_path: Path) -> None:
        self.clipped.append((item, clipped_path))

    def mark_failed(self, item: Item, reason: str) -> None:
        self.failed.append((item, reason))


class FakeFetcher:
    def __init__(self, mapping: dict[str, FetchResult | Exception]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.calls.append(url)
        v = self.mapping[url]
        if isinstance(v, Exception):
            raise v
        return v


class FakeExtractor:
    def __init__(self, mapping: dict[str, Article | Exception]) -> None:
        self.mapping = mapping

    def extract(self, html: str, url: str) -> Article:
        v = self.mapping[url]
        if isinstance(v, Exception):
            raise v
        return v


class FakeVault:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.written: list[Path] = []

    def write(self, article: Article, meta: ItemMeta) -> Path:
        # Use a hash-stable counter-based name since the new model has no id.
        target = self.tmp / f"clip-{len(self.written)}.md"
        target.write_text(article.content_markdown)
        self.written.append(target)
        return target


def make_item(url: str = "https://example.com/x") -> Item:
    return Item(url=url, received_at=datetime(2026, 5, 12, tzinfo=UTC))


def make_article(content: str = "hi") -> Article:
    return Article(
        title="t", byline="", content_markdown=content, published=None, site_name="example.com"
    )
