# url2obsidian

Share URLs from iPhone -> Raindrop.io -> auto-clipped into your Obsidian vault.

See `docs/superpowers/specs/2026-05-12-url2obsidian-design.md` for the design.

## Setup

1. `uv sync`
2. `cd tools/defuddle-cli && npm install && cd ../..`
3. `playwright install chromium`
4. `uv run url2obsidian configure`
5. See `packaging/` for the launchd install instructions printed by `configure`.
