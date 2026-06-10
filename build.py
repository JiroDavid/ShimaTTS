#!/usr/bin/env python3
"""
Run on Windows to build ShimaTTS.exe.
Requires: pip install pyinstaller (on Windows)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "src" / "overlay" / "static"
ASSETS_DIR = ROOT / "assets"

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onedir",
    "--name", "ShimaTTS",
    "--noconsole",
    "--icon", str(ASSETS_DIR / "icon.ico"),
    "--add-data", f"{STATIC_DIR};src/overlay/static",
    "--add-data", f"{ASSETS_DIR};assets",
    "--hidden-import", "TTS",
    "--hidden-import", "torch",
    "--hidden-import", "torchaudio",
    "--hidden-import", "sounddevice",
    "--hidden-import", "pystray",
    "--collect-all", "TTS",
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
