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
