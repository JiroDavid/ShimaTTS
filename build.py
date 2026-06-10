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
    # ML / TTS packages with data files or lazy imports PyInstaller misses
    "--collect-all", "f5_tts",
    "--collect-all", "vocos",
    "--collect-all", "soundfile",
    "--collect-all", "better_profanity",
    "--collect-all", "transformers",
    "--collect-all", "tokenizers",
    "--collect-all", "einops",
    "--collect-all", "x_transformers",
    "--collect-all", "ema_pytorch",
    "--collect-all", "pypinyin",
    "--collect-all", "rjieba",
    "--collect-all", "librosa",
    "--collect-all", "cached_path",
    "--collect-all", "huggingface_hub",
    "--collect-all", "omegaconf",
    "--collect-all", "torchdiffeq",
    "--collect-all", "unidecode",
    # Web / app packages with lazy backends or data files
    "--collect-all", "anyio",           # starlette async backend (lazily imported)
    "--collect-all", "pydantic",        # fastapi validation (native .pyd + lazy internals)
    "--collect-all", "pydantic_core",   # pydantic V2 native extension
    "--collect-all", "pystray",         # includes _win32 backend missed by --hidden-import
    "--collect-all", "python_multipart", # fastapi file upload form parsing
    "--collect-all", "certifi",         # requests CA bundle (data file)
    "--collect-all", "h11",             # uvicorn HTTP/1.1 fallback parser
    # Hidden imports for lazy-loaded backends not reachable by static analysis
    "--hidden-import", "torch",
    "--hidden-import", "torchaudio",
    "--hidden-import", "sounddevice",
    "--hidden-import", "pydub",
    "--hidden-import", "hydra",
    "--hidden-import", "safetensors",
    "--hidden-import", "six",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.http.h11_impl",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "uvicorn.protocols.websockets.websockets_impl",
    "--hidden-import", "uvicorn.lifespan.on",
    "--hidden-import", "fastapi",
    "--hidden-import", "websockets",
    "--hidden-import", "requests",
    # Exclude heavy training/UI deps pulled in transitively by f5-tts
    "--exclude-module", "gradio",
    "--exclude-module", "gradio_client",
    "--exclude-module", "wandb",
    "--exclude-module", "datasets",
    "--exclude-module", "bitsandbytes",
    "--collect-all", "matplotlib",
    "--exclude-module", "accelerate",
    "--exclude-module", "torchcodec",
    "--exclude-module", "transformers_stream_generator",
    "--exclude-module", "numba",
    "--exclude-module", "llvmlite",
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
