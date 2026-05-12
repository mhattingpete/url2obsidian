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
