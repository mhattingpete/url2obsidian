from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class Item:
    id: int
    url: str
    title: str
    excerpt: str
    tags: tuple[str, ...]
    created: datetime


@dataclass(frozen=True, slots=True)
class ItemMeta:
    raindrop_id: int
    source_url: str
    raindrop_title: str
    raindrop_excerpt: str
    tags: tuple[str, ...]
    created: datetime

    @classmethod
    def from_item(cls, item: Item) -> "ItemMeta":
        return cls(
            raindrop_id=item.id,
            source_url=item.url,
            raindrop_title=item.title,
            raindrop_excerpt=item.excerpt,
            tags=item.tags,
            created=item.created,
        )


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
