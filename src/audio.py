import asyncio
import wave
from typing import Awaitable, Callable

import numpy as np
try:
    import sounddevice as sd
except OSError:
    sd = None  # type: ignore[assignment]


def get_wav_duration_ms(wav_path: str) -> int:
    with wave.open(wav_path, "r") as f:
        return int(f.getnframes() / f.getframerate() * 1000)


def play_wav(wav_path: str) -> None:
    with wave.open(wav_path, "r") as f:
        rate = f.getframerate()
        channels = f.getnchannels()
        raw = f.readframes(f.getnframes())

    data = np.frombuffer(raw, dtype=np.int16)
    if channels == 2:
        data = data.reshape(-1, 2)

    sd.play(data, samplerate=rate)
    sd.wait()


async def play_with_notify(
    wav_path: str, on_start: Callable[[int], Awaitable[None]]
) -> None:
    duration_ms = get_wav_duration_ms(wav_path)
    await on_start(duration_ms)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, play_wav, wav_path)
