import tomllib
from pathlib import Path

import pytest

from url2obsidian.config import DEFAULT_INBOX_DIR, Config, load_config


def test_load_config_from_path(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        'vault_path = "/tmp/vault"\n'
        'clippings_subdir = "Clippings"\n'
        'inbox_dir = "/tmp/inbox"\n'
        "poll_interval_seconds = 300\n"
        "download_images = true\n"
        "notification_on_error = true\n"
    )
    cfg = load_config(cfg_file)
    assert isinstance(cfg, Config)
    assert cfg.vault_path == Path("/tmp/vault")
    assert cfg.inbox_dir == Path("/tmp/inbox")
    assert cfg.poll_interval_seconds == 300


def test_load_config_uses_default_inbox_dir(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('vault_path = "/tmp/vault"\n')
    cfg = load_config(cfg_file)
    assert cfg.inbox_dir == DEFAULT_INBOX_DIR


def test_load_config_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "absent.toml")


def test_load_config_invalid_toml(tmp_path: Path):
    cfg_file = tmp_path / "bad.toml"
    cfg_file.write_text("not = valid = toml")
    with pytest.raises(tomllib.TOMLDecodeError):
        load_config(cfg_file)
