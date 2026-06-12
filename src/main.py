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

from src.config import Config, app_home, load_config, save_config
from src.queue_manager import QueueManager
from src.twitch import TwitchListener
from src.overlay.server import app as overlay_app, broadcast, set_app_server, set_setup_server
from src.tray import TrayApp
import src.tts as tts_module

_EXE_DIR = app_home()
LOG_PATH = _EXE_DIR / "ShimaTTS.log"

if (_EXE_DIR / "ffmpeg.exe").exists():
    import pydub
    pydub.AudioSegment.converter = str(_EXE_DIR / "ffmpeg.exe")
    pydub.AudioSegment.ffprobe = str(_EXE_DIR / "ffprobe.exe")

_log_handlers: list[logging.Handler] = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
if sys.stdout is not None:
    _log_handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_log_handlers,
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ShimaTTS - Local Twitch TTS alerts")
    p.add_argument("--test-tts", metavar="MESSAGE", help="Generate and play TTS without Twitch")
    p.add_argument("--test-overlay", action="store_true", help="Fire a fake redemption in OBS")
    p.add_argument("--test-twitch", action="store_true", help="Connect and print redemptions without TTS")
    p.add_argument("--smoke", action="store_true", help="Import every runtime dependency and exit (build verification)")
    return p.parse_args()


_SMOKE_MODULES = (
    "torch", "torchaudio", "f5_tts.api", "vocos", "soundfile", "sounddevice",
    "pydub", "librosa", "transformers", "scipy", "matplotlib",
    "fastapi", "uvicorn", "websockets", "requests", "pystray", "PIL",
    "tkinter", "tkinter.filedialog",
)


def _run_smoke() -> int:
    import importlib
    from src.f5tts_stubs import install as _install_stubs
    _install_stubs()
    failures = []
    modules = _SMOKE_MODULES + (("webview",) if sys.platform == "win32" else ())
    for name in modules:
        try:
            importlib.import_module(name)
            logger.info("smoke ok: %s", name)
        except Exception as e:
            failures.append(f"{name}: {e}")
            logger.error("smoke FAIL: %s: %s", name, e)
    if os.environ.get("SHIMA_HOME"):
        for f in ("ffmpeg.exe", "ffprobe.exe"):
            if not (_EXE_DIR / f).exists():
                failures.append(f"missing bundled binary: {f}")
                logger.error("smoke FAIL: missing bundled binary %s", f)
    static_dir = Path(__file__).parent / "overlay" / "static"
    if not (static_dir / "config.html").exists():
        failures.append("static files missing")
        logger.error("smoke FAIL: static files missing at %s", static_dir)
    if failures:
        logger.error("Smoke test failed: %d problem(s)", len(failures))
        return 1
    logger.info("Smoke test passed: %d modules importable", len(modules))
    return 0


async def _run_test_tts(message: str, cfg: Config) -> None:
    logger.info("Loading model for TTS test...")
    tts_module.load_model(progress_callback=print)
    wav = tts_module.generate(message, cfg.voice_sample, cfg.voice_sample_text)
    from src.audio import play_wav
    logger.info("Playing: %s", message)
    await asyncio.get_running_loop().run_in_executor(None, play_wav, wav)
    os.unlink(wav)


async def _run_test_overlay(cfg: Config) -> None:
    server_cfg = uvicorn.Config(overlay_app, host="127.0.0.1", port=cfg.port, log_level="warning", log_config=None)
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
        client_id=cfg.client_id,
        channel_name=cfg.channel_name,
        reward_name=cfg.reward_name,
        on_redemption=on_redeem,
        on_status_change=lambda s: print(f"Status: {s}"),
    )
    logger.info("Listening for '%s' redemptions on #%s (Ctrl+C to stop)...", cfg.reward_name, cfg.channel_name)
    await listener.run()


async def run_app(cfg: Config, tray: TrayApp) -> None:
    queue_mgr = QueueManager(config=cfg, on_overlay_event=broadcast)

    listener = TwitchListener(
        token=cfg.twitch_token,
        client_id=cfg.client_id,
        channel_name=cfg.channel_name,
        reward_name=cfg.reward_name,
        on_redemption=queue_mgr.enqueue,
        on_status_change=tray.set_status,
    )

    server_cfg = uvicorn.Config(
        overlay_app, host="127.0.0.1", port=cfg.port, log_level="warning", log_config=None,
    )
    server = uvicorn.Server(server_cfg)
    set_app_server(server)

    async def model_then_twitch():
        loop = asyncio.get_running_loop()
        logger.info("Loading TTS model...")
        await loop.run_in_executor(
            None, lambda: tts_module.load_model(progress_callback=lambda m: logger.info("TTS: %s", m))
        )
        try:
            await loop.run_in_executor(
                None, lambda: tts_module.warmup(cfg.voice_sample, cfg.voice_sample_text)
            )
        except Exception:
            logger.exception("TTS warmup failed - first redeem will be slower")
        logger.info("Model ready.")
        await asyncio.gather(listener.run(), queue_mgr.run())

    logger.info("ShimaTTS running on http://localhost:%d", cfg.port)
    worker = asyncio.create_task(model_then_twitch())
    # If the Twitch/TTS side dies, stop serving so the failure surfaces here
    worker.add_done_callback(lambda t: setattr(server, "should_exit", True))
    try:
        await server.serve()
    finally:
        set_app_server(None)
    if worker.done():
        worker.result()
    else:
        # Logout: drop the listener that still holds the revoked token
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


def _open_config_after_delay(url: str, delay: float = 1.0) -> None:
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()


def _supervisor(tray: TrayApp, open_browser: bool) -> None:
    opened = False
    while True:
        cfg = load_config()
        if cfg.is_complete():
            asyncio.run(run_app(cfg, tray))
            logger.info("Logged out - returning to setup mode.")
            tray.set_status("Logged out")
            continue
        logger.info("Config incomplete - starting in setup mode.")
        server_cfg = uvicorn.Config(
            overlay_app, host="127.0.0.1", port=cfg.port, log_level="warning", log_config=None,
        )
        server = uvicorn.Server(server_cfg)
        set_setup_server(server)
        if open_browser and not opened:
            _open_config_after_delay(f"http://localhost:{cfg.port}/config")
            opened = True
        asyncio.run(server.serve())
        set_setup_server(None)


_window_icon = None


def _prepare_webview():
    """Fully load pywebview, the .NET/WebView2 backend AND System.Drawing
    BEFORE any torch import starts. Loading CLR assemblies concurrently with
    torch's C extensions deadlocks on the Windows loader lock."""
    if sys.platform != "win32":
        return None
    try:
        import webview
        import webview.platforms.winforms  # noqa: F401 - forces CLR load now
    except Exception as e:
        logger.info("pywebview unavailable (%s) - using browser instead", e)
        return None
    try:
        ico = Path(__file__).parent / "overlay" / "static" / "icon.ico"
        if ico.exists():
            import clr
            clr.AddReference("System.Drawing")
            from System.Drawing import Icon
            globals()["_window_icon"] = Icon(str(ico))
    except Exception:
        logger.exception("Could not preload window icon")
    return webview


_SPLASH_HTML = """
<html><body style="background:#0e0d0b;color:#b5a795;display:flex;align-items:center;
justify-content:center;height:95vh;font-family:'Trebuchet MS','Segoe UI',sans-serif;
font-size:17px;font-weight:600">Starting ShimaTTS...</body></html>
"""


def _wait_for_port(url: str, timeout_s: float = 30.0) -> bool:
    import socket
    from urllib.parse import urlparse
    parsed = urlparse(url)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((parsed.hostname, parsed.port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _port_in_use(port: int) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.8):
            return True
    except OSError:
        return False


def _run_window(webview, url: str, on_gui_ready, hide_on_close: bool = True) -> bool:
    """Open the config UI in a native window. Blocks until the GUI loop ends."""
    window = webview.create_window(
        "ShimaTTS", html=_SPLASH_HTML, width=1320, height=900, min_size=(720, 600),
    )

    def on_closing():
        if not hide_on_close:
            return True
        window.hide()
        logger.info("Window hidden - ShimaTTS keeps running in the tray.")
        return False

    def gui_ready():
        # Assign the preloaded icon BEFORE the supervisor starts importing
        # torch - mixing CLR work with those imports deadlocks the process.
        # WinForms only allows UI changes from its own thread, so post the
        # assignment there with BeginInvoke instead of setting it directly
        # (a direct cross-thread set blocks this thread forever).
        if _window_icon is not None:
            try:
                from System import Action
                for _ in range(100):
                    native = window.native
                    if native is not None and native.IsHandleCreated:
                        native.BeginInvoke(Action(lambda: setattr(native, "Icon", _window_icon)))
                        break
                    time.sleep(0.05)
                else:
                    logger.warning("Window handle never appeared - icon not set")
            except Exception:
                logger.exception("Could not set window icon")
        on_gui_ready()
        if _wait_for_port(url):
            window.load_url(url)
        else:
            logger.error("Server did not come up within 30s - check the log.")

    window.events.closing += on_closing
    globals()["_webview_window"] = window
    try:
        webview.start(func=gui_ready)
    except Exception:
        logger.exception("webview failed to start - using browser instead")
        globals()["_webview_window"] = None
        return False
    return True


_webview_window = None


def _show_window_or_browser(url: str) -> None:
    win = _webview_window
    if win is not None:
        try:
            win.show()
            return
        except Exception:
            logger.exception("Could not show window, opening browser")
    webbrowser.open(url)


def _seed_default_media() -> None:
    """First run: copy the bundled starter voice/GIF into data/ so the
    libraries aren't empty before the user uploads anything."""
    defaults = _EXE_DIR / "defaults"
    data = _EXE_DIR / "data"
    if data.exists() or not defaults.is_dir():
        return
    import shutil
    data.mkdir(parents=True)
    for f in defaults.iterdir():
        if f.is_file():
            shutil.copy2(f, data / f.name)
            logger.info("Seeded default media: %s", f.name)


def main() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JiroDavid.ShimaTTS")
        except Exception:
            pass

    args = parse_args()
    cfg = load_config()
    _seed_default_media()

    if args.smoke:
        sys.exit(_run_smoke())

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

    config_url = f"http://localhost:{cfg.port}/config"

    if _port_in_use(cfg.port):
        # Another ShimaTTS already owns the port: don't spawn a second app,
        # just open a window onto the running instance and exit when closed
        logger.info("ShimaTTS is already running - opening its window instead.")
        webview = _prepare_webview()
        if webview is None or not _run_window(webview, config_url, lambda: None, hide_on_close=False):
            webbrowser.open(config_url)
        return

    tray = TrayApp(
        config_url=config_url,
        log_path=str(LOG_PATH),
        on_exit=lambda: os._exit(0),
        on_open_config=lambda: _show_window_or_browser(config_url),
    )
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    supervisor = threading.Thread(target=_supervisor, args=(tray, False), daemon=True)
    started = threading.Event()

    def start_supervisor():
        if not started.is_set():
            started.set()
            supervisor.start()

    webview = _prepare_webview()
    if webview is not None and _run_window(webview, config_url, start_supervisor):
        # Window was destroyed but the app lives on in the tray
        supervisor.join()
        return

    # No native window: browser-based flow
    start_supervisor()
    if not cfg.is_complete():
        _open_config_after_delay(config_url)
    supervisor.join()


if __name__ == "__main__":
    main()
