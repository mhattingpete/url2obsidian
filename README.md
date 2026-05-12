# url2obsidian

Share a URL from your iPhone → it lands as a clipped markdown note in your
Obsidian vault within minutes.

```
iPhone Share Sheet → Raindrop.io (Inbox/Unclipped)
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
uv run url2obsidian configure
```

`configure` will prompt for a Raindrop personal access token (from
<https://app.raindrop.io/settings/integrations>), store it in your macOS
Keychain, and write a config template to `~/.config/url2obsidian/config.toml`.
Edit the template to point at your vault, then:

```
cp packaging/com.mhattingpete.url2obsidian.plist.template \
   ~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist
# edit the plist to use your uv path and repo path
launchctl load ~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist
```

## Manual one-off

```
uv run url2obsidian clip https://some.article/url
```

