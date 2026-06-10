import logging
import os
import tempfile
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
_MODELS_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ShimaTTS" / "models"
)

_tts = None


def load_model(progress_callback: Optional[Callable[[str], None]] = None) -> None:
    global _tts
    from TTS.api import TTS
    import torch

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["COQUI_TOS_AGREED"] = "1"

    use_gpu = torch.cuda.is_available()
    device = "cuda" if use_gpu else "cpu"
    logger.info("Loading XTTS v2 on %s", device)

    if progress_callback:
        progress_callback(f"Loading XTTS v2 model on {device} (~1.8GB on first run)...")

    _tts = TTS(model_name=MODEL_NAME, gpu=use_gpu, progress_bar=True)

    if progress_callback:
        progress_callback("Model ready.")


def generate(text: str, voice_sample: str) -> str:
    if _tts is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name

    _tts.tts_to_file(
        text=text,
        speaker_wav=voice_sample,
        language="en",
        file_path=out_path,
    )
    return out_path


def is_loaded() -> bool:
    return _tts is not None
