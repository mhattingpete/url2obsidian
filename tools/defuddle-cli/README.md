# defuddle-cli

Pinned `defuddle` dependency. defuddle ships its own CLI binary
(`node_modules/.bin/defuddle`); the Python extractor invokes it directly:

```
defuddle parse <html-file> -j -m
```

This writes JSON with `{title, author, site, published, content, ...}` to stdout.

## Install

```
npm install
```
