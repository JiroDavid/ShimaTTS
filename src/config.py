import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Config:
    twitch_token: str = ""
    twitch_client_id: str = ""
    channel_name: str = ""
    reward_name: str = ""
    voice_sample: str = ""
    overlay_gif: str = ""
    max_message_length: int = 200
    port: int = 7878

    def __post_init__(self):
        self.max_message_length = int(self.max_message_length)
        self.port = int(self.port)

    def is_complete(self) -> bool:
        return all([
            self.twitch_token,
            self.twitch_client_id,
            self.channel_name,
            self.reward_name,
            self.voice_sample,
            self.overlay_gif,
        ])


def config_path() -> Path:
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
    return base / "config.json"


def load_config() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return Config()
    valid_keys = Config.__dataclass_fields__.keys()
    return Config(**{k: v for k, v in data.items() if k in valid_keys})


def save_config(cfg: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(cfg), f, indent=2)
