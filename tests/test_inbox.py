from datetime import UTC, datetime
from pathlib import Path

from url2obsidian.inbox import FileInbox
from url2obsidian.models import Item


def _make_item(url: str) -> Item:
    return Item(url=url, received_at=datetime(2026, 5, 12, tzinfo=UTC))


def test_list_pending_empty_when_no_files(tmp_path: Path):
    inbox = FileInbox(tmp_path)
    assert inbox.list_pending() == []


def test_list_pending_claims_inbox_via_atomic_rename(tmp_path: Path):
    (tmp_path / "inbox.txt").write_text("https://example.com/a\nhttps://example.com/b\n")
    inbox = FileInbox(tmp_path)
    items = inbox.list_pending()
    assert [i.url for i in items] == ["https://example.com/a", "https://example.com/b"]
    assert not (tmp_path / "inbox.txt").exists()
    assert (tmp_path / "inbox.processing").exists()


def test_list_pending_ignores_blank_and_comment_lines(tmp_path: Path):
    (tmp_path / "inbox.txt").write_text(
        "https://example.com/a\n\n# a comment\nhttps://example.com/b\n"
    )
    inbox = FileInbox(tmp_path)
    items = inbox.list_pending()
    assert [i.url for i in items] == ["https://example.com/a", "https://example.com/b"]


def test_list_pending_deduplicates(tmp_path: Path):
    (tmp_path / "inbox.txt").write_text(
        "https://example.com/a\nhttps://example.com/a\nhttps://example.com/b\n"
    )
    items = FileInbox(tmp_path).list_pending()
    assert [i.url for i in items] == ["https://example.com/a", "https://example.com/b"]


def test_list_pending_resumes_from_processing_file(tmp_path: Path):
    """Crash recovery: if a previous run left inbox.processing, use it."""
    (tmp_path / "inbox.processing").write_text("https://example.com/leftover\n")
    items = FileInbox(tmp_path).list_pending()
    assert [i.url for i in items] == ["https://example.com/leftover"]


def test_mark_clipped_writes_processed_log(tmp_path: Path):
    (tmp_path / "inbox.txt").write_text("https://example.com/a\n")
    inbox = FileInbox(tmp_path)
    items = inbox.list_pending()
    inbox.mark_clipped(items[0], Path("/vault/Clippings/a.md"))

    log = (tmp_path / "processed.log").read_text()
    assert "https://example.com/a" in log
    assert "/vault/Clippings/a.md" in log
    assert "\t" in log  # tab-separated


def test_mark_failed_writes_failed_log(tmp_path: Path):
    (tmp_path / "inbox.txt").write_text("https://example.com/bad\n")
    inbox = FileInbox(tmp_path)
    items = inbox.list_pending()
    inbox.mark_failed(items[0], "http-404")

    log = (tmp_path / "failed.log").read_text()
    assert "https://example.com/bad" in log
    assert "http-404" in log


def test_processing_file_deleted_when_all_items_resolved(tmp_path: Path):
    (tmp_path / "inbox.txt").write_text("https://example.com/a\nhttps://example.com/b\n")
    inbox = FileInbox(tmp_path)
    items = inbox.list_pending()
    inbox.mark_clipped(items[0], Path("/vault/a.md"))
    assert (tmp_path / "inbox.processing").exists()  # still has b pending
    inbox.mark_failed(items[1], "extractor")
    assert not (tmp_path / "inbox.processing").exists()


def test_processing_file_remains_if_some_items_unresolved(tmp_path: Path):
    """If the worker crashes mid-loop, inbox.processing stays for retry."""
    (tmp_path / "inbox.txt").write_text("https://example.com/a\nhttps://example.com/b\n")
    inbox = FileInbox(tmp_path)
    items = inbox.list_pending()
    inbox.mark_clipped(items[0], Path("/vault/a.md"))
    assert (tmp_path / "inbox.processing").exists()


def test_new_urls_added_during_processing_survive(tmp_path: Path):
    """iOS adds a URL while the worker is processing; the new URL must persist."""
    (tmp_path / "inbox.txt").write_text("https://example.com/old\n")
    inbox = FileInbox(tmp_path)
    items = inbox.list_pending()  # renames inbox.txt -> inbox.processing
    # Simulate iOS Shortcut appending while the worker runs.
    (tmp_path / "inbox.txt").write_text("https://example.com/new\n")
    inbox.mark_clipped(items[0], Path("/vault/old.md"))
    # processing file gets cleaned up; the new inbox.txt is preserved
    assert not (tmp_path / "inbox.processing").exists()
    assert (tmp_path / "inbox.txt").read_text().strip() == "https://example.com/new"


def test_enqueue_appends_to_inbox(tmp_path: Path):
    inbox = FileInbox(tmp_path)
    inbox.enqueue("https://example.com/a")
    inbox.enqueue("https://example.com/b")
    content = (tmp_path / "inbox.txt").read_text()
    assert content == "https://example.com/a\nhttps://example.com/b\n"
