import argparse
import asyncio
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from src.config import Config, load_config, save_config
from src.queue_manager import QueueManager
from src.twitch import TwitchListener
from src.overlay.server import app as overlay_app, broadcast
from src.tray import TrayApp
import src.tts as tts_module

_EXE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
LOG_PATH = _EXE_DIR / "ShimaTTS.log"

if getattr(sys, 'frozen', False):
    import pydub
    pydub.AudioSegment.converter = str(_EXE_DIR / "ffmpeg.exe")
    pydub.AudioSegment.ffprobe = str(_EXE_DIR / "ffprobe.exe")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ShimaTTS - Local Twitch TTS alerts")
    p.add_argument("--test-tts", metavar="MESSAGE", help="Generate and play TTS without Twitch")
    p.add_argument("--test-overlay", action="store_true", help="Fire a fake redemption in OBS")
    p.add_argument("--test-twitch", action="store_true", help="Connect and print redemptions without TTS")
    p.add_argument("--tts-server", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args()


async def _run_test_tts(message: str, cfg: Config) -> None:
    logger.info("Loading model for TTS test...")
    tts_module.load_model(progress_callback=print)
    wav = tts_module.generate(message, cfg.voice_sample)
    from src.audio import play_wav
    logger.info("Playing: %s", message)
    await asyncio.get_running_loop().run_in_executor(None, play_wav, wav)
    os.unlink(wav)


async def _run_test_overlay(cfg: Config) -> None:
    server_cfg = uvicorn.Config(overlay_app, host="127.0.0.1", port=cfg.port, log_level="warning")
    server = uvicorn.Server(server_cfg)

    async def fire_after_start():
        await asyncio.sleep(1.5)
        await broadcast("TestViewer", "This is a test TTS message from ShimaTTS!", 4000)
        await asyncio.sleep(5)
        server.should_exit = True

    logger.info("Open http://localhost:%d/overlay in OBS browser source, then check for alert...", cfg.port)
    await asyncio.gather(server.serve(), fire_after_start())


async def _run_test_twitch(cfg: Config) -> None:
    def on_redeem(username: str, message: str) -> None:
        print(f"REDEMPTION: [{username}] {message}")

    listener = TwitchListener(
        token=cfg.twitch_token,
        client_id=cfg.twitch_client_id,
        channel_name=cfg.channel_name,
        reward_name=cfg.reward_name,
        on_redemption=on_redeem,
        on_status_change=lambda s: print(f"Status: {s}"),
    )
    logger.info("Listening for '%s' redemptions on #%s (Ctrl+C to stop)...", cfg.reward_name, cfg.channel_name)
    await listener.run()


async def run_app(cfg: Config) -> None:
    tray = TrayApp(
        config_url=f"http://localhost:{cfg.port}/config",
        log_path=str(LOG_PATH),
        on_exit=lambda: os._exit(0),
    )
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    logger.info("Starting TTS server...")
    tts_module.load_model(progress_callback=lambda m: logger.info("TTS: %s", m))
    logger.info("Model ready.")

    queue_mgr = QueueManager(config=cfg, on_overlay_event=broadcast)

    listener = TwitchListener(
        token=cfg.twitch_token,
        client_id=cfg.twitch_client_id,
        channel_name=cfg.channel_name,
        reward_name=cfg.reward_name,
        on_redemption=queue_mgr.enqueue,
        on_status_change=tray.set_status,
    )

    server_cfg = uvicorn.Config(
        overlay_app, host="127.0.0.1", port=cfg.port, log_level="warning"
    )
    server = uvicorn.Server(server_cfg)

    logger.info("ShimaTTS running on http://localhost:%d", cfg.port)
    await asyncio.gather(server.serve(), listener.run(), queue_mgr.run())


def _open_config_after_delay(url: str, delay: float = 1.0) -> None:
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    args = parse_args()
    cfg = load_config()

    if args.tts_server:
        from src.tts_server import run as run_tts_server
        run_tts_server()
        return

    if args.test_tts:
        if not cfg.voice_sample:
            print("Error: voice_sample not configured. Run without flags to open config.")
            sys.exit(1)
        asyncio.run(_run_test_tts(args.test_tts, cfg))
        return

    if args.test_overlay:
        asyncio.run(_run_test_overlay(cfg))
        return

    if args.test_twitch:
        if not cfg.is_complete():
            print("Error: config incomplete. Run without flags to open config.")
            sys.exit(1)
        asyncio.run(_run_test_twitch(cfg))
        return

    if not cfg.is_complete():
        logger.info("Config incomplete - opening setup page.")
        server_cfg = uvicorn.Config(
            overlay_app, host="127.0.0.1", port=cfg.port, log_level="warning"
        )
        server = uvicorn.Server(server_cfg)
        _open_config_after_delay(f"http://localhost:{cfg.port}/config")
        asyncio.run(server.serve())
        return

    asyncio.run(run_app(cfg))


if __name__ == "__main__":
    main()
