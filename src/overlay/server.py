import asyncio
import json
import logging
import os
import re
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Set

import requests as req
from fastapi import Body, FastAPI, File, Query, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import DEFAULT_TWITCH_CLIENT_ID, Config, load_config, save_config

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Set by main.py during setup-only mode so the save handler can signal exit
_setup_server = None


def set_setup_server(server) -> None:
    global _setup_server
    _setup_server = server

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def no_stale_cache(request, call_next):
    """OBS and browsers cache the overlay/config pages hard; everything is
    local so force revalidation instead of chasing stale styles."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response

_connections: Set[WebSocket] = set()


@app.get("/overlay", response_class=HTMLResponse)
async def overlay():
    return (STATIC_DIR / "overlay.html").read_text(encoding="utf-8")


@app.get("/auth/callback", response_class=HTMLResponse)
async def auth_callback():
    return (STATIC_DIR / "auth_callback.html").read_text(encoding="utf-8")


@app.post("/auth/token")
async def auth_token(data: dict = Body(...)):
    token = data.get("token", "").strip()
    client_id = data.get("client_id", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="No token provided")
    cfg = load_config()
    cfg.twitch_token = token
    # Persist the client id only when it's a custom one - keeps config.json
    # clean and the UI's client-id field hidden for the default app
    if client_id and client_id != DEFAULT_TWITCH_CLIENT_ID:
        cfg.twitch_client_id = client_id
    effective_id = client_id or cfg.client_id
    if effective_id:
        try:
            resp = await asyncio.to_thread(
                req.get,
                "https://api.twitch.tv/helix/users",
                headers={"Authorization": f"Bearer {token}", "Client-Id": effective_id},
                timeout=5,
            )
            if resp.ok:
                users = resp.json().get("data", [])
                if users:
                    cfg.channel_name = users[0]["login"]
            else:
                logger.warning("Twitch user lookup failed: HTTP %s", resp.status_code)
        except Exception:
            logger.exception("Twitch user lookup failed")
    save_config(cfg)
    return {"status": "ok", "channel_name": cfg.channel_name}


def _data_dir() -> Path:
    from src.config import config_path
    d = config_path().parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _unique_dest(filename: str) -> Path:
    name = re.sub(r'[^\w.\- ]', '_', Path(filename).name) or "file"
    dest = _data_dir() / name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while dest.exists():
        dest = _data_dir() / f"{stem}-{n}{suffix}"
        n += 1
    return dest


@app.post("/upload/voice")
async def upload_voice(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ('.wav', '.mp3'):
        raise HTTPException(status_code=400, detail="Only WAV and MP3 supported")
    dest = _unique_dest(file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": str(dest)}


@app.post("/upload/gif")
async def upload_gif(file: UploadFile = File(...)):
    if Path(file.filename).suffix.lower() != '.gif':
        raise HTTPException(status_code=400, detail="Only GIF supported")
    dest = _unique_dest(file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": str(dest)}


_AUDIO_EXTS = {'.wav', '.mp3'}


def _safe_data_file(name: str) -> Path:
    target = _data_dir() / Path(name).name
    if target.name != name or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return target


@app.get("/files")
async def list_files():
    cfg = load_config()
    files = []
    for p in sorted(_data_dir().iterdir()):
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        kind = "audio" if suffix in _AUDIO_EXTS else "gif" if suffix == ".gif" else "other"
        files.append({
            "name": p.name,
            "path": str(p),
            "size": p.stat().st_size,
            "kind": kind,
            "in_use": str(p) in (cfg.voice_sample, cfg.overlay_gif),
        })
    return {"files": files, "voice_sample": cfg.voice_sample, "overlay_gif": cfg.overlay_gif}


@app.get("/files/{name}")
async def get_file(name: str):
    return FileResponse(str(_safe_data_file(name)))


@app.delete("/files/{name}")
async def delete_file(name: str):
    target = _safe_data_file(name)
    target.unlink()
    cfg = load_config()
    changed = False
    if cfg.voice_sample == str(target):
        cfg.voice_sample = ""
        changed = True
    if cfg.overlay_gif == str(target):
        cfg.overlay_gif = ""
        changed = True
    if changed:
        save_config(cfg)
    return {"status": "deleted", "config_cleared": changed}


@app.post("/test/alert")
async def test_alert(data: dict = Body(default={})):
    username = str(data.get("username") or "shima").strip() or "shima"
    message = str(data.get("message") or "This is a test alert from ShimaTTS!").strip()
    await broadcast(username, message, int(data.get("duration_ms") or 4000))
    return {"status": "sent", "connections": len(_connections)}


@app.post("/app/quit")
async def app_quit():
    logger.info("Quit requested from config UI")
    asyncio.get_running_loop().call_later(0.3, os._exit, 0)
    return {"status": "quitting"}


@app.get("/browse")
async def browse_file(type: str = Query("gif")):
    if sys.platform != "win32":
        raise HTTPException(status_code=501, detail="Native browse only supported on Windows")

    def _webview_dialog() -> str | None:
        import src.main as main_mod
        win = getattr(main_mod, "_webview_window", None)
        if win is None:
            return None
        import webview
        if type == "voice":
            file_types = ("Audio files (*.wav;*.mp3)", "All files (*.*)")
        else:
            file_types = ("GIF files (*.gif)", "All files (*.*)")
        result = win.create_file_dialog(webview.OPEN_DIALOG, file_types=file_types)
        if not result:
            return ""
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    def _tkinter_dialog() -> str:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if type == "voice":
            path = filedialog.askopenfilename(
                parent=root,
                title="Select Voice Sample",
                filetypes=[("Audio files", "*.wav *.mp3"), ("WAV", "*.wav"), ("MP3", "*.mp3"), ("All files", "*.*")],
            )
        else:
            path = filedialog.askopenfilename(
                parent=root,
                title="Select Alert GIF",
                filetypes=[("GIF files", "*.gif"), ("All files", "*.*")],
            )
        root.destroy()
        return path or ""

    def _pick() -> str:
        try:
            result = _webview_dialog()
            if result is not None:
                return result
        except Exception:
            logger.exception("webview file dialog failed, falling back to tkinter")
        return _tkinter_dialog()

    path = await asyncio.to_thread(_pick)
    return {"path": path}


@app.get("/overlay-gif")
async def overlay_gif():
    cfg = load_config()
    path = Path(cfg.overlay_gif)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="GIF not found")
    return FileResponse(str(path))


@app.get("/config", response_class=HTMLResponse)
async def config_page():
    return (STATIC_DIR / "config.html").read_text(encoding="utf-8")


@app.get("/config/data")
async def config_data():
    cfg = load_config()
    return {
        "twitch_token": cfg.twitch_token,
        "twitch_client_id": cfg.twitch_client_id,
        "channel_name": cfg.channel_name,
        "reward_name": cfg.reward_name,
        "voice_sample": cfg.voice_sample,
        "voice_sample_text": cfg.voice_sample_text,
        "overlay_gif": cfg.overlay_gif,
        "tts_template": cfg.tts_template,
        "max_message_words": cfg.max_message_words,
        "blocked_words": cfg.blocked_words,
        "default_client_id": DEFAULT_TWITCH_CLIENT_ID,
    }


@app.post("/config/save")
async def config_save(data: dict = Body(...)):
    valid_keys = Config.__dataclass_fields__.keys()
    # Merge onto the existing config so fields the UI doesn't send
    # (port, twitch_client_id, voice_sample_text) survive a save
    merged = asdict(load_config())
    merged.update({k: v for k, v in data.items() if k in valid_keys})
    try:
        cfg = Config(**merged)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    save_config(cfg)
    complete = cfg.is_complete()
    if complete and _setup_server is not None:
        _setup_server.should_exit = True
    return {"status": "saved", "complete": complete}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _connections.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _connections.discard(ws)


async def broadcast(username: str, message: str, duration_ms: int) -> None:
    payload = json.dumps({
        "username": username,
        "message": message,
        "duration_ms": duration_ms,
    })
    dead: Set[WebSocket] = set()
    for ws in list(_connections):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _connections.discard(ws)
