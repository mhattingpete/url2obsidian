import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "url2obsidian" / "config.toml"
DEFAULT_INBOX_DIR = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/url2obsidian"


class Config(BaseModel):
    vault_path: Path
    clippings_subdir: str = "Clippings"
    inbox_dir: Path = DEFAULT_INBOX_DIR
    poll_interval_seconds: int = Field(default=300, ge=60)
    download_images: bool = True
    notification_on_error: bool = True


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = tomllib.loads(path.read_text())
    return Config(**data)
