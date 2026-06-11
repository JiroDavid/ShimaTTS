import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.config import Config, load_config, save_config


def test_config_defaults():
    cfg = Config()
    assert cfg.max_message_words == 20
    assert cfg.blocked_words == []
    assert cfg.port == 7878
    assert cfg.twitch_token == ""


def test_blocked_words_normalized():
    cfg = Config(blocked_words=["  Foo ", "BAR", "", "baz"])
    assert cfg.blocked_words == ["foo", "bar", "baz"]


def test_load_ignores_legacy_keys(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"max_message_length": 200, "channel_name": "x"}')
    with patch("src.config.config_path", return_value=config_file):
        cfg = load_config()
    assert cfg.channel_name == "x"
    assert cfg.max_message_words == 20


def test_is_complete_false_when_fields_empty():
    assert Config().is_complete() is False


def test_is_complete_true_when_all_fields_set(basic_config):
    assert basic_config.is_complete() is True


def test_save_and_load_roundtrip(tmp_path, basic_config):
    config_file = tmp_path / "config.json"
    with patch("src.config.config_path", return_value=config_file):
        save_config(basic_config)
        loaded = load_config()
    assert loaded == basic_config


def test_load_returns_defaults_when_file_missing(tmp_path):
    with patch("src.config.config_path", return_value=tmp_path / "missing.json"):
        cfg = load_config()
    assert cfg.twitch_token == ""
    assert cfg.max_message_words == 20


def test_save_writes_valid_json(tmp_path, basic_config):
    config_file = tmp_path / "config.json"
    with patch("src.config.config_path", return_value=config_file):
        save_config(basic_config)
    data = json.loads(config_file.read_text())
    assert data["channel_name"] == "testchannel"


def test_load_returns_defaults_on_malformed_json(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text("{not valid json")
    with patch("src.config.config_path", return_value=config_file):
        cfg = load_config()
    assert cfg.twitch_token == ""
