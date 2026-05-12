import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import structlog
import typer

from url2obsidian.config import DEFAULT_CONFIG_PATH, DEFAULT_INBOX_DIR, Config, load_config
from url2obsidian.extractor import DefuddleExtractor
from url2obsidian.fetcher import PlaywrightBrowser, TwoTierFetcher
from url2obsidian.inbox import FileInbox
from url2obsidian.models import Item, ItemMeta
from url2obsidian.renderer import render
from url2obsidian.vault import FileVaultWriter
from url2obsidian.worker import run_once as worker_run_once

app = typer.Typer(no_args_is_help=True, add_completion=False)
log = structlog.get_logger("url2obsidian.cli")


def _cli_path() -> Path:
    """Locate tools/defuddle-cli/node_modules/.bin/defuddle from a project checkout."""
    here = Path(__file__).resolve()
    for ancestor in [here.parent, *here.parents]:
        cand = ancestor / "tools" / "defuddle-cli" / "node_modules" / ".bin" / "defuddle"
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "tools/defuddle-cli/node_modules/.bin/defuddle not found. "
        "Run `cd tools/defuddle-cli && npm install` from the project checkout."
    )


def _build(
    config: Config,
) -> tuple[FileInbox, TwoTierFetcher, DefuddleExtractor, FileVaultWriter]:
    inbox = FileInbox(inbox_dir=config.inbox_dir)
    fetcher = TwoTierFetcher(browser=PlaywrightBrowser())
    extractor = DefuddleExtractor(cli_path=_cli_path())
    vault = FileVaultWriter(
        vault_path=config.vault_path,
        clippings_subdir=config.clippings_subdir,
        download_images=config.download_images,
    )
    return inbox, fetcher, extractor, vault


@app.command()
def init() -> None:
    """Create the iCloud inbox directory + config file, and print Shortcut setup steps."""
    DEFAULT_INBOX_DIR.mkdir(parents=True, exist_ok=True)
    inbox_file = DEFAULT_INBOX_DIR / "inbox.txt"
    if not inbox_file.exists():
        inbox_file.touch()
    typer.echo(f"Inbox directory: {DEFAULT_INBOX_DIR}")
    typer.echo("  inbox.txt    -> Shortcut appends URLs here")
    typer.echo("  processed.log -> successful clippings (audit)")
    typer.echo("  failed.log   -> failed URLs with reason (audit)")

    if not DEFAULT_CONFIG_PATH.exists():
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text(_DEFAULT_CONFIG_TEMPLATE)
        typer.echo(f"\nWrote config template to {DEFAULT_CONFIG_PATH}")
        typer.echo("Edit vault_path to point at your Obsidian vault.")
    else:
        typer.echo(f"\nConfig already exists at {DEFAULT_CONFIG_PATH}; left untouched.")

    typer.echo("\n--- iOS Shortcut setup ---")
    typer.echo("1. iPhone: Shortcuts app -> + (new) -> name it 'Save to Obsidian'.")
    typer.echo("2. Open settings (i): toggle 'Show in Share Sheet' ON.")
    typer.echo("3. Add ONE action: 'Append to Text File'.")
    typer.echo("   - File: iCloud Drive -> Shortcuts -> url2obsidian -> inbox.txt")
    typer.echo("     (NOT the top-level iCloud Drive/url2obsidian -- iOS writes")
    typer.echo("      into the Shortcuts app's own container by default.)")
    typer.echo("   - Text: tap the field, then the 'Shortcut Input' magic variable.")
    typer.echo("   - Append: ON. Line break: Append.")
    typer.echo("4. Save. Share a URL from Safari -> 'Save to Obsidian'.")
    typer.echo("5. Spell-check the filename in the picker -- 'inbox.txt' not 'indbox.txt'.\n")

    typer.echo("To install the launchd agent:")
    typer.echo(
        "  cp packaging/com.mhattingpete.url2obsidian.plist.template "
        "~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist"
    )
    typer.echo("  # edit the plist to point at your uv binary and project path")
    typer.echo("  launchctl load ~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist")


@app.command()
def enqueue(url: str) -> None:
    """Manually append a URL to the inbox (testing convenience; bypasses iOS)."""
    config = load_config()
    inbox = FileInbox(inbox_dir=config.inbox_dir)
    inbox.enqueue(url)
    typer.echo(f"Enqueued: {url}")


@app.command("run-once")
def run_once_cmd() -> None:
    config = load_config()
    inbox, fetcher, extractor, vault = _build(config)
    worker_run_once(inbox, fetcher, extractor, vault)


@app.command()
def daemon() -> None:
    config = load_config()
    inbox, fetcher, extractor, vault = _build(config)
    log.info("daemon_start", interval=config.poll_interval_seconds)
    while True:
        try:
            worker_run_once(inbox, fetcher, extractor, vault)
        except Exception as e:
            log.error("run_failed", error=str(e))
        time.sleep(config.poll_interval_seconds)


@app.command()
def clip(url: str) -> None:
    """Clip a single URL directly to the vault, bypassing the inbox."""
    config = load_config()
    fetcher = TwoTierFetcher(browser=PlaywrightBrowser())
    extractor = DefuddleExtractor(cli_path=_cli_path())
    vault = FileVaultWriter(
        vault_path=config.vault_path,
        clippings_subdir=config.clippings_subdir,
        download_images=config.download_images,
    )

    fetched = fetcher.fetch(url)
    article = extractor.extract(fetched.html, url)
    if len(article.content_markdown.strip()) < 200:
        typer.echo(
            f"Extracted content too short ({len(article.content_markdown)} chars).",
            err=True,
        )
        raise typer.Exit(1)

    item = Item(url=url, received_at=datetime.now(UTC))
    meta = ItemMeta.from_item(item)
    final = render(article, meta, clipped_at=datetime.now(UTC))
    article_with_fm = replace(article, content_markdown=final)
    path = vault.write(article_with_fm, meta)
    typer.echo(f"Wrote {path}")


_DEFAULT_CONFIG_TEMPLATE = """\
vault_path            = "/Users/CHANGEME/Documents/Obsidian Vault"
clippings_subdir      = "Clippings"
poll_interval_seconds = 300
download_images       = true
notification_on_error = true
"""


if __name__ == "__main__":
    app()
