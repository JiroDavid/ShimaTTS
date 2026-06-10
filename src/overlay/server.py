import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Set

import requests as req
from fastapi import Body, FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import Config, load_config, save_config

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Set by main.py during setup-only mode so the save handler can signal exit
_setup_server = None


def set_setup_server(server) -> None:
    global _setup_server
    _setup_server = server

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_connections: Set[WebSocket] = set()


@app.get("/overlay", response_class=HTMLResponse)
async def overlay():
    return (STATIC_DIR / "overlay.html").read_text()


@app.get("/auth/callback", response_class=HTMLResponse)
async def auth_callback():
    return (STATIC_DIR / "auth_callback.html").read_text()


@app.post("/auth/token")
async def auth_token(data: dict = Body(...)):
    token = data.get("token", "").strip()
    client_id = data.get("client_id", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="No token provided")
    cfg = load_config()
    cfg.twitch_token = token
    if client_id:
        cfg.twitch_client_id = client_id
    if client_id:
        try:
            resp = await asyncio.to_thread(
                req.get,
                "https://api.twitch.tv/helix/users",
                headers={"Authorization": f"Bearer {token}", "Client-Id": client_id},
                timeout=5,
            )
            if resp.ok:
                users = resp.json().get("data", [])
                if users:
                    cfg.channel_name = users[0]["login"]
        except Exception:
            pass
    save_config(cfg)
    return {"status": "ok", "channel_name": cfg.channel_name}


def _data_dir() -> Path:
    from src.config import config_path
    d = config_path().parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.post("/upload/voice")
async def upload_voice(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ('.wav', '.mp3'):
        raise HTTPException(status_code=400, detail="Only WAV and MP3 supported")
    dest = _data_dir() / f"voice_sample{suffix}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": str(dest)}


@app.post("/upload/gif")
async def upload_gif(file: UploadFile = File(...)):
    dest = _data_dir() / "overlay.gif"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": str(dest)}


@app.get("/overlay-gif")
async def overlay_gif():
    cfg = load_config()
    path = Path(cfg.overlay_gif)
    if not path.exists():
        raise HTTPException(status_code=404, detail="GIF not found")
    return FileResponse(str(path))


@app.get("/config", response_class=HTMLResponse)
async def config_page():
    return (STATIC_DIR / "config.html").read_text()


@app.get("/config/data")
async def config_data():
    cfg = load_config()
    return {
        "twitch_token": cfg.twitch_token,
        "twitch_client_id": cfg.twitch_client_id,
        "channel_name": cfg.channel_name,
        "reward_name": cfg.reward_name,
        "voice_sample": cfg.voice_sample,
        "overlay_gif": cfg.overlay_gif,
        "max_message_length": cfg.max_message_length,
        "port": cfg.port,
    }


@app.post("/config/save")
async def config_save(data: dict = Body(...)):
    valid_keys = Config.__dataclass_fields__.keys()
    try:
        cfg = Config(**{k: v for k, v in data.items() if k in valid_keys})
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
