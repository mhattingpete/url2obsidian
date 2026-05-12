import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from url2obsidian.models import Article


class ExtractorError(RuntimeError):
    pass


class DefuddleExtractor:
    """Wraps the `defuddle` Node CLI binary.

    defuddle's CLI reads HTML from a file (not stdin), so we write the
    incoming HTML to a tempfile per call. Output is JSON with the fields
    produced by `defuddle parse <file> -j -m`.
    """

    def __init__(self, cli_path: Path, timeout_s: float = 30.0) -> None:
        self._cli = cli_path
        self._timeout = timeout_s

    def extract(self, html: str, url: str) -> Article:
        if not html:
            raise ExtractorError("empty html")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(html)
            tmp_path = Path(tmp.name)

        try:
            proc = subprocess.run(
                [str(self._cli), "parse", str(tmp_path), "-j", "-m"],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise ExtractorError(f"defuddle timeout after {self._timeout}s") from e
        finally:
            tmp_path.unlink(missing_ok=True)

        if proc.returncode != 0:
            raise ExtractorError(f"defuddle exit {proc.returncode}: {proc.stderr.strip()}")

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ExtractorError(f"defuddle produced invalid JSON: {e}") from e

        return Article(
            title=data.get("title", "") or "",
            byline=data.get("author", "") or "",
            content_markdown=data.get("content", "") or "",
            published=_parse_iso(data.get("published")),
            site_name=data.get("site", "") or data.get("domain", "") or "",
        )


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
