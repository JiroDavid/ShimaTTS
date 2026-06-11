#!/usr/bin/env python3
"""
Build the ShimaTTS distribution.

Only launcher.py gets frozen (PyInstaller). The app itself ships as source
and runs from a uv-provisioned environment created on the user's machine at
first launch - that's what makes GPU torch possible (CUDA torch is 4+ GB,
GitHub release assets cap at 2 GB).

Output: dist/ShimaTTS/
  ShimaTTS.exe      frozen launcher
  uv.exe            pinned uv binary (downloaded at build time)
  ffmpeg.exe        copied from PATH
  ffprobe.exe       copied from PATH
  requirements.txt  runtime env spec
  src/              app source + static files
"""
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist" / "ShimaTTS"
UV_VERSION = "0.11.20"
UV_URL = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/uv-x86_64-pc-windows-msvc.zip"


def find_binary(name: str) -> Path:
    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(
            f"Could not find '{name}' on PATH. Install ffmpeg and ensure it is on your PATH."
        )
    return Path(path)


def fetch_uv() -> Path:
    cache = ROOT / "build" / f"uv-{UV_VERSION}.exe"
    if cache.exists():
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    zip_path = cache.with_suffix(".zip")
    print(f"Downloading uv {UV_VERSION}...")
    urllib.request.urlretrieve(UV_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("uv.exe") as src, open(cache, "wb") as dst:
            shutil.copyfileobj(src, dst)
    zip_path.unlink()
    return cache


def build_launcher() -> Path:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "ShimaTTS",
        "--icon", str(ROOT / "assets" / "icon.ico"),
        "--distpath", str(ROOT / "build" / "launcher-dist"),
        "--workpath", str(ROOT / "build" / "launcher-work"),
        "--specpath", str(ROOT / "build"),
        str(ROOT / "launcher.py"),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        sys.exit("PyInstaller failed.")
    return ROOT / "build" / "launcher-dist" / "ShimaTTS.exe"


def main() -> None:
    if sys.platform != "win32":
        sys.exit("This build targets Windows - run it with a Windows Python.")

    ffmpeg = find_binary("ffmpeg")
    ffprobe = find_binary("ffprobe")
    uv = fetch_uv()
    exe = build_launcher()

    # Refresh build outputs but keep provisioned runtime/user state so a
    # rebuild doesn't force a multi-GB re-download during development
    keep = {"runtime", "pydist", "uv-cache", "launcher.log", "ShimaTTS.log", "config.json", "data"}
    if DIST.exists():
        for child in DIST.iterdir():
            if child.name in keep:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    DIST.mkdir(parents=True, exist_ok=True)

    shutil.copy2(exe, DIST / "ShimaTTS.exe")
    shutil.copy2(uv, DIST / "uv.exe")
    shutil.copy2(ffmpeg, DIST / "ffmpeg.exe")
    shutil.copy2(ffprobe, DIST / "ffprobe.exe")
    shutil.copy2(ROOT / "requirements.txt", DIST / "requirements.txt")
    shutil.copytree(
        ROOT / "src", DIST / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    if (ROOT / "defaults").is_dir():
        shutil.copytree(ROOT / "defaults", DIST / "defaults")

    size_mb = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1048576
    print(f"\nBuild complete: {DIST} ({size_mb:.0f} MB before zip)")


if __name__ == "__main__":
    main()
