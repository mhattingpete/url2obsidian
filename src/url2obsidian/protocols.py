from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from url2obsidian.models import Article, FetchResult, Item, ItemMeta


@runtime_checkable
class RaindropAPI(Protocol):
    def list_unclipped(self) -> Iterable[Item]: ...
    def mark_clipped(self, item_id: int, tag: str) -> None: ...
    def mark_failed(self, item_id: int, reason: str) -> None: ...


@runtime_checkable
class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchResult: ...


@runtime_checkable
class Extractor(Protocol):
    def extract(self, html: str, url: str) -> Article: ...


@runtime_checkable
class VaultWriter(Protocol):
    def write(self, article: Article, meta: ItemMeta) -> Path: ...
