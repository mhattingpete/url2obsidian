from datetime import datetime, timezone

from url2obsidian.models import Article, FetchResult, Item, ItemMeta


def test_item_is_frozen():
    item = Item(
        id=1,
        url="https://example.com/a",
        title="A",
        excerpt="ex",
        tags=("from-phone",),
        created=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )
    try:
        item.id = 2  # type: ignore[misc]
    except Exception as e:
        assert "frozen" in str(e).lower() or "cannot assign" in str(e).lower()
    else:
        raise AssertionError("Item should be frozen")


def test_item_meta_derives_from_item():
    item = Item(
        id=42,
        url="https://example.com/x",
        title="raw title",
        excerpt="",
        tags=("from-phone",),
        created=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )
    meta = ItemMeta.from_item(item)
    assert meta.raindrop_id == 42
    assert meta.source_url == "https://example.com/x"
    assert "from-phone" in meta.tags


def test_article_has_required_fields():
    a = Article(
        title="T",
        byline="B",
        content_markdown="# hi",
        published=None,
        site_name="example.com",
    )
    assert a.title == "T"
    assert a.content_markdown.startswith("# hi")


def test_fetch_result_carries_html_and_method():
    fr = FetchResult(url="https://x", html="<html></html>", method="httpx", status=200)
    assert fr.method in {"httpx", "playwright"}
