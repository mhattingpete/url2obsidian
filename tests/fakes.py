from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from url2obsidian.models import Article, FetchResult, Item, ItemMeta


class FakeRaindrop:
    def __init__(self, items: list[Item]) -> None:
        self.items = items
        self.clipped: list[tuple[int, str]] = []
        self.failed: list[tuple[int, str]] = []

    def list_unclipped(self) -> Iterable[Item]:
        yield from self.items

    def mark_clipped(self, item_id: int, tag: str) -> None:
        self.clipped.append((item_id, tag))

    def mark_failed(self, item_id: int, reason: str) -> None:
        self.failed.append((item_id, reason))


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
        target = self.tmp / f"{meta.raindrop_id}.md"
        target.write_text(article.content_markdown)
        self.written.append(target)
        return target


def make_item(rid: int, url: str = "https://example.com/x") -> Item:
    return Item(
        id=rid,
        url=url,
        title=f"item-{rid}",
        excerpt="",
        tags=("from-phone",),
        created=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )


def make_article(content: str = "hi") -> Article:
    return Article(
        title="t",
        byline="",
        content_markdown=content,
        published=None,
        site_name="example.com",
    )
