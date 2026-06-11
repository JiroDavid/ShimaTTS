import os
import pytest
from unittest.mock import MagicMock


def test_generate_calls_infer():
    import src.tts as tts_mod
    mock_model = MagicMock()
    original = tts_mod._model
    tts_mod._model = mock_model
    try:
        def fake_infer(**kwargs):
            open(kwargs["file_wave"], "w").close()
        mock_model.infer.side_effect = fake_infer

        result = tts_mod.generate("hello world", "/voice.wav", "sample text")
        assert result.endswith(".wav")
        assert os.path.exists(result)
        os.unlink(result)

        mock_model.infer.assert_called_once()
        call_kwargs = mock_model.infer.call_args.kwargs
        assert call_kwargs["gen_text"] == "hello world"
        assert call_kwargs["ref_file"] == "/voice.wav"
        assert call_kwargs["ref_text"] == "sample text"
    finally:
        tts_mod._model = original


def test_generate_raises_when_model_not_loaded():
    import src.tts as tts_mod
    original = tts_mod._model
    tts_mod._model = None
    try:
        with pytest.raises(RuntimeError, match="Model not loaded"):
            tts_mod.generate("hello", "/voice.wav")
    finally:
        tts_mod._model = original


def test_is_loaded_false_before_load():
    import src.tts as tts_mod
    original = tts_mod._model
    tts_mod._model = None
    try:
        assert tts_mod.is_loaded() is False
    finally:
        tts_mod._model = original


def test_is_loaded_true_after_mock_load():
    import src.tts as tts_mod
    original = tts_mod._model
    tts_mod._model = MagicMock()
    try:
        assert tts_mod.is_loaded() is True
    finally:
        tts_mod._model = original
