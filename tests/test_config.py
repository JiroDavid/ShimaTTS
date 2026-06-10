import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.config import Config, load_config, save_config


def test_config_defaults():
    cfg = Config()
    assert cfg.max_message_length == 200
    assert cfg.port == 7878
    assert cfg.twitch_token == ""


def test_is_complete_false_when_fields_empty():
    assert Config().is_complete() is False


def test_is_complete_true_when_all_fields_set(basic_config):
    assert basic_config.is_complete() is True


def test_save_and_load_roundtrip(tmp_path, basic_config):
    config_file = tmp_path / "config.json"
    with patch("src.config.config_path", return_value=config_file):
        save_config(basic_config)
        loaded = load_config()
    assert loaded.twitch_token == "test_token"
    assert loaded.twitch_client_id == "test_client_id"
    assert loaded.channel_name == "testchannel"
    assert loaded.port == 7878


def test_load_returns_defaults_when_file_missing(tmp_path):
    with patch("src.config.config_path", return_value=tmp_path / "missing.json"):
        cfg = load_config()
    assert cfg.twitch_token == ""
    assert cfg.max_message_length == 200


def test_save_writes_valid_json(tmp_path, basic_config):
    config_file = tmp_path / "config.json"
    with patch("src.config.config_path", return_value=config_file):
        save_config(basic_config)
    data = json.loads(config_file.read_text())
    assert data["channel_name"] == "testchannel"
