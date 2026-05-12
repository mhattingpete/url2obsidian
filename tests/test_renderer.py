from datetime import UTC, datetime
from pathlib import Path

from url2obsidian.models import Article, ItemMeta
from url2obsidian.renderer import render

FIXTURES = Path(__file__).parent / "fixtures"


def test_render_matches_golden():
    article = Article(
        title="Hello World",
        byline="Jane Doe",
        content_markdown="# Hello\n\nBody.",
        published=datetime(2026, 4, 1, tzinfo=UTC),
        site_name="example.com",
    )
    meta = ItemMeta(
        source_url="https://example.com/post",
        received_at=datetime(2026, 5, 12, tzinfo=UTC),
        tags=("from-phone",),
    )
    fixed_clipped_at = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)
    rendered = render(article, meta, clipped_at=fixed_clipped_at)
    expected = (FIXTURES / "expected_clipping.md").read_text()
    assert rendered == expected


def test_render_handles_missing_published():
    article = Article(
        title="No Date",
        byline="",
        content_markdown="Body",
        published=None,
        site_name="example.com",
    )
    meta = ItemMeta(
        source_url="https://x",
        received_at=datetime(2026, 5, 12, tzinfo=UTC),
        tags=(),
    )
    out = render(article, meta, clipped_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC))
    assert 'published: ""' in out or "published:" not in out
    assert "Body" in out
