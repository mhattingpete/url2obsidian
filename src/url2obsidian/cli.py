import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import keyring
import structlog
import typer

from url2obsidian.config import DEFAULT_CONFIG_PATH, Config, load_config
from url2obsidian.extractor import DefuddleExtractor
from url2obsidian.fetcher import PlaywrightBrowser, TwoTierFetcher
from url2obsidian.models import ItemMeta
from url2obsidian.raindrop_client import RaindropClient
from url2obsidian.renderer import render
from url2obsidian.vault import FileVaultWriter
from url2obsidian.worker import run_once as worker_run_once

app = typer.Typer(no_args_is_help=True, add_completion=False)
log = structlog.get_logger("url2obsidian.cli")

_KEYRING_SERVICE = "url2obsidian"
_KEYRING_USER = "raindrop-token"


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
) -> tuple[RaindropClient, TwoTierFetcher, DefuddleExtractor, FileVaultWriter]:
    token = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    if not token:
        typer.echo(
            "No Raindrop token in keychain. Run `url2obsidian configure` first.",
            err=True,
        )
        raise typer.Exit(2)
    api = RaindropClient(
        token=token,
        inbox_collection=config.inbox_collection,
        clipped_collection=config.clipped_collection,
        failed_collection=config.failed_collection,
    )
    fetcher = TwoTierFetcher(browser=PlaywrightBrowser())
    extractor = DefuddleExtractor(cli_path=_cli_path())
    vault = FileVaultWriter(
        vault_path=config.vault_path,
        clippings_subdir=config.clippings_subdir,
        download_images=config.download_images,
    )
    return api, fetcher, extractor, vault


@app.command()
def configure() -> None:
    """Store a Raindrop token in the macOS Keychain and seed the config file."""
    token = typer.prompt("Raindrop personal access token", hide_input=True)
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, token)
    typer.echo("Token stored in Keychain.")

    if not DEFAULT_CONFIG_PATH.exists():
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text(_DEFAULT_CONFIG_TEMPLATE)
        typer.echo(f"Wrote config template to {DEFAULT_CONFIG_PATH}")
        typer.echo("Edit it to point at your vault, then re-run.")
    else:
        typer.echo(f"Config already exists at {DEFAULT_CONFIG_PATH}; left untouched.")

    typer.echo("\nTo install the launchd agent:")
    typer.echo(
        "  cp packaging/com.mhattingpete.url2obsidian.plist.template "
        "~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist"
    )
    typer.echo("  # edit the plist to point at your uv binary and project path")
    typer.echo("  launchctl load ~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist")


@app.command("run-once")
def run_once_cmd() -> None:
    config = load_config()
    api, fetcher, extractor, vault = _build(config)
    worker_run_once(api, fetcher, extractor, vault)


@app.command()
def daemon() -> None:
    config = load_config()
    api, fetcher, extractor, vault = _build(config)
    log.info("daemon_start", interval=config.poll_interval_seconds)
    while True:
        try:
            worker_run_once(api, fetcher, extractor, vault)
        except Exception as e:
            log.error("run_failed", error=str(e))
        time.sleep(config.poll_interval_seconds)


@app.command()
def clip(url: str) -> None:
    """Clip a single URL directly to the vault, bypassing Raindrop."""
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

    meta = ItemMeta(
        raindrop_id=0,
        source_url=url,
        raindrop_title=article.title,
        raindrop_excerpt="",
        tags=("manual",),
        created=datetime.now(UTC),
    )
    final = render(article, meta, clipped_at=datetime.now(UTC))
    article_with_fm = replace(article, content_markdown=final)
    path = vault.write(article_with_fm, meta)
    typer.echo(f"Wrote {path}")


_DEFAULT_CONFIG_TEMPLATE = """\
vault_path          = "/Users/CHANGEME/Obsidian/MainVault"
clippings_subdir    = "Clippings"
inbox_collection    = "Unclipped"
clipped_collection  = "Clipped"
failed_collection   = "Failed"
poll_interval_seconds = 300
download_images       = true
notification_on_error = true
"""


if __name__ == "__main__":
    app()
