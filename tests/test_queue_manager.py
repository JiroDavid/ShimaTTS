import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import Config
from src.queue_manager import QueueManager


@pytest.fixture
def cfg():
    return Config(
        twitch_token="t", twitch_client_id="c",
        channel_name="ch", reward_name="TTS",
        voice_sample="/voice.wav", overlay_gif="/gif.gif",
        max_message_length=200,
    )


@pytest.mark.asyncio
async def test_enqueue_filtered_message_is_dropped(cfg):
    overlay_events = []
    qm = QueueManager(cfg, on_overlay_event=AsyncMock(side_effect=overlay_events.append))
    # "a" * 201 exceeds max_message_length=200
    qm.enqueue("viewer", "a" * 201)
    assert qm._queue.empty()


@pytest.mark.asyncio
async def test_enqueue_clean_message_is_queued(cfg):
    qm = QueueManager(cfg, on_overlay_event=AsyncMock())
    qm.enqueue("viewer", "hello chat")
    assert not qm._queue.empty()
    username, message = qm._queue.get_nowait()
    assert username == "viewer"
    assert message == "hello chat"


@pytest.mark.asyncio
async def test_process_calls_tts_and_audio(cfg, tmp_path):
    fake_wav = str(tmp_path / "out.wav")
    open(fake_wav, "w").close()

    overlay_calls = []

    async def fake_overlay(u, m, d):
        overlay_calls.append((u, m, d))

    qm = QueueManager(cfg, on_overlay_event=fake_overlay)

    async def fake_play(wav, on_start):
        await on_start(1500)

    with patch("src.queue_manager.tts_module.generate", return_value=fake_wav), \
         patch("src.queue_manager.audio.play_with_notify", side_effect=fake_play):
        await qm._process("viewer1", "hello world")

    assert len(overlay_calls) == 1
    assert overlay_calls[0][0] == "viewer1"
    assert overlay_calls[0][1] == "hello world"


@pytest.mark.asyncio
async def test_process_cleans_up_wav_on_error(cfg, tmp_path):
    fake_wav = str(tmp_path / "out.wav")
    open(fake_wav, "w").close()

    qm = QueueManager(cfg, on_overlay_event=AsyncMock())

    with patch("src.queue_manager.tts_module.generate", return_value=fake_wav), \
         patch("src.queue_manager.audio.play_with_notify", new_callable=AsyncMock,
               side_effect=RuntimeError("audio fail")):
        with pytest.raises(RuntimeError):
            await qm._process("viewer1", "oops")

    import os
    assert not os.path.exists(fake_wav)
