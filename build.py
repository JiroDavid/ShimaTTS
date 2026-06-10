#!/usr/bin/env python3
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "src" / "overlay" / "static"
ASSETS_DIR = ROOT / "assets"


def find_binary(name: str) -> Path:
    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(
            f"Could not find '{name}' on PATH. Install ffmpeg and ensure it is on your PATH."
        )
    return Path(path)


ffmpeg = find_binary("ffmpeg")
ffprobe = find_binary("ffprobe")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onedir",
    "--name", "ShimaTTS",
    "--noconsole",
    "--icon", str(ASSETS_DIR / "icon.ico"),
    "--add-data", f"{STATIC_DIR};src/overlay/static",
    "--add-data", f"{ASSETS_DIR};assets",
    "--add-binary", f"{ffmpeg};.",
    "--add-binary", f"{ffprobe};.",
    "--collect-all", "f5_tts",
    "--collect-all", "vocos",
    "--collect-all", "soundfile",
    "--collect-all", "better_profanity",
    "--collect-all", "transformers",
    "--collect-all", "tokenizers",
    "--collect-all", "einops",
    "--collect-all", "x_transformers",
    "--collect-all", "jieba",
    "--collect-all", "pypinyin",
    "--collect-all", "librosa",
    "--collect-all", "numba",
    "--collect-all", "llvmlite",
    "--collect-all", "accelerate",
    "--collect-all", "uvicorn",
    "--hidden-import", "torch",
    "--hidden-import", "torchaudio",
    "--hidden-import", "sounddevice",
    "--hidden-import", "pystray",
    "--hidden-import", "pydub",
    "--hidden-import", "omegaconf",
    "--hidden-import", "hydra",
    "--hidden-import", "cached_path",
    "--hidden-import", "safetensors",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "uvicorn.lifespan.on",
    "--hidden-import", "fastapi",
    "--hidden-import", "websockets",
    "--hidden-import", "requests",
    "--paths", ".",
    str(ROOT / "src" / "main.py"),
]

print("Building ShimaTTS.exe...")
result = subprocess.run(cmd, cwd=str(ROOT))
if result.returncode == 0:
    print("\nBuild complete: dist/ShimaTTS/ShimaTTS.exe")
else:
    print("\nBuild failed.")
    sys.exit(1)
