from dataclasses import replace
from datetime import UTC, datetime

import httpx
import structlog

from url2obsidian.extractor import ExtractorError
from url2obsidian.models import Item, ItemMeta
from url2obsidian.protocols import Extractor, Fetcher, Inbox, VaultWriter
from url2obsidian.renderer import render

log = structlog.get_logger("url2obsidian")

_MIN_CONTENT_CHARS = 200


def run_once(
    inbox: Inbox,
    fetcher: Fetcher,
    extractor: Extractor,
    vault: VaultWriter,
) -> None:
    for item in inbox.list_pending():
        _process_one(item, inbox, fetcher, extractor, vault)


def _process_one(
    item: Item,
    inbox: Inbox,
    fetcher: Fetcher,
    extractor: Extractor,
    vault: VaultWriter,
) -> None:
    try:
        fetched = fetcher.fetch(item.url)
    except httpx.HTTPStatusError as e:
        reason = f"http-{e.response.status_code}"
        log.warning("fetch_http_error", url=item.url, status=e.response.status_code)
        inbox.mark_failed(item, reason)
        return
    except httpx.HTTPError:
        log.warning("fetch_error", url=item.url)
        inbox.mark_failed(item, "fetch")
        return

    try:
        article = extractor.extract(fetched.html, item.url)
    except ExtractorError:
        log.warning("extractor_error", url=item.url)
        inbox.mark_failed(item, "extractor")
        return

    if len(article.content_markdown.strip()) < _MIN_CONTENT_CHARS:
        log.warning("empty_content", url=item.url)
        inbox.mark_failed(item, "empty")
        return

    meta = ItemMeta.from_item(item)
    final_md = render(article, meta, clipped_at=datetime.now(UTC))
    article_with_fm = replace(article, content_markdown=final_md)

    try:
        path = vault.write(article_with_fm, meta)
    except Exception as e:
        log.warning("vault_error", url=item.url, error=str(e))
        inbox.mark_failed(item, "vault")
        return

    inbox.mark_clipped(item, path)
    log.info("clipped", url=item.url, path=str(path))
