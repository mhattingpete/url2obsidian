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
