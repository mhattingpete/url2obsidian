# url2obsidian Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Mac worker that polls a Raindrop.io inbox collection, fetches each URL, extracts a clean-markdown clipping via `defuddle` (the same engine the Obsidian Web Clipper uses), and writes it into the user's Obsidian vault — so that sharing a URL from the iPhone Share Sheet to Raindrop ends up as a clipped note in the vault within minutes.

**Architecture:** Python (uv) orchestrator with `typing.Protocol` seams for four adapters (`RaindropAPI`, `Fetcher`, `Extractor`, `VaultWriter`). The extractor is a thin subprocess wrapper around a tiny Node CLI that runs `defuddle`. Scheduled by macOS launchd every 5 minutes. Flat package layout; one composition root in `cli.py`. No domain/application/infrastructure folder split.

**Tech Stack:** Python 3.12 (uv, ruff, ty, pytest, respx, structlog), httpx, pydantic v2, Jinja2, Typer, keyring, Playwright (fallback only). Node 20 + `defuddle` for extraction. launchd for scheduling.

---

## Reference: spec

`docs/superpowers/specs/2026-05-12-url2obsidian-design.md` — read first if implementing this plan in a fresh session.

## File Structure

```
url2obsidian/
├── pyproject.toml                            # uv-managed Python project
├── .python-version                            # 3.12
├── .gitignore
├── README.md                                  # install + setup steps
├── src/
│   └── url2obsidian/
│       ├── __init__.py
│       ├── models.py                          # Item, ItemMeta, Article, FetchResult dataclasses
│       ├── protocols.py                       # RaindropAPI, Fetcher, Extractor, VaultWriter
│       ├── config.py                          # pydantic model + TOML loader
│       ├── raindrop_client.py                 # httpx client implementing RaindropAPI
│       ├── fetcher.py                         # httpx GET + Playwright fallback (Fetcher)
│       ├── extractor.py                       # subprocess wrapper around defuddle-cli (Extractor)
│       ├── renderer.py                        # Jinja2 template -> markdown string
│       ├── vault.py                           # slug/collision/write/image (VaultWriter)
│       ├── worker.py                          # orchestrator: run_once(api, fetcher, extractor, vault)
│       └── cli.py                             # Typer CLI: configure | run-once | daemon | clip
├── tools/
│   └── defuddle-cli/
│       ├── package.json
│       └── index.js                           # stdin HTML -> stdout JSON
├── packaging/
│   └── com.mhattingpete.url2obsidian.plist.template
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── article-substack.html
│   │   ├── article-nyt-like.html
│   │   ├── readme-github.html
│   │   ├── spa-skeleton.html
│   │   ├── page-404.html
│   │   └── raindrop-list.json
│   ├── fakes.py                               # FakeRaindropAPI, FakeFetcher, etc.
│   ├── test_config.py
│   ├── test_vault.py
│   ├── test_renderer.py
│   ├── test_extractor.py                      # invokes real defuddle-cli
│   ├── test_fetcher.py                        # respx-mocked
│   ├── test_raindrop_client.py                # respx-mocked
│   └── test_worker.py                         # uses fakes
└── .github/
    └── workflows/
        └── ci.yml
```

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `src/url2obsidian/__init__.py`
- Create: `tests/conftest.py`
- Create: `README.md`

- [ ] **Step 1: Pin Python version**

Create `.python-version`:

```
3.12
```

- [ ] **Step 2: Write `pyproject.toml`**

Create `pyproject.toml`:

```toml
[project]
name = "url2obsidian"
version = "0.1.0"
description = "Share URLs from iPhone to Obsidian via Raindrop.io inbox"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "jinja2>=3.1",
    "typer>=0.12",
    "keyring>=25",
    "playwright>=1.45",
    "structlog>=24",
    "pyobjc-framework-Cocoa>=10; platform_system == 'Darwin'",
]

[project.scripts]
url2obsidian = "url2obsidian.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/url2obsidian"]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "ruff>=0.6",
    "ty>=0.0.1a0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: Write `.gitignore`**

Create `.gitignore`:

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
node_modules/
.coverage
htmlcov/
```

- [ ] **Step 4: Package init**

Create `src/url2obsidian/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Empty conftest**

Create `tests/conftest.py`:

```python
```

- [ ] **Step 6: Bare README**

Create `README.md`:

```markdown
# url2obsidian

Share URLs from iPhone -> Raindrop.io -> auto-clipped into your Obsidian vault.

See `docs/superpowers/specs/2026-05-12-url2obsidian-design.md` for the design.

## Setup

1. `uv sync`
2. `cd tools/defuddle-cli && npm install && cd ../..`
3. `playwright install chromium`
4. `uv run url2obsidian configure`
5. See `packaging/` for the launchd install instructions printed by `configure`.
```

- [ ] **Step 7: Verify environment builds**

Run: `uv sync`
Expected: exits 0; creates `.venv/`; `uv.lock` is written.

Run: `uv run python -c "import url2obsidian; print(url2obsidian.__version__)"`
Expected: prints `0.1.0`.

Run: `uv run pytest`
Expected: `no tests ran` (exit 0 or 5 — both acceptable here).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .python-version .gitignore src/url2obsidian/__init__.py tests/conftest.py README.md uv.lock
git commit -m "feat: scaffold url2obsidian python project"
```

---

## Task 2: Data models

**Files:**
- Create: `src/url2obsidian/models.py`
- Create: `tests/test_models.py`

These are the data types passed across protocol boundaries. Plain `dataclass`es (frozen) — no I/O, no behavior.

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
from datetime import datetime, timezone

from url2obsidian.models import Article, FetchResult, Item, ItemMeta


def test_item_is_frozen():
    item = Item(
        id=1,
        url="https://example.com/a",
        title="A",
        excerpt="ex",
        tags=("from-phone",),
        created=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )
    try:
        item.id = 2  # type: ignore[misc]
    except Exception as e:
        assert "frozen" in str(e).lower() or "cannot assign" in str(e).lower()
    else:
        raise AssertionError("Item should be frozen")


def test_item_meta_derives_from_item():
    item = Item(
        id=42,
        url="https://example.com/x",
        title="raw title",
        excerpt="",
        tags=("from-phone",),
        created=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )
    meta = ItemMeta.from_item(item)
    assert meta.raindrop_id == 42
    assert meta.source_url == "https://example.com/x"
    assert "from-phone" in meta.tags


def test_article_has_required_fields():
    a = Article(
        title="T",
        byline="B",
        content_markdown="# hi",
        published=None,
        site_name="example.com",
    )
    assert a.title == "T"
    assert a.content_markdown.startswith("# hi")


def test_fetch_result_carries_html_and_method():
    fr = FetchResult(url="https://x", html="<html></html>", method="httpx", status=200)
    assert fr.method in {"httpx", "playwright"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: collection error / `ImportError: cannot import name 'Article'`.

- [ ] **Step 3: Implement models**

Create `src/url2obsidian/models.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class Item:
    id: int
    url: str
    title: str
    excerpt: str
    tags: tuple[str, ...]
    created: datetime


@dataclass(frozen=True, slots=True)
class ItemMeta:
    raindrop_id: int
    source_url: str
    raindrop_title: str
    raindrop_excerpt: str
    tags: tuple[str, ...]
    created: datetime

    @classmethod
    def from_item(cls, item: Item) -> "ItemMeta":
        return cls(
            raindrop_id=item.id,
            source_url=item.url,
            raindrop_title=item.title,
            raindrop_excerpt=item.excerpt,
            tags=item.tags,
            created=item.created,
        )


@dataclass(frozen=True, slots=True)
class Article:
    title: str
    byline: str
    content_markdown: str
    published: datetime | None
    site_name: str
    images: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    html: str
    method: Literal["httpx", "playwright"]
    status: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/url2obsidian/models.py tests/test_models.py
git commit -m "feat(models): add Item, ItemMeta, Article, FetchResult dataclasses"
```

---

## Task 3: Protocols

**Files:**
- Create: `src/url2obsidian/protocols.py`
- Create: `tests/test_protocols.py`

These declare the four seams. The test just verifies they exist with the right signatures via `runtime_checkable`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_protocols.py`:

```python
from collections.abc import Iterable
from pathlib import Path

from url2obsidian.models import Article, FetchResult, Item, ItemMeta
from url2obsidian.protocols import Extractor, Fetcher, RaindropAPI, VaultWriter


class _RaindropImpl:
    def list_unclipped(self) -> Iterable[Item]:
        return []

    def mark_clipped(self, item_id: int, tag: str) -> None:
        pass

    def mark_failed(self, item_id: int, reason: str) -> None:
        pass


class _FetcherImpl:
    def fetch(self, url: str) -> FetchResult:
        return FetchResult(url=url, html="", method="httpx", status=200)


class _ExtractorImpl:
    def extract(self, html: str, url: str) -> Article:
        return Article(title="", byline="", content_markdown="", published=None, site_name="")


class _VaultImpl:
    def write(self, article: Article, meta: ItemMeta) -> Path:
        return Path("/tmp/x.md")


def test_implementations_satisfy_protocols():
    assert isinstance(_RaindropImpl(), RaindropAPI)
    assert isinstance(_FetcherImpl(), Fetcher)
    assert isinstance(_ExtractorImpl(), Extractor)
    assert isinstance(_VaultImpl(), VaultWriter)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_protocols.py -v`
Expected: `ImportError: cannot import name 'Extractor'`.

- [ ] **Step 3: Implement protocols**

Create `src/url2obsidian/protocols.py`:

```python
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from url2obsidian.models import Article, FetchResult, Item, ItemMeta


@runtime_checkable
class RaindropAPI(Protocol):
    def list_unclipped(self) -> Iterable[Item]: ...
    def mark_clipped(self, item_id: int, tag: str) -> None: ...
    def mark_failed(self, item_id: int, reason: str) -> None: ...


@runtime_checkable
class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchResult: ...


@runtime_checkable
class Extractor(Protocol):
    def extract(self, html: str, url: str) -> Article: ...


@runtime_checkable
class VaultWriter(Protocol):
    def write(self, article: Article, meta: ItemMeta) -> Path: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_protocols.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/url2obsidian/protocols.py tests/test_protocols.py
git commit -m "feat(protocols): declare RaindropAPI, Fetcher, Extractor, VaultWriter seams"
```

---

## Task 4: Config

**Files:**
- Create: `src/url2obsidian/config.py`
- Create: `tests/test_config.py`

Pydantic settings model + TOML loader. Loads from `~/.config/url2obsidian/config.toml`, with overrides via env vars (handy for tests).

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import tomllib
from pathlib import Path

import pytest

from url2obsidian.config import Config, load_config


def test_load_config_from_path(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        'vault_path = "/tmp/vault"\n'
        'clippings_subdir = "Clippings"\n'
        'inbox_collection = "Inbox/Unclipped"\n'
        'clipped_collection = "Inbox/Clipped"\n'
        'failed_collection = "Inbox/Failed"\n'
        "poll_interval_seconds = 300\n"
        "download_images = true\n"
        "notification_on_error = true\n"
    )
    cfg = load_config(cfg_file)
    assert isinstance(cfg, Config)
    assert cfg.vault_path == Path("/tmp/vault")
    assert cfg.poll_interval_seconds == 300
    assert cfg.download_images is True


def test_load_config_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "absent.toml")


def test_load_config_invalid_toml(tmp_path: Path):
    cfg_file = tmp_path / "bad.toml"
    cfg_file.write_text("not = valid = toml")
    with pytest.raises(tomllib.TOMLDecodeError):
        load_config(cfg_file)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: `ImportError: cannot import name 'Config'`.

- [ ] **Step 3: Implement config**

Create `src/url2obsidian/config.py`:

```python
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "url2obsidian" / "config.toml"


class Config(BaseModel):
    vault_path: Path
    clippings_subdir: str = "Clippings"
    inbox_collection: str = "Inbox/Unclipped"
    clipped_collection: str = "Inbox/Clipped"
    failed_collection: str = "Inbox/Failed"
    poll_interval_seconds: int = Field(default=300, ge=60)
    download_images: bool = True
    notification_on_error: bool = True


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = tomllib.loads(path.read_text())
    return Config(**data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/url2obsidian/config.py tests/test_config.py
git commit -m "feat(config): pydantic Config model with TOML loader"
```

---

## Task 5: Vault writer

**Files:**
- Create: `src/url2obsidian/vault.py`
- Create: `tests/test_vault.py`

Writes a markdown file into `<vault>/Clippings/<slug>.md`. Handles slug generation, collision suffixes, and (optional) image download/rewrite. Pure I/O — takes already-rendered markdown.

- [ ] **Step 1: Write the failing test**

Create `tests/test_vault.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest

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
    writer = FileVaultWriter(vault_path=tmp_path, clippings_subdir="Clippings", download_images=False)
    path = writer.write(_article("My Post"), _meta())
    assert path == tmp_path / "Clippings" / "my-post.md"
    assert path.exists()
    assert "# Hello" in path.read_text()


def test_write_collision_appends_suffix(tmp_path: Path):
    writer = FileVaultWriter(vault_path=tmp_path, clippings_subdir="Clippings", download_images=False)
    p1 = writer.write(_article("Same Title"), _meta(rid=1))
    p2 = writer.write(_article("Same Title"), _meta(rid=2))
    p3 = writer.write(_article("Same Title"), _meta(rid=3))
    assert p1.name == "same-title.md"
    assert p2.name == "same-title-2.md"
    assert p3.name == "same-title-3.md"


def test_write_collision_gives_up_after_ten(tmp_path: Path):
    writer = FileVaultWriter(vault_path=tmp_path, clippings_subdir="Clippings", download_images=False)
    for i in range(10):
        writer.write(_article("Dup"), _meta(rid=i))
    with pytest.raises(RuntimeError, match="naming"):
        writer.write(_article("Dup"), _meta(rid=99))
```

NOTE: this task does NOT yet test image download. Image rewriting is added in Task 5b below.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vault.py -v`
Expected: `ImportError: cannot import name 'slugify'`.

- [ ] **Step 3: Implement vault writer (no images yet)**

Create `src/url2obsidian/vault.py`:

```python
import re
import unicodedata
import uuid
from pathlib import Path

from url2obsidian.models import Article, ItemMeta

_MAX_SUFFIX = 10


def slugify(text: str) -> str:
    if not text or not text.strip():
        return f"untitled-{uuid.uuid4().hex[:8]}"
    norm = unicodedata.normalize("NFKD", text)
    ascii_only = norm.encode("ascii", "ignore").decode("ascii")
    lower = ascii_only.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lower).strip("-")
    return cleaned or f"untitled-{uuid.uuid4().hex[:8]}"


class FileVaultWriter:
    def __init__(
        self,
        vault_path: Path,
        clippings_subdir: str = "Clippings",
        download_images: bool = True,
    ) -> None:
        self._vault = vault_path
        self._subdir = clippings_subdir
        self._download_images = download_images

    def write(self, article: Article, meta: ItemMeta) -> Path:
        target_dir = self._vault / self._subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        base = slugify(article.title)
        path = self._resolve_path(target_dir, base)
        # NOTE: this method writes article.content_markdown as-is.
        # Frontmatter is the renderer's job; vault.write expects the *final*
        # markdown string. We'll wire renderer + vault together in worker.py.
        path.write_text(article.content_markdown)
        return path

    @staticmethod
    def _resolve_path(target_dir: Path, base: str) -> Path:
        candidate = target_dir / f"{base}.md"
        if not candidate.exists():
            return candidate
        for n in range(2, _MAX_SUFFIX + 1):
            candidate = target_dir / f"{base}-{n}.md"
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"naming: too many collisions for slug {base!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_vault.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/url2obsidian/vault.py tests/test_vault.py
git commit -m "feat(vault): FileVaultWriter with slug + collision handling"
```

---

## Task 5b: Vault image download

**Files:**
- Modify: `src/url2obsidian/vault.py`
- Modify: `tests/test_vault.py`

Adds image-download behavior to `FileVaultWriter`. When `download_images=True`, walk the markdown for `![alt](url)` patterns, download to `<vault>/Clippings/_assets/<slug>/<filename>`, and rewrite the markdown to relative paths. Failures are non-fatal: keep the remote URL.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_vault.py`:

```python
import httpx
import respx


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
        writer = FileVaultWriter(vault_path=tmp_path, clippings_subdir="Clippings", download_images=True)
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
        respx.get("https://img.example.com/missing.png").mock(return_value=httpx.Response(404))
        writer = FileVaultWriter(vault_path=tmp_path, clippings_subdir="Clippings", download_images=True)
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
    writer = FileVaultWriter(vault_path=tmp_path, clippings_subdir="Clippings", download_images=False)
    path = writer.write(article, _meta())
    assert "https://img.example.com/p.png" in path.read_text()
    assert not (tmp_path / "Clippings" / "_assets").exists()
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest tests/test_vault.py::test_write_downloads_images_when_enabled -v`
Expected: AssertionError — image URL still in file.

- [ ] **Step 3: Implement image download in `FileVaultWriter`**

Replace the body of `FileVaultWriter` in `src/url2obsidian/vault.py` with:

```python
import re
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from url2obsidian.models import Article, ItemMeta

_MAX_SUFFIX = 10
_IMG_PATTERN = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>https?://[^)\s]+)\)")


def slugify(text: str) -> str:
    if not text or not text.strip():
        return f"untitled-{uuid.uuid4().hex[:8]}"
    norm = unicodedata.normalize("NFKD", text)
    ascii_only = norm.encode("ascii", "ignore").decode("ascii")
    lower = ascii_only.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lower).strip("-")
    return cleaned or f"untitled-{uuid.uuid4().hex[:8]}"


class FileVaultWriter:
    def __init__(
        self,
        vault_path: Path,
        clippings_subdir: str = "Clippings",
        download_images: bool = True,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._vault = vault_path
        self._subdir = clippings_subdir
        self._download_images = download_images
        self._http = http_client or httpx.Client(timeout=15.0, follow_redirects=True)

    def write(self, article: Article, meta: ItemMeta) -> Path:
        target_dir = self._vault / self._subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        base = slugify(article.title)
        path = self._resolve_path(target_dir, base)
        markdown = article.content_markdown
        if self._download_images:
            markdown = self._download_and_rewrite(markdown, target_dir, base)
        path.write_text(markdown)
        return path

    def _download_and_rewrite(self, markdown: str, target_dir: Path, slug: str) -> str:
        assets_dir = target_dir / "_assets" / slug

        def replace(match: re.Match[str]) -> str:
            url = match.group("url")
            alt = match.group("alt")
            filename = self._filename_for(url)
            if not filename:
                return match.group(0)
            local = assets_dir / filename
            try:
                resp = self._http.get(url)
                resp.raise_for_status()
                assets_dir.mkdir(parents=True, exist_ok=True)
                local.write_bytes(resp.content)
            except (httpx.HTTPError, OSError):
                return match.group(0)
            rel = f"_assets/{slug}/{filename}"
            return f"![{alt}]({rel})"

        return _IMG_PATTERN.sub(replace, markdown)

    @staticmethod
    def _filename_for(url: str) -> str:
        path = urlparse(url).path
        name = path.rsplit("/", 1)[-1] if "/" in path else path
        return name if name else ""

    @staticmethod
    def _resolve_path(target_dir: Path, base: str) -> Path:
        candidate = target_dir / f"{base}.md"
        if not candidate.exists():
            return candidate
        for n in range(2, _MAX_SUFFIX + 1):
            candidate = target_dir / f"{base}-{n}.md"
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"naming: too many collisions for slug {base!r}")
```

- [ ] **Step 4: Run all vault tests**

Run: `uv run pytest tests/test_vault.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/url2obsidian/vault.py tests/test_vault.py
git commit -m "feat(vault): download images locally and rewrite markdown refs"
```

---

## Task 6: Renderer

**Files:**
- Create: `src/url2obsidian/renderer.py`
- Create: `tests/test_renderer.py`
- Create: `tests/fixtures/expected_clipping.md`

Pure function: takes an `Article` + `ItemMeta`, returns the final markdown string (frontmatter + body). Uses Jinja2 from a template embedded in the module.

- [ ] **Step 1: Write golden file**

Create `tests/fixtures/expected_clipping.md`:

```markdown
---
title: "Hello World"
source: "https://example.com/post"
author: "Jane Doe"
published: "2026-04-01"
site: "example.com"
clipped: "2026-05-12T10:00:00+00:00"
raindrop_id: 42
tags: [clippings, from-phone]
---

# Hello

Body.
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_renderer.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from url2obsidian.models import Article, ItemMeta
from url2obsidian.renderer import render

FIXTURES = Path(__file__).parent / "fixtures"


def test_render_matches_golden(monkeypatch):
    article = Article(
        title="Hello World",
        byline="Jane Doe",
        content_markdown="# Hello\n\nBody.",
        published=datetime(2026, 4, 1, tzinfo=timezone.utc),
        site_name="example.com",
    )
    meta = ItemMeta(
        raindrop_id=42,
        source_url="https://example.com/post",
        raindrop_title="Hello World",
        raindrop_excerpt="",
        tags=("from-phone",),
        created=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )
    fixed_clipped_at = datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)
    rendered = render(article, meta, clipped_at=fixed_clipped_at)
    expected = (FIXTURES / "expected_clipping.md").read_text()
    assert rendered == expected


def test_render_handles_missing_published():
    article = Article(
        title="No Date",
        byline="",
        content_markdown="Body",
        published=None,
        site_name="example.com",
    )
    meta = ItemMeta(
        raindrop_id=1,
        source_url="https://x",
        raindrop_title="No Date",
        raindrop_excerpt="",
        tags=(),
        created=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )
    out = render(article, meta, clipped_at=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc))
    assert 'published: ""' in out or "published:" not in out
    assert "Body" in out
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_renderer.py -v`
Expected: `ImportError: cannot import name 'render'`.

- [ ] **Step 4: Implement renderer**

Create `src/url2obsidian/renderer.py`:

```python
from datetime import datetime

from jinja2 import Environment, StrictUndefined

from url2obsidian.models import Article, ItemMeta

_TEMPLATE = """\
---
title: "{{ title }}"
source: "{{ source }}"
author: "{{ author }}"
published: "{{ published }}"
site: "{{ site }}"
clipped: "{{ clipped }}"
raindrop_id: {{ raindrop_id }}
tags: [{{ tags }}]
---

{{ body }}
"""


def render(article: Article, meta: ItemMeta, clipped_at: datetime) -> str:
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    template = env.from_string(_TEMPLATE)
    tags = ["clippings", *meta.tags]
    return template.render(
        title=_escape(article.title),
        source=meta.source_url,
        author=_escape(article.byline),
        published=_iso_date(article.published),
        site=_escape(article.site_name),
        clipped=clipped_at.isoformat(),
        raindrop_id=meta.raindrop_id,
        tags=", ".join(tags),
        body=article.content_markdown,
    )


def _escape(value: str) -> str:
    return value.replace('"', '\\"')


def _iso_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.date().isoformat()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_renderer.py -v`
Expected: 2 passed.

If `test_render_matches_golden` fails on whitespace, view the diff: `diff <(uv run python -c "...") tests/fixtures/expected_clipping.md`. Adjust the template or golden file so they match exactly. Whitespace must be byte-identical.

- [ ] **Step 6: Commit**

```bash
git add src/url2obsidian/renderer.py tests/test_renderer.py tests/fixtures/expected_clipping.md
git commit -m "feat(renderer): Jinja2 template with frontmatter + body"
```

---

## Task 7: Defuddle CLI (Node sidecar)

**Files:**
- Create: `tools/defuddle-cli/package.json`
- Create: `tools/defuddle-cli/index.js`
- Create: `tools/defuddle-cli/README.md`

A 30-line Node CLI that reads `{html, url}` JSON from stdin, runs `defuddle`, and emits `{title, byline, content_markdown, published, site_name}` JSON on stdout. This is the only Node code in the project.

> **IMPORTANT:** The exact `defuddle` API may change between versions. **Before writing `index.js`, read `https://github.com/kepano/defuddle#readme`** for the current API. The skeleton below shows the I/O contract; adapt the body to defuddle's actual signature. The Python wrapper (Task 8) tests the I/O contract, not defuddle internals, so the contract here is what matters.

- [ ] **Step 1: `package.json`**

Create `tools/defuddle-cli/package.json`:

```json
{
  "name": "defuddle-cli",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "bin": "./index.js",
  "dependencies": {
    "defuddle": "^0.3.0",
    "jsdom": "^24.0.0"
  }
}
```

> If `defuddle` is on a different version, run `npm view defuddle version` and update the `^` constraint to the current major.

- [ ] **Step 2: Install dependencies**

Run: `cd tools/defuddle-cli && npm install`
Expected: creates `node_modules/`, writes `package-lock.json`. Exit 0.

- [ ] **Step 3: Write `index.js`**

Read defuddle's README. Then create `tools/defuddle-cli/index.js`:

```javascript
#!/usr/bin/env node
import { Defuddle } from "defuddle";
import { JSDOM } from "jsdom";

async function main() {
  const raw = await readAll(process.stdin);
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (e) {
    fail("invalid-stdin-json", e);
  }
  const { html, url } = payload;
  if (typeof html !== "string" || typeof url !== "string") {
    fail("missing-html-or-url");
  }

  let result;
  try {
    const dom = new JSDOM(html, { url });
    // NOTE: confirm Defuddle's constructor + .parse() shape against the
    // current README; adjust if the API has changed.
    const defuddle = new Defuddle(dom.window.document, { url, markdown: true });
    result = defuddle.parse();
  } catch (e) {
    fail("defuddle-error", e);
  }

  const out = {
    title: result.title || "",
    byline: result.author || result.byline || "",
    content_markdown: result.content || "",
    published: result.published || null,
    site_name: result.site || "",
  };
  process.stdout.write(JSON.stringify(out));
}

function readAll(stream) {
  return new Promise((resolve, reject) => {
    let data = "";
    stream.setEncoding("utf8");
    stream.on("data", (c) => (data += c));
    stream.on("end", () => resolve(data));
    stream.on("error", reject);
  });
}

function fail(kind, err) {
  process.stderr.write(JSON.stringify({ error: kind, detail: err?.message || String(err) }));
  process.exit(1);
}

main().catch((e) => fail("uncaught", e));
```

- [ ] **Step 4: Smoke-test the CLI manually**

Run:

```bash
echo '{"html":"<html><body><h1>Hi</h1><p>Body.</p></body></html>","url":"https://example.com"}' \
  | node tools/defuddle-cli/index.js
```

Expected: JSON on stdout with non-empty `content_markdown`. If defuddle's API differs from the skeleton, this is where you'll see it — adapt `index.js` until the smoke output is valid JSON.

- [ ] **Step 5: `tools/defuddle-cli/README.md`**

Create:

```markdown
# defuddle-cli

Stdin/stdout wrapper around defuddle, called from the Python worker.

## Install

```
npm install
```

## Use

```
echo '{"html":"...","url":"..."}' | node index.js
```

Output: JSON `{title, byline, content_markdown, published, site_name}`.
On error: exit 1 with `{error, detail}` on stderr.
```

- [ ] **Step 6: Commit**

```bash
git add tools/defuddle-cli/package.json tools/defuddle-cli/package-lock.json tools/defuddle-cli/index.js tools/defuddle-cli/README.md
git commit -m "feat(defuddle-cli): node stdin/stdout wrapper around defuddle"
```

Note: add `tools/defuddle-cli/node_modules/` to `.gitignore` (already covered by the global `node_modules/` rule from Task 1).

---

## Task 8: Extractor (Python wrapper around defuddle-cli)

**Files:**
- Create: `src/url2obsidian/extractor.py`
- Create: `tests/test_extractor.py`
- Create: `tests/fixtures/article-simple.html`

Calls the Node CLI via `subprocess`. Test calls the **real** binary with a fixture — no mock.

- [ ] **Step 1: Provide a fixture HTML**

Create `tests/fixtures/article-simple.html`:

```html
<!doctype html>
<html>
  <head><title>Simple Test Article</title></head>
  <body>
    <article>
      <h1>Simple Test Article</h1>
      <p class="byline">By Test Author</p>
      <p>This is the first paragraph of a simple test article used by the
         extractor test. It has enough content for defuddle to extract.</p>
      <p>This is a second paragraph. Lorem ipsum dolor sit amet, consectetur
         adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore
         magna aliqua.</p>
    </article>
  </body>
</html>
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_extractor.py`:

```python
import shutil
from pathlib import Path

import pytest

from url2obsidian.extractor import DefuddleExtractor, ExtractorError

FIXTURES = Path(__file__).parent / "fixtures"
CLI_PATH = Path(__file__).resolve().parents[1] / "tools" / "defuddle-cli" / "index.js"


pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not CLI_PATH.exists(),
    reason="node and tools/defuddle-cli/index.js required",
)


def test_extract_simple_article():
    html = (FIXTURES / "article-simple.html").read_text()
    extractor = DefuddleExtractor(cli_path=CLI_PATH)
    article = extractor.extract(html, "https://example.com/post")
    assert article.title
    assert "Simple Test Article" in article.title
    assert article.content_markdown.strip()
    assert len(article.content_markdown) > 100


def test_extract_invalid_html_raises():
    extractor = DefuddleExtractor(cli_path=CLI_PATH)
    with pytest.raises(ExtractorError):
        extractor.extract("", "https://example.com/post")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_extractor.py -v`
Expected: `ImportError: cannot import name 'DefuddleExtractor'`.

- [ ] **Step 4: Implement extractor**

Create `src/url2obsidian/extractor.py`:

```python
import json
import subprocess
from datetime import datetime
from pathlib import Path

from url2obsidian.models import Article


class ExtractorError(RuntimeError):
    pass


class DefuddleExtractor:
    def __init__(self, cli_path: Path, node_bin: str = "node", timeout_s: float = 30.0) -> None:
        self._cli = cli_path
        self._node = node_bin
        self._timeout = timeout_s

    def extract(self, html: str, url: str) -> Article:
        if not html:
            raise ExtractorError("empty html")
        payload = json.dumps({"html": html, "url": url})
        try:
            proc = subprocess.run(
                [self._node, str(self._cli)],
                input=payload,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise ExtractorError(f"defuddle-cli timeout after {self._timeout}s") from e

        if proc.returncode != 0:
            raise ExtractorError(f"defuddle-cli exit {proc.returncode}: {proc.stderr.strip()}")

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ExtractorError(f"defuddle-cli produced invalid JSON: {e}") from e

        return Article(
            title=data.get("title", "") or "",
            byline=data.get("byline", "") or "",
            content_markdown=data.get("content_markdown", "") or "",
            published=_parse_iso(data.get("published")),
            site_name=data.get("site_name", "") or "",
        )


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_extractor.py -v`
Expected: 2 passed. (If they don't, run the CLI manually as in Task 7 Step 4 to confirm it's producing the right JSON shape.)

- [ ] **Step 6: Commit**

```bash
git add src/url2obsidian/extractor.py tests/test_extractor.py tests/fixtures/article-simple.html
git commit -m "feat(extractor): subprocess wrapper around defuddle-cli"
```

---

## Task 9: Fetcher (httpx + Playwright fallback)

**Files:**
- Create: `src/url2obsidian/fetcher.py`
- Create: `tests/test_fetcher.py`

Two-tier fetch. Tier 1: httpx GET. Tier 2 (fallback): Playwright headless Chromium loads the page until `networkidle`, returns rendered HTML. Trigger for tier 2: tier 1 returned non-HTML, or returned HTML shorter than `min_html_bytes` (default 2048), or raised a network error.

Tests use `respx` for tier 1 and a **fake** `BrowserFetcher` to assert the trigger condition (Playwright itself is integration-tested manually).

- [ ] **Step 1: Write the failing test**

Create `tests/test_fetcher.py`:

```python
from typing import Callable

import httpx
import pytest
import respx

from url2obsidian.fetcher import BrowserFetch, TwoTierFetcher
from url2obsidian.models import FetchResult


class FakeBrowser:
    def __init__(self, html: str = "<html><body>browser</body></html>") -> None:
        self.calls: list[str] = []
        self._html = html

    def fetch(self, url: str) -> FetchResult:
        self.calls.append(url)
        return FetchResult(url=url, html=self._html, method="playwright", status=200)


@respx.mock
def test_httpx_path_when_response_is_large_html():
    big_html = "<html><body>" + ("x" * 3000) + "</body></html>"
    respx.get("https://example.com/a").mock(
        return_value=httpx.Response(200, html=big_html)
    )
    browser = FakeBrowser()
    f = TwoTierFetcher(browser=browser, min_html_bytes=2048)
    r = f.fetch("https://example.com/a")
    assert r.method == "httpx"
    assert "xxx" in r.html
    assert browser.calls == []


@respx.mock
def test_fallback_when_response_is_too_small():
    respx.get("https://example.com/spa").mock(
        return_value=httpx.Response(200, html="<html><body>skel</body></html>")
    )
    browser = FakeBrowser(html="<html><body>fully rendered</body></html>")
    f = TwoTierFetcher(browser=browser, min_html_bytes=2048)
    r = f.fetch("https://example.com/spa")
    assert r.method == "playwright"
    assert "fully rendered" in r.html
    assert browser.calls == ["https://example.com/spa"]


@respx.mock
def test_fallback_on_network_error():
    respx.get("https://example.com/down").mock(side_effect=httpx.ConnectError("boom"))
    browser = FakeBrowser()
    f = TwoTierFetcher(browser=browser, min_html_bytes=2048)
    r = f.fetch("https://example.com/down")
    assert r.method == "playwright"


@respx.mock
def test_http_4xx_propagates_without_fallback():
    respx.get("https://example.com/dead").mock(return_value=httpx.Response(404))
    browser = FakeBrowser()
    f = TwoTierFetcher(browser=browser, min_html_bytes=2048)
    with pytest.raises(httpx.HTTPStatusError):
        f.fetch("https://example.com/dead")
    assert browser.calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fetcher.py -v`
Expected: `ImportError: cannot import name 'TwoTierFetcher'`.

- [ ] **Step 3: Implement fetcher**

Create `src/url2obsidian/fetcher.py`:

```python
from typing import Protocol

import httpx

from url2obsidian.models import FetchResult

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15 url2obsidian/0.1"
)


class BrowserFetch(Protocol):
    def fetch(self, url: str) -> FetchResult: ...


class TwoTierFetcher:
    def __init__(
        self,
        browser: BrowserFetch,
        min_html_bytes: int = 2048,
        timeout_s: float = 15.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._browser = browser
        self._min = min_html_bytes
        self._http = http_client or httpx.Client(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        )

    def fetch(self, url: str) -> FetchResult:
        try:
            resp = self._http.get(url)
        except httpx.HTTPError:
            return self._browser.fetch(url)

        if 400 <= resp.status_code < 500:
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        looks_like_html = "html" in content_type or "<html" in resp.text[:200].lower()
        if not looks_like_html or len(resp.text) < self._min:
            return self._browser.fetch(url)

        return FetchResult(url=url, html=resp.text, method="httpx", status=resp.status_code)


class PlaywrightBrowser:
    """Real browser fallback. Lazy-imports playwright so unit tests don't need it."""

    def __init__(self, timeout_s: float = 30.0) -> None:
        self._timeout = timeout_s

    def fetch(self, url: str) -> FetchResult:
        from playwright.sync_api import sync_playwright  # lazy

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                ctx = browser.new_context(user_agent=_UA)
                page = ctx.new_page()
                resp = page.goto(url, wait_until="networkidle", timeout=int(self._timeout * 1000))
                html = page.content()
                status = resp.status if resp else 0
            finally:
                browser.close()
        return FetchResult(url=url, html=html, method="playwright", status=status)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetcher.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/url2obsidian/fetcher.py tests/test_fetcher.py
git commit -m "feat(fetcher): two-tier httpx + Playwright fallback"
```

---

## Task 10: Raindrop client

**Files:**
- Create: `src/url2obsidian/raindrop_client.py`
- Create: `tests/test_raindrop_client.py`
- Create: `tests/fixtures/raindrop-list.json`

> **IMPORTANT:** Read the Raindrop API reference at `https://developer.raindrop.io/v1/raindrops` first. The token is a personal access token from `https://app.raindrop.io/settings/integrations`. Endpoints and JSON shapes below reflect the API at time of writing; verify against the live docs before coding. The Python interface (`list_unclipped`, `mark_clipped`, `mark_failed`) is what the rest of the system depends on — adapt the HTTP body to whatever the live API requires.

Approach: collections are identified by name in our config; the client resolves names to IDs at construction time (one `GET /collections`), then uses IDs for subsequent operations.

- [ ] **Step 1: Provide a fixture API response**

Create `tests/fixtures/raindrop-list.json`. After consulting the Raindrop docs, save **one real `GET /raindrops/<id>` response** here (you can curl it with your token against a test collection). It must contain at least 2 items so pagination test logic exercises. The structure typically looks like:

```json
{
  "result": true,
  "items": [
    {
      "_id": 111,
      "link": "https://example.com/a",
      "title": "A",
      "excerpt": "",
      "tags": ["from-phone"],
      "created": "2026-05-12T09:00:00.000Z"
    },
    {
      "_id": 112,
      "link": "https://example.com/b",
      "title": "B",
      "excerpt": "",
      "tags": [],
      "created": "2026-05-12T09:01:00.000Z"
    }
  ],
  "count": 2
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_raindrop_client.py`:

```python
import json
from pathlib import Path

import httpx
import pytest
import respx

from url2obsidian.raindrop_client import RaindropClient, RaindropError

FIXTURES = Path(__file__).parent / "fixtures"
RAINDROP_BASE = "https://api.raindrop.io/rest/v1"


def _collections_response(name_to_id: dict[str, int]) -> dict:
    return {
        "result": True,
        "items": [{"_id": cid, "title": name} for name, cid in name_to_id.items()],
    }


@respx.mock
def test_list_unclipped_returns_items_from_inbox_collection():
    respx.get(f"{RAINDROP_BASE}/collections").mock(
        return_value=httpx.Response(200, json=_collections_response({
            "Unclipped": 7001, "Clipped": 7002, "Failed": 7003,
        }))
    )
    items_payload = json.loads((FIXTURES / "raindrop-list.json").read_text())
    respx.get(f"{RAINDROP_BASE}/raindrops/7001").mock(
        return_value=httpx.Response(200, json=items_payload)
    )

    client = RaindropClient(
        token="t",
        inbox_collection="Unclipped",
        clipped_collection="Clipped",
        failed_collection="Failed",
    )
    items = list(client.list_unclipped())
    assert len(items) >= 2
    assert items[0].url.startswith("http")
    assert items[0].id > 0


@respx.mock
def test_mark_clipped_moves_item_to_clipped_collection():
    respx.get(f"{RAINDROP_BASE}/collections").mock(
        return_value=httpx.Response(200, json=_collections_response({
            "Unclipped": 7001, "Clipped": 7002, "Failed": 7003,
        }))
    )
    route = respx.put(f"{RAINDROP_BASE}/raindrop/123").mock(
        return_value=httpx.Response(200, json={"result": True})
    )
    client = RaindropClient(
        token="t",
        inbox_collection="Unclipped",
        clipped_collection="Clipped",
        failed_collection="Failed",
    )
    client.mark_clipped(item_id=123, tag="clipped-2026-05-12")
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["collection"]["$id"] == 7002
    assert "clipped-2026-05-12" in body["tags"]


@respx.mock
def test_unauthorized_raises():
    respx.get(f"{RAINDROP_BASE}/collections").mock(
        return_value=httpx.Response(401, json={"result": False, "errorMessage": "unauthorized"})
    )
    with pytest.raises(RaindropError, match="unauth"):
        RaindropClient(
            token="bad",
            inbox_collection="Unclipped",
            clipped_collection="Clipped",
            failed_collection="Failed",
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_raindrop_client.py -v`
Expected: `ImportError: cannot import name 'RaindropClient'`.

- [ ] **Step 4: Implement client**

Create `src/url2obsidian/raindrop_client.py`:

```python
from collections.abc import Iterable
from datetime import datetime

import httpx

from url2obsidian.models import Item

_BASE = "https://api.raindrop.io/rest/v1"
_PAGE_SIZE = 50


class RaindropError(RuntimeError):
    pass


class RaindropClient:
    def __init__(
        self,
        token: str,
        inbox_collection: str,
        clipped_collection: str,
        failed_collection: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._http = http_client or httpx.Client(
            base_url=_BASE,
            timeout=20.0,
            headers={"Authorization": f"Bearer {token}"},
        )
        self._inbox_name = inbox_collection
        self._clipped_name = clipped_collection
        self._failed_name = failed_collection
        names = self._resolve_collections()
        self._inbox_id = names[inbox_collection]
        self._clipped_id = names[clipped_collection]
        self._failed_id = names[failed_collection]

    def _resolve_collections(self) -> dict[str, int]:
        try:
            resp = self._http.get("/collections")
        except httpx.HTTPError as e:
            raise RaindropError(f"network error contacting raindrop: {e}") from e
        if resp.status_code in (401, 403):
            raise RaindropError("unauthorized: check your Raindrop token")
        resp.raise_for_status()
        data = resp.json()
        out: dict[str, int] = {}
        for item in data.get("items", []):
            out[item["title"]] = int(item["_id"])
        missing = [n for n in (self._inbox_name, self._clipped_name, self._failed_name) if n not in out]
        if missing:
            raise RaindropError(f"collections not found: {missing}")
        return out

    def list_unclipped(self) -> Iterable[Item]:
        page = 0
        while True:
            resp = self._http.get(
                f"/raindrops/{self._inbox_id}",
                params={"perpage": _PAGE_SIZE, "page": page},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return
            for raw in items:
                yield Item(
                    id=int(raw["_id"]),
                    url=raw["link"],
                    title=raw.get("title", ""),
                    excerpt=raw.get("excerpt", ""),
                    tags=tuple(raw.get("tags", [])),
                    created=_parse_iso(raw.get("created")),
                )
            if len(items) < _PAGE_SIZE:
                return
            page += 1

    def mark_clipped(self, item_id: int, tag: str) -> None:
        self._move(item_id, target_collection_id=self._clipped_id, extra_tag=tag)

    def mark_failed(self, item_id: int, reason: str) -> None:
        self._move(
            item_id,
            target_collection_id=self._failed_id,
            extra_tag=f"clip-error:{reason}",
        )

    def _move(self, item_id: int, target_collection_id: int, extra_tag: str) -> None:
        resp = self._http.put(
            f"/raindrop/{item_id}",
            json={
                "collection": {"$id": target_collection_id},
                "tags": [extra_tag],
            },
        )
        if resp.status_code in (401, 403):
            raise RaindropError("unauthorized: check your Raindrop token")
        resp.raise_for_status()


def _parse_iso(raw: str | None) -> datetime:
    if not raw:
        return datetime.fromtimestamp(0)
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_raindrop_client.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/url2obsidian/raindrop_client.py tests/test_raindrop_client.py tests/fixtures/raindrop-list.json
git commit -m "feat(raindrop): httpx client implementing RaindropAPI protocol"
```

---

## Task 11: Worker orchestrator

**Files:**
- Create: `src/url2obsidian/worker.py`
- Create: `tests/fakes.py`
- Create: `tests/test_worker.py`

The orchestrator: iterates `RaindropAPI.list_unclipped()`, runs fetch → extract → render → write → mark_clipped, with structured logging. Compose error handling per the spec.

- [ ] **Step 1: Test fakes**

Create `tests/fakes.py`:

```python
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from url2obsidian.models import Article, FetchResult, Item, ItemMeta


class FakeRaindrop:
    def __init__(self, items: list[Item]) -> None:
        self.items = items
        self.clipped: list[tuple[int, str]] = []
        self.failed: list[tuple[int, str]] = []

    def list_unclipped(self) -> Iterable[Item]:
        yield from self.items

    def mark_clipped(self, item_id: int, tag: str) -> None:
        self.clipped.append((item_id, tag))

    def mark_failed(self, item_id: int, reason: str) -> None:
        self.failed.append((item_id, reason))


class FakeFetcher:
    def __init__(self, mapping: dict[str, FetchResult | Exception]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.calls.append(url)
        v = self.mapping[url]
        if isinstance(v, Exception):
            raise v
        return v


class FakeExtractor:
    def __init__(self, mapping: dict[str, Article | Exception]) -> None:
        self.mapping = mapping

    def extract(self, html: str, url: str) -> Article:
        v = self.mapping[url]
        if isinstance(v, Exception):
            raise v
        return v


class FakeVault:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.written: list[Path] = []

    def write(self, article: Article, meta: ItemMeta) -> Path:
        target = self.tmp / f"{meta.raindrop_id}.md"
        target.write_text(article.content_markdown)
        self.written.append(target)
        return target


def make_item(rid: int, url: str = "https://example.com/x") -> Item:
    return Item(
        id=rid,
        url=url,
        title=f"item-{rid}",
        excerpt="",
        tags=("from-phone",),
        created=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )


def make_article(content: str = "hi") -> Article:
    return Article(
        title="t",
        byline="",
        content_markdown=content,
        published=None,
        site_name="example.com",
    )
```

- [ ] **Step 2: Worker tests**

Create `tests/test_worker.py`:

```python
from pathlib import Path

import httpx

from tests.fakes import FakeExtractor, FakeFetcher, FakeRaindrop, FakeVault, make_article, make_item
from url2obsidian.extractor import ExtractorError
from url2obsidian.models import FetchResult
from url2obsidian.worker import run_once


def _fetch_ok(url: str, html: str = "<html>body</html>") -> FetchResult:
    return FetchResult(url=url, html=html, method="httpx", status=200)


def test_happy_path_marks_clipped(tmp_path: Path):
    item = make_item(rid=1, url="https://example.com/a")
    api = FakeRaindrop([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    extractor = FakeExtractor({item.url: make_article("# hello")})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)

    assert len(api.clipped) == 1
    assert api.clipped[0][0] == 1
    assert api.clipped[0][1].startswith("clipped-")
    assert api.failed == []
    assert vault.written and vault.written[0].read_text() == "# hello"


def test_fetch_error_marks_failed(tmp_path: Path):
    item = make_item(rid=2, url="https://example.com/b")
    api = FakeRaindrop([item])
    fetcher = FakeFetcher({item.url: httpx.ConnectError("boom")})
    extractor = FakeExtractor({})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)

    assert api.clipped == []
    assert api.failed == [(2, "fetch")]


def test_http_4xx_marks_failed_with_code(tmp_path: Path):
    item = make_item(rid=3, url="https://example.com/c")
    api = FakeRaindrop([item])
    err = httpx.HTTPStatusError("404", request=httpx.Request("GET", item.url), response=httpx.Response(404))
    fetcher = FakeFetcher({item.url: err})
    extractor = FakeExtractor({})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)
    assert api.failed == [(3, "http-404")]


def test_extractor_error_marks_failed(tmp_path: Path):
    item = make_item(rid=4, url="https://example.com/d")
    api = FakeRaindrop([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    extractor = FakeExtractor({item.url: ExtractorError("bad html")})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)
    assert api.failed == [(4, "extractor")]


def test_empty_content_marks_failed(tmp_path: Path):
    item = make_item(rid=5, url="https://example.com/e")
    api = FakeRaindrop([item])
    fetcher = FakeFetcher({item.url: _fetch_ok(item.url)})
    extractor = FakeExtractor({item.url: make_article(content="")})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)
    assert api.failed == [(5, "empty")]


def test_one_item_failing_does_not_block_next(tmp_path: Path):
    item_a = make_item(rid=10, url="https://example.com/fail")
    item_b = make_item(rid=11, url="https://example.com/ok")
    api = FakeRaindrop([item_a, item_b])
    fetcher = FakeFetcher({
        item_a.url: httpx.ConnectError("boom"),
        item_b.url: _fetch_ok(item_b.url),
    })
    extractor = FakeExtractor({item_b.url: make_article("# ok")})
    vault = FakeVault(tmp_path)

    run_once(api, fetcher, extractor, vault)
    assert api.failed == [(10, "fetch")]
    assert [c[0] for c in api.clipped] == [11]
```

- [ ] **Step 3: Run worker tests to verify they fail**

Run: `uv run pytest tests/test_worker.py -v`
Expected: `ImportError: cannot import name 'run_once'`.

- [ ] **Step 4: Implement worker**

Create `src/url2obsidian/worker.py`:

```python
from datetime import date

import httpx
import structlog

from url2obsidian.extractor import ExtractorError
from url2obsidian.models import ItemMeta
from url2obsidian.protocols import Extractor, Fetcher, RaindropAPI, VaultWriter

log = structlog.get_logger("url2obsidian")

_MIN_CONTENT_CHARS = 200


def run_once(
    api: RaindropAPI,
    fetcher: Fetcher,
    extractor: Extractor,
    vault: VaultWriter,
) -> None:
    for item in api.list_unclipped():
        _process_one(item, api, fetcher, extractor, vault)


def _process_one(item, api, fetcher, extractor, vault) -> None:
    try:
        fetched = fetcher.fetch(item.url)
    except httpx.HTTPStatusError as e:
        reason = f"http-{e.response.status_code}"
        log.warning("fetch_http_error", id=item.id, url=item.url, status=e.response.status_code)
        api.mark_failed(item.id, reason)
        return
    except httpx.HTTPError:
        log.warning("fetch_error", id=item.id, url=item.url)
        api.mark_failed(item.id, "fetch")
        return

    try:
        article = extractor.extract(fetched.html, item.url)
    except ExtractorError:
        log.warning("extractor_error", id=item.id, url=item.url)
        api.mark_failed(item.id, "extractor")
        return

    if len(article.content_markdown.strip()) < _MIN_CONTENT_CHARS:
        log.warning("empty_content", id=item.id, url=item.url)
        api.mark_failed(item.id, "empty")
        return

    meta = ItemMeta.from_item(item)
    try:
        path = vault.write(article, meta)
    except Exception as e:
        log.warning("vault_error", id=item.id, url=item.url, error=str(e))
        api.mark_failed(item.id, "vault")
        return

    tag = f"clipped-{date.today().isoformat()}"
    api.mark_clipped(item.id, tag)
    log.info("clipped", id=item.id, url=item.url, path=str(path))
```

Note: the worker uses `_MIN_CONTENT_CHARS = 200`, lower than the test in Task 11's `test_empty_content_marks_failed` uses (empty string). The "200 chars" matches the spec's "<500 chars triggers playwright fallback then if still empty -> failed" — but that fallback is the fetcher's responsibility, not the worker's. The worker only sees the post-fallback content.

- [ ] **Step 5: Run worker tests to verify they pass**

Run: `uv run pytest tests/test_worker.py -v`
Expected: 6 passed.

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: all tests pass (modulo the extractor tests which require Node + the CLI installed).

- [ ] **Step 7: Commit**

```bash
git add src/url2obsidian/worker.py tests/fakes.py tests/test_worker.py
git commit -m "feat(worker): orchestrate fetch -> extract -> render -> vault -> mark"
```

---

## Task 12: CLI + composition root

**Files:**
- Create: `src/url2obsidian/cli.py`
- Modify: `src/url2obsidian/__init__.py` (no change needed, just confirm `__version__`)
- Modify: `README.md` (replace contents)

Wires everything together. Commands:
- `configure` — interactive: prompt for Raindrop token, store in keyring, write a template config.
- `run-once` — load config, build adapters, call `worker.run_once()`. Exits 0 on success even if some items failed (errors are per-item, not run-level).
- `daemon` — loop: `run-once`; sleep `poll_interval_seconds`; repeat. (For people who don't want launchd.)
- `clip <url>` — single-URL convenience: skip Raindrop, fetch+extract+render+write a single URL directly to the vault. Useful for manual end-to-end smoke testing.

Manual testing replaces unit tests here; the CLI is glue.

- [ ] **Step 1: Implement CLI**

Create `src/url2obsidian/cli.py`:

```python
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
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
    # Resolve tools/defuddle-cli/index.js relative to the repo root.
    # Allows running both from a uv-installed entrypoint and from a checkout.
    here = Path(__file__).resolve()
    for ancestor in [here.parent, *here.parents]:
        cand = ancestor / "tools" / "defuddle-cli" / "index.js"
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "tools/defuddle-cli/index.js not found. Run from the project checkout."
    )


def _build(config: Config) -> tuple[RaindropClient, TwoTierFetcher, DefuddleExtractor, FileVaultWriter]:
    token = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    if not token:
        typer.echo("No Raindrop token in keychain. Run `url2obsidian configure` first.", err=True)
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
        f"  cp packaging/com.mhattingpete.url2obsidian.plist.template "
        f"~/Library/LaunchAgents/com.mhattingpete.url2obsidian.plist"
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
        except Exception as e:  # never let the loop die from one bad run
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
        typer.echo(f"Extracted content too short ({len(article.content_markdown)} chars).", err=True)
        raise typer.Exit(1)

    meta = ItemMeta(
        raindrop_id=0,
        source_url=url,
        raindrop_title=article.title,
        raindrop_excerpt="",
        tags=("manual",),
        created=datetime.now(timezone.utc),
    )
    final = render(article, meta, clipped_at=datetime.now(timezone.utc))
    article_with_frontmatter = type(article)(
        title=article.title,
        byline=article.byline,
        content_markdown=final,
        published=article.published,
        site_name=article.site_name,
    )
    path = vault.write(article_with_frontmatter, meta)
    typer.echo(f"Wrote {path}")


_DEFAULT_CONFIG_TEMPLATE = '''\
vault_path          = "/Users/CHANGEME/Obsidian/MainVault"
clippings_subdir    = "Clippings"
inbox_collection    = "Unclipped"
clipped_collection  = "Clipped"
failed_collection   = "Failed"
poll_interval_seconds = 300
download_images       = true
notification_on_error = true
'''


if __name__ == "__main__":
    app()
```

Note: the `clip` command renders the frontmatter+body into `content_markdown` before calling `vault.write` so the file contains the full clipping. The Worker does this implicitly via the same render+vault path — wire this consistency in the next step.

- [ ] **Step 2: Wire render into worker too**

Modify `src/url2obsidian/worker.py`: replace the section starting at `meta = ItemMeta.from_item(item)` with:

```python
    from datetime import datetime, timezone
    from url2obsidian.renderer import render

    meta = ItemMeta.from_item(item)
    clipped_at = datetime.now(timezone.utc)
    final_md = render(article, meta, clipped_at=clipped_at)
    article_with_fm = type(article)(
        title=article.title,
        byline=article.byline,
        content_markdown=final_md,
        published=article.published,
        site_name=article.site_name,
    )
    try:
        path = vault.write(article_with_fm, meta)
    except Exception as e:
        log.warning("vault_error", id=item.id, url=item.url, error=str(e))
        api.mark_failed(item.id, "vault")
        return

    tag = f"clipped-{date.today().isoformat()}"
    api.mark_clipped(item.id, tag)
    log.info("clipped", id=item.id, url=item.url, path=str(path))
```

Then re-run worker tests: `uv run pytest tests/test_worker.py -v` — they should all still pass because `FakeVault` just checks `content_markdown`, which now contains the rendered output. If the assertion `vault.written[0].read_text() == "# hello"` in `test_happy_path_marks_clipped` fails because content now includes frontmatter, **change that assertion** to:

```python
assert "# hello" in vault.written[0].read_text()
assert "raindrop_id: 1" in vault.written[0].read_text()
```

- [ ] **Step 3: Manual smoke test**

Pre-req: `uv sync && cd tools/defuddle-cli && npm install && cd ../..` and `playwright install chromium`.

Run: `uv run url2obsidian clip https://en.wikipedia.org/wiki/Markdown`
Expected: prints `Wrote /…/Clippings/markdown.md`. Open the file; verify it has YAML frontmatter, the title, and a substantial body.

- [ ] **Step 4: Replace README**

Overwrite `README.md` with:

```markdown
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
https://app.raindrop.io/settings/integrations), store it in your macOS
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

## Design

See `docs/superpowers/specs/2026-05-12-url2obsidian-design.md`.
```

- [ ] **Step 5: Commit**

```bash
git add src/url2obsidian/cli.py src/url2obsidian/worker.py tests/test_worker.py README.md
git commit -m "feat(cli): configure | run-once | daemon | clip with composition root"
```

---

## Task 13: launchd plist template

**Files:**
- Create: `packaging/com.mhattingpete.url2obsidian.plist.template`

Static template. User copies it, edits the two `CHANGEME` paths, loads it.

- [ ] **Step 1: Write template**

Create `packaging/com.mhattingpete.url2obsidian.plist.template`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mhattingpete.url2obsidian</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/CHANGEME/.local/bin/uv</string>
        <string>run</string>
        <string>--directory</string>
        <string>/Users/CHANGEME/Documents/Repos/url2obsidian</string>
        <string>url2obsidian</string>
        <string>run-once</string>
    </array>

    <key>StartInterval</key>
    <integer>300</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>StandardOutPath</key>
    <string>/Users/CHANGEME/Library/Logs/url2obsidian/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/CHANGEME/Library/Logs/url2obsidian/stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 2: Commit**

```bash
git add packaging/com.mhattingpete.url2obsidian.plist.template
git commit -m "feat(packaging): launchd plist template"
```

---

## Task 14: CI

**Files:**
- Create: `.github/workflows/ci.yml`

GitHub Actions workflow: install uv, install Node deps for defuddle-cli, run ruff, ty, pytest.

- [ ] **Step 1: Write workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install Python deps
        run: uv sync --all-extras

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install defuddle-cli deps
        working-directory: tools/defuddle-cli
        run: npm ci

      - name: Cache Playwright browsers
        uses: actions/cache@v4
        with:
          path: ~/Library/Caches/ms-playwright
          key: playwright-${{ runner.os }}-${{ hashFiles('uv.lock') }}

      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps

      - name: Lint
        run: uv run ruff check .

      - name: Format check
        run: uv run ruff format --check .

      - name: Type check
        run: uv run ty src
        continue-on-error: true   # ty is alpha — don't block CI on its bugs

      - name: Test
        run: uv run pytest -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: lint, type-check, test on push"
```

---

## Final verification

- [ ] **Run the full local check**

Run: `uv run ruff check . && uv run ruff format --check . && uv run pytest -v`
Expected: all green.

- [ ] **End-to-end smoke**

Run: `uv run url2obsidian clip https://en.wikipedia.org/wiki/Markdown`
Expected: file appears at `<vault>/Clippings/markdown.md` with frontmatter and substantial body.

- [ ] **Schedule it**

Install the launchd plist per Task 13's README instructions. Share a URL from your phone to Raindrop. Wait ≤5 min. Check `<vault>/Clippings/` for the new file. Check Raindrop: item should now be in the `Clipped` collection.

---

## Self-review notes

**Spec coverage:**
- Capture side (Raindrop iOS app) — covered by README, no code needed. ✓
- Initial setup (`configure`) — Task 12. ✓
- Architecture pattern (Protocols, flat layout, composition root) — Tasks 3, 12. ✓
- Components table (10 modules + Node sidecar + plist + config) — Tasks 1–13. ✓
- Data flow (httpx → Playwright fallback → defuddle → render → vault → mark_clipped) — Tasks 9, 8, 6, 5, 10, 11. ✓
- Frontmatter shape — Task 6 golden file. ✓
- Error-handling table — Task 11 worker tests cover fetch error, http-4xx, extractor error, empty content; vault unwritable lands in `mark_failed` reason `vault`; auth errors handled in `RaindropClient` constructor; collision suffix in Task 5. ✓
- Idempotency — Raindrop tag state plus filename collision suffix handle re-runs. ✓
- Loud-failure principle — auth error raises at startup (CLI surfaces it); item errors only log + move to Failed. ✓
- Testing requirements — covered: unit tests per adapter, worker orchestration tests, manual e2e, ty + ruff in CI. ✓
- `flock` PID file for concurrent runs — **NOT** covered. launchd's `StartInterval` with a short job is generally safe (run-once finishes in seconds), but worst case overlapping runs could double-mark an item. Adding `flock` is a one-file change; left as a v1.1 follow-up.

**Placeholder scan:** none found.

**Type consistency:** `RaindropClient.list_unclipped` returns `Iterable[Item]` matching the protocol; `mark_clipped` / `mark_failed` arg names match. `FetchResult.method` Literal matches in fetcher and tests. `Article` reconstruction in CLI and worker uses `type(article)(...)` to dodge import — alternative is to import `Article` explicitly (cleaner; do this if you prefer in your implementation).

**Deferred for v1.1:**
- flock PID file
- macOS notifications via `pyobjc-framework-Cocoa` (dep already declared; not yet wired)
- exponential backoff on Raindrop 429/5xx (currently `raise_for_status` lets the next launchd run retry)
- bulk-clean tooling for the `Failed` collection
