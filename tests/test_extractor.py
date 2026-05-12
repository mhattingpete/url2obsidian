import shutil
from pathlib import Path

import pytest

from url2obsidian.extractor import DefuddleExtractor, ExtractorError

FIXTURES = Path(__file__).parent / "fixtures"
CLI_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "defuddle-cli"
    / "node_modules"
    / ".bin"
    / "defuddle"
)


pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not CLI_PATH.exists(),
    reason="node and tools/defuddle-cli/node_modules/.bin/defuddle required",
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
