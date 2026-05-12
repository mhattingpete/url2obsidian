from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from url2obsidian.models import Article, ItemMeta
from url2obsidian.vault import FileVaultWriter, slugify


def _meta(rid: int = 1) -> ItemMeta:
    return ItemMeta(
        raindrop_id=rid,
        source_url="https://example.com/post",
        raindrop_title="A",
        raindrop_excerpt="",
        tags=("from-phone",),
        created=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc),
    )


def _article(title: str = "Hello World") -> Article:
    return Article(
        title=title,
        byline="Jane Doe",
        content_markdown="# Hello\n\nBody.",
        published=None,
        site_name="example.com",
    )


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"
    assert slugify("  Trim & Punct!  ") == "trim-punct"
    assert slugify("Already-Slugged-1") == "already-slugged-1"


def test_slugify_collapses_whitespace_and_unicode():
    assert slugify("café résumé") == "cafe-resume"
    assert slugify("a\nb\tc") == "a-b-c"


def test_slugify_empty_falls_back():
    assert slugify("").startswith("untitled-")


def test_write_creates_file(tmp_path: Path):
    writer = FileVaultWriter(
        vault_path=tmp_path, clippings_subdir="Clippings", download_images=False
    )
    path = writer.write(_article("My Post"), _meta())
    assert path == tmp_path / "Clippings" / "my-post.md"
    assert path.exists()
    assert "# Hello" in path.read_text()


def test_write_collision_appends_suffix(tmp_path: Path):
    writer = FileVaultWriter(
        vault_path=tmp_path, clippings_subdir="Clippings", download_images=False
    )
    p1 = writer.write(_article("Same Title"), _meta(rid=1))
    p2 = writer.write(_article("Same Title"), _meta(rid=2))
    p3 = writer.write(_article("Same Title"), _meta(rid=3))
    assert p1.name == "same-title.md"
    assert p2.name == "same-title-2.md"
    assert p3.name == "same-title-3.md"


def test_write_collision_gives_up_after_ten(tmp_path: Path):
    writer = FileVaultWriter(
        vault_path=tmp_path, clippings_subdir="Clippings", download_images=False
    )
    for i in range(10):
        writer.write(_article("Dup"), _meta(rid=i))
    with pytest.raises(RuntimeError, match="naming"):
        writer.write(_article("Dup"), _meta(rid=99))


def test_write_downloads_images_when_enabled(tmp_path: Path):
    article = Article(
        title="With Image",
        byline="",
        content_markdown="Hello ![alt](https://img.example.com/pic.png) world",
        published=None,
        site_name="example.com",
    )
    with respx.mock:
        respx.get("https://img.example.com/pic.png").mock(
            return_value=httpx.Response(200, content=b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        )
        writer = FileVaultWriter(
            vault_path=tmp_path, clippings_subdir="Clippings", download_images=True
        )
        path = writer.write(article, _meta())
    assert path.exists()
    content = path.read_text()
    assert "https://img.example.com" not in content
    assert "_assets/with-image/pic.png" in content
    assert (tmp_path / "Clippings" / "_assets" / "with-image" / "pic.png").exists()


def test_write_image_download_failure_is_non_fatal(tmp_path: Path):
    article = Article(
        title="Broken Image",
        byline="",
        content_markdown="![](https://img.example.com/missing.png)",
        published=None,
        site_name="example.com",
    )
    with respx.mock:
        respx.get("https://img.example.com/missing.png").mock(
            return_value=httpx.Response(404)
        )
        writer = FileVaultWriter(
            vault_path=tmp_path, clippings_subdir="Clippings", download_images=True
        )
        path = writer.write(article, _meta())
    assert "https://img.example.com/missing.png" in path.read_text()


def test_write_skips_images_when_disabled(tmp_path: Path):
    article = Article(
        title="Skip",
        byline="",
        content_markdown="![](https://img.example.com/p.png)",
        published=None,
        site_name="example.com",
    )
    writer = FileVaultWriter(
        vault_path=tmp_path, clippings_subdir="Clippings", download_images=False
    )
    path = writer.write(article, _meta())
    assert "https://img.example.com/p.png" in path.read_text()
    assert not (tmp_path / "Clippings" / "_assets").exists()
