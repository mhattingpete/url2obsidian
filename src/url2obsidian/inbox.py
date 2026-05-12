from datetime import UTC, datetime
from pathlib import Path

from url2obsidian.models import Item


class FileInbox:
    """File-backed inbox queued via iCloud Drive.

    The iOS Shortcut appends URLs (one per line) to ``inbox.txt``. On each
    run, the worker atomically renames ``inbox.txt`` → ``inbox.processing``
    to claim the current snapshot; URLs added by iOS during processing land
    in a fresh ``inbox.txt`` and are picked up the next interval. Outcomes
    are appended to ``processed.log`` (success) or ``failed.log`` (failure)
    as ``<iso-timestamp>\\t<url>\\t<extra>``.
    """

    def __init__(self, inbox_dir: Path) -> None:
        self._dir = inbox_dir
        self._inbox = inbox_dir / "inbox.txt"
        self._processing = inbox_dir / "inbox.processing"
        self._processed = inbox_dir / "processed.log"
        self._failed = inbox_dir / "failed.log"
        self._pending: set[str] = set()

    def list_pending(self) -> list[Item]:
        if not self._processing.exists():
            if not self._inbox.exists():
                return []
            self._dir.mkdir(parents=True, exist_ok=True)
            self._inbox.rename(self._processing)

        received_at = datetime.fromtimestamp(self._processing.stat().st_mtime, tz=UTC)
        items: list[Item] = []
        seen: set[str] = set()
        for line in self._processing.read_text().splitlines():
            url = line.strip()
            if not url or url.startswith("#") or url in seen:
                continue
            seen.add(url)
            items.append(Item(url=url, received_at=received_at))
            self._pending.add(url)
        return items

    def mark_clipped(self, item: Item, clipped_path: Path) -> None:
        self._append_log(self._processed, item.url, str(clipped_path))
        self._pending.discard(item.url)
        self._maybe_drain()

    def mark_failed(self, item: Item, reason: str) -> None:
        self._append_log(self._failed, item.url, reason)
        self._pending.discard(item.url)
        self._maybe_drain()

    def enqueue(self, url: str) -> None:
        """Manually append a URL to inbox.txt (testing/CLI convenience)."""
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._inbox.open("a") as f:
            f.write(url.strip() + "\n")

    def _append_log(self, path: Path, url: str, extra: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).isoformat()
        with path.open("a") as f:
            f.write(f"{ts}\t{url}\t{extra}\n")

    def _maybe_drain(self) -> None:
        if not self._pending and self._processing.exists():
            self._processing.unlink()
