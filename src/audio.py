import asyncio
from typing import Awaitable, Callable

import soundfile as sf
try:
    import sounddevice as sd
except OSError:
    sd = None  # type: ignore[assignment]


def get_wav_duration_ms(wav_path: str) -> int:
    info = sf.info(wav_path)
    return int(info.duration * 1000)


def play_wav(wav_path: str) -> None:
    if sd is None:
        raise RuntimeError("sounddevice not available (PortAudio not installed)")
    data, rate = sf.read(wav_path)
    sd.play(data, samplerate=rate)
    sd.wait()


async def play_with_notify(
    wav_path: str, on_start: Callable[[int], Awaitable[None]]
) -> None:
    duration_ms = get_wav_duration_ms(wav_path)
    await on_start(duration_ms)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, play_wav, wav_path)
