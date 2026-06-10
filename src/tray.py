import logging
import os
import threading
import webbrowser
from typing import Callable

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

_STATUS_COLORS = {
    "starting":     (100, 100, 200),
    "connected":    (0,   200, 80),
    "reconnecting": (255, 200, 0),
    "error":        (220, 50,  50),
}


def _make_icon_image(status: str) -> Image.Image:
    color = _STATUS_COLORS.get(status, (120, 120, 120))
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color)
    return img


class TrayApp:
    def __init__(self, config_url: str, log_path: str, on_exit: Callable[[], None]):
        self.config_url = config_url
        self.log_path = log_path
        self.on_exit = on_exit
        self._icon: pystray.Icon | None = None

    def run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Open Config", self._open_config),
            pystray.MenuItem("View Logs", self._view_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._exit),
        )
        self._icon = pystray.Icon(
            "ShimaTTS",
            _make_icon_image("starting"),
            "ShimaTTS - Starting",
            menu,
        )
        self._icon.run()

    def set_status(self, status: str) -> None:
        if self._icon is None:
            return
        self._icon.icon = _make_icon_image(status)
        self._icon.title = f"ShimaTTS - {status.replace('_', ' ').title()}"

    def _open_config(self, icon=None, item=None) -> None:
        webbrowser.open(self.config_url)

    def _view_logs(self, icon=None, item=None) -> None:
        if hasattr(os, 'startfile'):
            os.startfile(self.log_path)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", self.log_path])

    def _exit(self, icon=None, item=None) -> None:
        if self._icon:
            self._icon.stop()
        self.on_exit()
