import asyncio
import struct
import wave
import pytest
from unittest.mock import patch, MagicMock


def make_test_wav(path: str, duration_ms: int = 500, rate: int = 22050) -> None:
    n_frames = int(rate * duration_ms / 1000)
    with wave.open(path, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"\x00\x00" * n_frames)


def test_get_wav_duration_ms(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    make_test_wav(wav_path, duration_ms=500)

    from src.audio import get_wav_duration_ms
    duration = get_wav_duration_ms(wav_path)
    assert 480 <= duration <= 520  # within 20ms tolerance


def test_play_wav_calls_sounddevice(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    make_test_wav(wav_path)

    with patch("src.audio.sd") as mock_sd:
        from src.audio import play_wav
        play_wav(wav_path)
        mock_sd.play.assert_called_once()
        mock_sd.wait.assert_called_once()


@pytest.mark.asyncio
async def test_play_with_notify_calls_on_start(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    make_test_wav(wav_path, duration_ms=200)

    notified_duration = []

    async def on_start(duration_ms: int) -> None:
        notified_duration.append(duration_ms)

    with patch("src.audio.sd"):
        from src.audio import play_with_notify
        await play_with_notify(wav_path, on_start)

    assert len(notified_duration) == 1
    assert notified_duration[0] > 0
