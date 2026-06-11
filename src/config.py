import json
import os
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path

# Client ID of the registered ShimaTTS Twitch app (public by design, like any
# native OAuth client). Users only override this if they registered their own
# app at dev.twitch.tv. Redirect URL registered for this ID must be
# http://localhost:7878/auth/callback
DEFAULT_TWITCH_CLIENT_ID = "icdpf44rbqxe2dm6q9qk7jqaotv3a4"


@dataclass
class Config:
    twitch_token: str = ""
    twitch_client_id: str = ""
    channel_name: str = ""
    reward_name: str = ""
    voice_sample: str = ""
    voice_sample_text: str = ""
    overlay_gif: str = ""
    tts_template: str = ""
    max_message_words: int = 20
    blocked_words: list = field(default_factory=list)
    port: int = 7878

    def __post_init__(self):
        self.max_message_words = int(self.max_message_words)
        self.port = int(self.port)
        self.blocked_words = [
            str(w).strip().lower() for w in (self.blocked_words or []) if str(w).strip()
        ]
        # Old builds persisted the built-in client id into config.json;
        # treat it as "not customized" so the UI keeps the field hidden
        if self.twitch_client_id == DEFAULT_TWITCH_CLIENT_ID:
            self.twitch_client_id = ""

    @property
    def client_id(self) -> str:
        return self.twitch_client_id or DEFAULT_TWITCH_CLIENT_ID

    def is_complete(self) -> bool:
        return all([
            self.twitch_token,
            self.client_id,
            self.channel_name,
            self.reward_name,
            self.voice_sample,
            self.overlay_gif,
        ])


def app_home() -> Path:
    env = os.environ.get("SHIMA_HOME")
    if env:
        return Path(env)
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def config_path() -> Path:
    return app_home() / "config.json"


def load_config() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return Config()
    valid_keys = Config.__dataclass_fields__.keys()
    return Config(**{k: v for k, v in data.items() if k in valid_keys})


def save_config(cfg: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)
