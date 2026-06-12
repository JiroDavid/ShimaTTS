import asyncio
import logging
import os
from typing import Callable, Tuple

DEFAULT_TTS_TEMPLATE = "{username} says {message}"

from src.config import Config
import src.tts as tts_module
import src.audio as audio

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(self, config: Config, on_overlay_event: Callable):
        self.config = config
        self.on_overlay_event = on_overlay_event
        self._queue: asyncio.Queue[Tuple[str, str]] = asyncio.Queue()

    def enqueue(self, username: str, message: str) -> None:
        self._queue.put_nowait((username, message))

    async def run(self) -> None:
        while True:
            username, message = await self._queue.get()
            try:
                await self._process(username, message)
            except Exception as e:
                logger.error("TTS processing failed for %s: %s", username, e)
            finally:
                self._queue.task_done()

    async def _process(self, username: str, message: str) -> None:
        loop = asyncio.get_running_loop()
        template = self.config.tts_template or DEFAULT_TTS_TEMPLATE
        if "{message}" not in template:
            template = DEFAULT_TTS_TEMPLATE
        tts_text = template.replace("{username}", username).replace("{message}", message)
        wav_path = await loop.run_in_executor(
            None, tts_module.generate, tts_text, self.config.voice_sample, self.config.voice_sample_text
        )

        async def on_start(duration_ms: int) -> None:
            await self.on_overlay_event(username, message, duration_ms)

        try:
            await audio.play_with_notify(wav_path, on_start)
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass
