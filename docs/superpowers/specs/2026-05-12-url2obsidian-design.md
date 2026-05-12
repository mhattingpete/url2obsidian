# url2obsidian — design

**Date:** 2026-05-12
**Status:** Draft for review
**Author:** Mathias (with Claude)

## Goal

Capture article URLs from an iPhone in seconds and have full, clean-markdown
clippings appear in the Obsidian vault automatically — matching the behavior
of the desktop Obsidian Web Clipper extension.

## Non-goals

- No mobile editing of the vault. The phone only enqueues URLs.
- No real-time clipping. A delay of up to one polling interval is acceptable.
- No support for non-article content (PDFs, videos, tweets) in v1.
- No multi-user / multi-vault support.
- No custom per-site clipping templates in v1. (defuddle's default behavior only.)

## Constraints

- iPhone (iOS) for capture; macOS for processing.
- Python is the primary language (uv, ruff, ty).
- Vault lives on macOS only at the start; mobile vault sync is out of scope.
- Free-tier services preferred. Raindrop.io free tier is sufficient.
- Secrets stored in macOS Keychain (`keyring`), not in dotfiles.

## High-level architecture

```
[iPhone Share Sheet]                   [Mac — laptop-on]
       |                                          |
       v                                          v
  Raindrop iOS app ---> Raindrop.io --poll--->  url2obsidian worker
                       (cloud inbox)              |
                                                  |-- fetch URL (httpx, Playwright fallback)
                                                  |-- extract via defuddle CLI (Node subprocess)
                                                  |-- render markdown from template
                                                  |-- write vault/Clippings/<slug>.md
                                                  '-- PATCH Raindrop: Inbox -> Clipped
```

Capture (iPhone -> Raindrop) and processing (Mac worker pulling from Raindrop)
are independent; they communicate only via the Raindrop REST API.

## Capture side (iPhone)

Zero custom code.

1. Install the Raindrop iOS app and sign in.
2. Create a collection `Inbox/Unclipped` and set it as the default.
3. Share any URL via the system Share Sheet -> Raindrop. Tags optional.
4. (Optional) An iOS Shortcut wrapper that pre-applies tag `from-phone`.

## Processing side (Mac)

### Initial setup

One-time, interactive: `url2obsidian configure` prompts for a Raindrop personal
access token and stores it in the macOS Keychain via `keyring`. Same command
seeds `~/.config/url2obsidian/config.toml` from a template if absent, and
prints the launchd `launchctl load` instruction.

### Architecture pattern

Dependency inversion at the seams using `typing.Protocol`. No full onion / clean
architecture folder split — the project is too small to earn that overhead.
Flat package layout; one composition root in `cli.py`.

### Components

**`url2obsidian` (Python package, uv-managed)** — flat layout:

| Module | Responsibility |
|---|---|
| `protocols.py` | `RaindropAPI`, `Fetcher`, `Extractor`, `VaultWriter` Protocols |
| `raindrop_client.py` | httpx client for Raindrop REST API; token from `keyring` |
| `fetcher.py` | httpx GET; Playwright fallback for JS-rendered pages |
| `extractor.py` | subprocess wrapper around the Node defuddle CLI |
| `renderer.py` | Jinja2 template -> final markdown with YAML frontmatter |
| `vault.py` | slugify, collision-resolve, write file, optional image download |
| `worker.py` | orchestrator: poll -> per item: fetch -> extract -> render -> write -> archive |
| `cli.py` | composition root + Typer CLI: `configure`, `run-once`, `daemon`, `clip <url>` |
| `config.py` | TOML config loader, model validated with pydantic |

**`tools/defuddle-cli/` (Node sidecar)** — minimal:

```js
// reads {html, url} JSON from stdin, runs defuddle, writes {title, byline,
// content_markdown, published, site_name, ...} JSON to stdout. No HTTP, no
// daemon. Invoked once per article by the Python worker via subprocess.
```

**launchd plist** — `~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist`
- Runs `url2obsidian run-once` every `poll_interval_seconds` (default 300).
- `RunAtLoad: true`, `KeepAlive: false`.
- Logs to `~/Library/Logs/url2obsidian/{stdout,stderr}.log`.

**Config file** — `~/.config/url2obsidian/config.toml`:

```toml
vault_path          = "/Users/map/Obsidian/MainVault"
clippings_subdir    = "Clippings"
inbox_collection    = "Inbox/Unclipped"
clipped_collection  = "Inbox/Clipped"
failed_collection   = "Inbox/Failed"
poll_interval_seconds = 300
download_images     = true
notification_on_error = true
```

### Protocols (the only "architecture" we keep)

```python
class RaindropAPI(Protocol):
    def list_unclipped(self) -> Iterable[Item]: ...
    def mark_clipped(self, item_id: int, tag: str) -> None: ...
    def mark_failed(self, item_id: int, reason: str) -> None: ...

class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchResult: ...

class Extractor(Protocol):
    def extract(self, html: str, url: str) -> Article: ...

class VaultWriter(Protocol):
    def write(self, article: Article, meta: ItemMeta) -> Path: ...
```

The worker depends only on these. Real implementations live in their modules.
Fakes live in `tests/`.

## Data flow (single URL, happy path)

1. **T+0s** — User taps Share -> Raindrop. Raindrop saves
   `{link, title, excerpt, tags:["from-phone"]}` in `Inbox/Unclipped`.
2. **T+<=300s** — launchd fires `url2obsidian run-once`.
3. Worker calls `GET /raindrops/<inbox_id>?perpage=50`, paginates if needed.
4. For each item (sequential, no concurrency in v1):
   1. `httpx.get(url, follow_redirects=True, timeout=15s)` with realistic User-Agent.
   2. If response is HTML and >2KB, send to defuddle. Otherwise -> Playwright
      fallback: load page, wait for `networkidle`, dump rendered HTML, then defuddle.
   3. Pipe HTML+URL to `defuddle-cli`; parse returned JSON.
   4. Build slug from title; resolve collisions with `-2`, `-3`, ..., `-10`.
   5. If `download_images=true`: walk markdown for image URLs, download into
      `<vault>/Clippings/_assets/<slug>/`, rewrite refs to relative paths.
   6. Render via Jinja template -> write `<vault>/Clippings/<slug>.md`.
   7. `PUT /raindrop/<id>` -> move to `Clipped`, add tag `clipped-YYYY-MM-DD`.
5. Worker writes one structured log line per item:
   `{id, url, status, duration_ms, output_path}`.
6. Exit 0.

### Output frontmatter

```yaml
---
title: "<extracted title>"
source: "<original url>"
author: "<byline>"
published: "<iso date if found>"
site: "<site_name>"
clipped: "2026-05-12T10:33:00+02:00"
raindrop_id: 1234567
tags: [clippings, from-phone]
---
```

Body follows: article markdown with preserved headings, lists, code blocks,
and image references.

## Error handling

| Failure | Behavior |
|---|---|
| Raindrop 401/403 | Hard stop. macOS notification ("re-auth needed"). No retry. |
| Raindrop 429 / 5xx | Exponential backoff (1s, 4s, 16s, then give up). Item stays in Unclipped; next run retries. |
| Fetch timeout / network error | Retry once after 30s. Else tag `clip-error:fetch`, move to Failed. |
| HTTP 4xx (dead, paywall) | No retry. Tag `clip-error:http-<code>`, move to Failed. |
| Defuddle empty / <500 chars | Trigger Playwright fallback. If still empty -> `clip-error:empty`, Failed. |
| Defuddle subprocess error | Tag `clip-error:extractor`, move to Failed. Log stderr. |
| Vault path missing / unwritable | Hard stop with notification. Don't touch Raindrop state. |
| Filename collision | `-2`, `-3`, ..., `-10`. Beyond that: `clip-error:naming`. |
| Image download failure | Non-fatal. Keep remote URL; frontmatter `images_partial: true`. |
| Worker crashes mid-item | launchd re-fires next interval. Re-processing is idempotent. |
| Two concurrent runs | `flock` PID file in `~/Library/Caches/url2obsidian/` ensures single instance. |

### Principles

1. **Raindrop is the source of truth.** The worker never deletes items; it
   only moves them between collections and adds tags. Failed items are always
   inspectable.
2. **Idempotent retries.** Reprocessing the same item produces the same
   output file (or a `-2` if you've manually edited the prior one).
3. **Loud failures, quiet successes.** macOS notification only on hard stops
   (auth, vault). Item-level errors go to the `Failed` collection and the log.

## Testing

- **Unit tests (pytest)** per adapter against its Protocol, using fixture HTML
  and fake implementations of the others. No network, fast.
  - `test_extractor.py` — 8-10 saved HTML fixtures (Substack, NYT-like,
    GitHub README, JS-skeleton, 404, empty); assert title and word-count
    thresholds.
  - `test_fetcher.py` — `respx` mocks; verify timeout, redirect, and
    Playwright fallback trigger.
  - `test_raindrop_client.py` — `respx` against recorded API responses;
    verify pagination and error mapping.
  - `test_vault.py` — `tmp_path`; slug, collision suffix, frontmatter
    ordering, image rewriting.
  - `test_renderer.py` — golden-file: known `Article` + `ItemMeta` produces
    byte-identical markdown.
- **Worker orchestration tests** with all four Protocols stubbed. State
  machine: success path; each error class lands in `Failed` with right tag;
  idempotency.
- **One manual end-to-end test** (not CI): `url2obsidian clip <stable url>`
  against a temp vault, assert non-trivial output. Documented in README.
- **No mocking the Node CLI in unit tests.** Call the real `defuddle-cli`
  binary with fixture HTML; a mock would just reimplement defuddle wrong.
- **Type checking:** `ty` strict on `src/`.
- **Lint/format:** `ruff` + `ruff format`.
- **CI:** GitHub Actions runs `uv sync`, `ty`, `ruff`, `pytest` on push.
  Playwright browsers cached.

## Out of scope (future work)

- Mobile Obsidian vault sync.
- Per-site custom Web Clipper templates.
- Clipping non-article content (PDFs, YouTube, tweets).
- A web UI for the `Failed` queue (CLI inspection is enough at v1).
- Parallel processing of items within one run.

## Open questions

None at design time. Implementation may surface defuddle edge cases that
require small extractor pre/post-processing; those will be handled in the
plan.
