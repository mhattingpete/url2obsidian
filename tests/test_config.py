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
