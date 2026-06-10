import json
import logging
from pathlib import Path
from typing import Set

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import Config, load_config, save_config

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_connections: Set[WebSocket] = set()


@app.get("/overlay", response_class=HTMLResponse)
async def overlay():
    return (STATIC_DIR / "overlay.html").read_text()


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
    cfg = Config(**{k: v for k, v in data.items() if k in valid_keys})
    save_config(cfg)
    return {"status": "saved"}


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
