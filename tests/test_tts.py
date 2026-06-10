import os
import pytest
from unittest.mock import MagicMock, patch


def test_generate_calls_tts_to_file(tmp_path):
    import src.tts as tts_mod
    mock_tts_instance = MagicMock()
    original = tts_mod._tts
    tts_mod._tts = mock_tts_instance
    try:
        def fake_tts_to_file(**kwargs):
            open(kwargs["file_path"], "w").close()
        mock_tts_instance.tts_to_file.side_effect = fake_tts_to_file

        result = tts_mod.generate("hello world", "/voice.wav")
        assert result.endswith(".wav")
        assert os.path.exists(result)

        mock_tts_instance.tts_to_file.assert_called_once()
        call_kwargs = mock_tts_instance.tts_to_file.call_args.kwargs
        assert call_kwargs["text"] == "hello world"
        assert call_kwargs["speaker_wav"] == "/voice.wav"
        assert call_kwargs["language"] == "en"
    finally:
        tts_mod._tts = original


def test_generate_raises_when_model_not_loaded():
    import src.tts as tts_mod
    original = tts_mod._tts
    tts_mod._tts = None
    try:
        with pytest.raises(RuntimeError, match="Model not loaded"):
            tts_mod.generate("hello", "/voice.wav")
    finally:
        tts_mod._tts = original


def test_is_loaded_false_before_load():
    import src.tts as tts_mod
    original = tts_mod._tts
    tts_mod._tts = None
    try:
        assert tts_mod.is_loaded() is False
    finally:
        tts_mod._tts = original


def test_is_loaded_true_after_mock_load():
    import src.tts as tts_mod
    original = tts_mod._tts
    tts_mod._tts = MagicMock()
    try:
        assert tts_mod.is_loaded() is True
    finally:
        tts_mod._tts = original
