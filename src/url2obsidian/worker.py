from dataclasses import replace
from datetime import UTC, date, datetime

import httpx
import structlog

from url2obsidian.extractor import ExtractorError
from url2obsidian.models import ItemMeta
from url2obsidian.protocols import Extractor, Fetcher, RaindropAPI, VaultWriter
from url2obsidian.renderer import render

log = structlog.get_logger("url2obsidian")

_MIN_CONTENT_CHARS = 200


def run_once(
    api: RaindropAPI,
    fetcher: Fetcher,
    extractor: Extractor,
    vault: VaultWriter,
) -> None:
    for item in api.list_unclipped():
        _process_one(item, api, fetcher, extractor, vault)


def _process_one(item, api, fetcher, extractor, vault) -> None:
    try:
        fetched = fetcher.fetch(item.url)
    except httpx.HTTPStatusError as e:
        reason = f"http-{e.response.status_code}"
        log.warning("fetch_http_error", id=item.id, url=item.url, status=e.response.status_code)
        api.mark_failed(item.id, reason)
        return
    except httpx.HTTPError:
        log.warning("fetch_error", id=item.id, url=item.url)
        api.mark_failed(item.id, "fetch")
        return

    try:
        article = extractor.extract(fetched.html, item.url)
    except ExtractorError:
        log.warning("extractor_error", id=item.id, url=item.url)
        api.mark_failed(item.id, "extractor")
        return

    if len(article.content_markdown.strip()) < _MIN_CONTENT_CHARS:
        log.warning("empty_content", id=item.id, url=item.url)
        api.mark_failed(item.id, "empty")
        return

    meta = ItemMeta.from_item(item)
    clipped_at = datetime.now(UTC)
    final_md = render(article, meta, clipped_at=clipped_at)
    article_with_fm = replace(article, content_markdown=final_md)

    try:
        path = vault.write(article_with_fm, meta)
    except Exception as e:
        log.warning("vault_error", id=item.id, url=item.url, error=str(e))
        api.mark_failed(item.id, "vault")
        return

    tag = f"clipped-{date.today().isoformat()}"
    api.mark_clipped(item.id, tag)
    log.info("clipped", id=item.id, url=item.url, path=str(path))
