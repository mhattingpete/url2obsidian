from datetime import datetime

from jinja2 import Environment, StrictUndefined

from url2obsidian.models import Article, ItemMeta

_TEMPLATE = """\
---
title: "{{ title }}"
source: "{{ source }}"
author: "{{ author }}"
published: "{{ published }}"
site: "{{ site }}"
clipped: "{{ clipped }}"
tags: [{{ tags }}]
---

{{ body }}
"""


def render(article: Article, meta: ItemMeta, clipped_at: datetime) -> str:
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    template = env.from_string(_TEMPLATE)
    tags = ["clippings", *meta.tags]
    return template.render(
        title=_escape(article.title),
        source=meta.source_url,
        author=_escape(article.byline),
        published=_iso_date(article.published),
        site=_escape(article.site_name),
        clipped=clipped_at.isoformat(),
        tags=", ".join(tags),
        body=article.content_markdown,
    )


def _escape(value: str) -> str:
    return value.replace('"', '\\"')


def _iso_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.date().isoformat()
