import logging
import os
import tempfile
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()


def load_model(progress_callback: Optional[Callable[[str], None]] = None) -> None:
    global _model

    with _lock:
        if _model is not None:
            return

        from f5_tts.api import F5TTS
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading F5-TTS on %s", device)

        if progress_callback:
            progress_callback(f"Loading F5-TTS model on {device}...")

        _model = F5TTS(device=device)

        if progress_callback:
            progress_callback("Model ready.")


def generate(text: str, voice_sample: str, ref_text: str = "") -> str:
    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name

    _model.infer(
        ref_file=voice_sample,
        ref_text=ref_text,
        gen_text=text,
        file_wave=out_path,
        target_rms=0.3,
        nfe_step=64,
        cfg_strength=2.0,
        speed=0.85,
    )
    return out_path


def is_loaded() -> bool:
    return _model is not None
