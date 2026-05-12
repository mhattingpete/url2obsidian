# url2obsidian

Share a URL from your iPhone → it lands as a clipped markdown note in your
Obsidian vault within minutes. No third-party services; just iCloud Drive
and a small Mac worker.

```
iPhone Share Sheet → iOS Shortcut → iCloud Drive/url2obsidian/inbox.txt
                                              ↓
                                    url2obsidian (Mac, launchd every 5 min)
                                              ↓
                                    fetch + defuddle + render
                                              ↓
                                <vault>/Clippings/<slug>.md
```

## Install

```
git clone <this repo>
cd url2obsidian
uv sync
(cd tools/defuddle-cli && npm install)
uv run playwright install chromium
uv run url2obsidian init
```

`init` creates the iCloud inbox directory, writes a config template to
`~/.config/url2obsidian/config.toml`, and prints the iOS Shortcut steps.
Edit the config to point at your Obsidian vault.

### iOS Shortcut (one-time, ~3 minutes)

On iPhone, Shortcuts app → **+** → name it "Save to Obsidian":

1. Open settings (the **`ⓘ`** icon) → toggle **"Show in Share Sheet"** ON.
2. Add **one** action: **Append to Text File**.
   - **File**: iCloud Drive → Shortcuts → `url2obsidian` → `inbox.txt`
   - **Text**: tap the field, then the **Shortcut Input** magic-variable chip.
   - **Append**: ON. **Line break**: Append.
3. Save. Share a URL from Safari → pick **Save to Obsidian**.

#### Path gotcha

iOS Shortcuts' file picker shows two iCloud locations that look similar:

- **`iCloud Drive/Shortcuts/url2obsidian/`** — the Shortcuts app's own iCloud
  container. This is where "Append to Text File" naturally writes. On macOS
  it's at `~/Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/url2obsidian/`.
  **This is the default `inbox_dir` and what you should use.**
- **`iCloud Drive/url2obsidian/`** — top-level iCloud Drive folder. Works too
  but requires extra navigation in the Shortcut's file picker. On macOS at
  `~/Library/Mobile Documents/com~apple~CloudDocs/url2obsidian/`. If you
  prefer this, set `inbox_dir` in `config.toml` accordingly.

Double-check the filename spelling in the picker — `inbox.txt`, not `indbox.txt`.
A typo there silently sends URLs to a file the worker doesn't read.

### Launchd

```
cp packaging/com.mhattingpete.url2obsidian.plist.template \
   ~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist
# edit the plist to use your uv path and repo path
launchctl load ~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist
```

## Manual one-off

```
uv run url2obsidian clip https://some.article/url      # direct: fetch + clip
uv run url2obsidian enqueue https://some.article/url   # via inbox (test full flow)
uv run url2obsidian run-once                           # process the inbox now
```

## Audit trails

In `~/Library/Mobile Documents/com~apple~CloudDocs/url2obsidian/`:

- `inbox.txt` — pending URLs (Shortcut writes here)
- `processed.log` — successful clippings: `<iso>\t<url>\t<vault-path>`
- `failed.log` — failures: `<iso>\t<url>\t<reason>` (e.g. `fetch`, `http-404`, `extractor`, `empty`)
