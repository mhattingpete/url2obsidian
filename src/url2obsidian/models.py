from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class Item:
    """A URL queued for clipping. The inbox supplies these; downstream code
    uses `url` to fetch and `received_at` for provenance."""

    url: str
    received_at: datetime


@dataclass(frozen=True, slots=True)
class ItemMeta:
    """Provenance for a clipping, written into the markdown frontmatter."""

    source_url: str
    received_at: datetime
    tags: tuple[str, ...] = ("from-phone",)

    @classmethod
    def from_item(cls, item: Item) -> "ItemMeta":
        return cls(source_url=item.url, received_at=item.received_at)


@dataclass(frozen=True, slots=True)
class Article:
    title: str
    byline: str
    content_markdown: str
    published: datetime | None
    site_name: str
    images: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    html: str
    method: Literal["httpx", "playwright"]
    status: int
