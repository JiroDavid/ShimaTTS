# ShimaTTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Windows app that listens for Twitch channel point redemptions and plays an AI TTS alert (XTTS v2 voice cloning) via an OBS browser source overlay, packaged as a `.exe`.

**Architecture:** One Python process runs six asyncio components: a Twitch EventSub WebSocket listener, a content filter + queue, an XTTS v2 TTS generator (CUDA), an audio player, a FastAPI overlay server (OBS browser source at `localhost:7878`), and a pystray system tray. Components communicate via an in-process `asyncio.Queue`. PyInstaller `--onedir` produces the `.exe`.

**Tech Stack:** Python 3.11, XTTS v2 (`TTS` / coqui), FastAPI + uvicorn, websockets, sounddevice, pystray, Pillow, better-profanity, PyInstaller

**Spec clarification:** The Twitch Helix API requires both an OAuth user token and an app Client-ID. A `twitch_client_id` field is added to config — users register a free app at dev.twitch.tv to get one.

---

## File Structure

```
ShimaTTS/
├── src/
│   ├── __init__.py
│   ├── main.py              # entry point, CLI flags, app bootstrap
│   ├── config.py            # Config dataclass, load/save
│   ├── filter.py            # message length + profanity filtering
│   ├── tts.py               # XTTS v2 model load + inference
│   ├── audio.py             # WAV playback via sounddevice
│   ├── twitch.py            # Twitch EventSub WebSocket listener
│   ├── queue_manager.py     # asyncio queue, orchestrates filter→tts→audio
│   ├── tray.py              # pystray system tray
│   └── overlay/
│       ├── __init__.py
│       ├── server.py        # FastAPI app (overlay + config + WebSocket)
│       └── static/
│           ├── overlay.html
│           ├── overlay.css
│           ├── overlay.js
│           ├── config.html
│           ├── config.css
│           └── config.js
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_filter.py
│   ├── test_tts.py
│   ├── test_audio.py
│   ├── test_twitch.py
│   ├── test_queue_manager.py
│   └── test_overlay_server.py
├── requirements.txt
├── requirements-dev.txt
├── build.py                 # PyInstaller build script
├── .github/
│   └── workflows/
│       └── build.yml        # Windows exe build on release tag
├── assets/
│   └── logo.svg
├── docs/
│   ├── design.md
│   └── plans/
│       └── 2026-06-10-shimatts-implementation.md
└── README.md
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create requirements.txt**

```
TTS>=0.22.0
torch>=2.1.0
torchaudio>=2.1.0
fastapi>=0.110.0
uvicorn>=0.29.0
websockets>=12.0
better-profanity>=0.7.0
sounddevice>=0.4.6
numpy>=1.26.0
pystray>=0.19.5
Pillow>=10.2.0
requests>=2.31.0
```

- [ ] **Step 2: Create requirements-dev.txt**

```
pytest>=8.1.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

- [ ] **Step 3: Create empty init files**

`src/__init__.py` and `tests/__init__.py` — both empty files.

- [ ] **Step 4: Create tests/conftest.py**

```python
import pytest
from src.config import Config


@pytest.fixture
def basic_config():
    return Config(
        twitch_token="test_token",
        twitch_client_id="test_client_id",
        channel_name="testchannel",
        reward_name="TTS",
        voice_sample="/test/voice.wav",
        overlay_gif="/test/shima.gif",
    )
```

- [ ] **Step 5: Install dev dependencies**

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/WSL2
pip install -r requirements-dev.txt
```

Expected: installs pytest and httpx without errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt src/__init__.py tests/__init__.py tests/conftest.py
git commit -m "feat: project scaffold, requirements, test fixtures"
```

---

## Task 2: Config Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.config import Config, load_config, save_config


def test_config_defaults():
    cfg = Config()
    assert cfg.max_message_length == 200
    assert cfg.port == 7878
    assert cfg.twitch_token == ""


def test_is_complete_false_when_fields_empty():
    assert Config().is_complete() is False


def test_is_complete_true_when_all_fields_set(basic_config):
    assert basic_config.is_complete() is True


def test_save_and_load_roundtrip(tmp_path, basic_config):
    config_file = tmp_path / "config.json"
    with patch("src.config.config_path", return_value=config_file):
        save_config(basic_config)
        loaded = load_config()
    assert loaded.twitch_token == "test_token"
    assert loaded.twitch_client_id == "test_client_id"
    assert loaded.channel_name == "testchannel"
    assert loaded.port == 7878


def test_load_returns_defaults_when_file_missing(tmp_path):
    with patch("src.config.config_path", return_value=tmp_path / "missing.json"):
        cfg = load_config()
    assert cfg.twitch_token == ""
    assert cfg.max_message_length == 200


def test_save_writes_valid_json(tmp_path, basic_config):
    config_file = tmp_path / "config.json"
    with patch("src.config.config_path", return_value=config_file):
        save_config(basic_config)
    data = json.loads(config_file.read_text())
    assert data["channel_name"] == "testchannel"
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Implement src/config.py**

```python
import json
import os
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
    exe_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
    return exe_dir / "config.json"


def load_config() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    with open(path) as f:
        data = json.load(f)
    valid_keys = Config.__dataclass_fields__.keys()
    return Config(**{k: v for k, v in data.items() if k in valid_keys})


def save_config(cfg: Config) -> None:
    path = config_path()
    with open(path, "w") as f:
        json.dump(asdict(cfg), f, indent=2)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_config.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: config module with load/save and completeness check"
```

---

## Task 3: Content Filter

**Files:**
- Create: `src/filter.py`
- Create: `tests/test_filter.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_filter.py
import pytest
from src.filter import is_allowed


def test_allows_clean_message():
    assert is_allowed("hello chat, how are you", 200) is True


def test_rejects_message_over_limit():
    assert is_allowed("a" * 201, 200) is False


def test_allows_message_at_exact_limit():
    assert is_allowed("a" * 200, 200) is True


def test_allows_adult_language():
    assert is_allowed("holy shit that was insane", 200) is True


def test_allows_anatomical_terms():
    assert is_allowed("penis and vagina are medical terms", 200) is True


def test_rejects_racial_slur():
    # better-profanity blocks this by default
    assert is_allowed("you fucking n*gger", 200) is False


def test_rejects_hate_speech_phrase():
    assert is_allowed("kill all jews", 200) is False


def test_rejects_homophobic_slur():
    assert is_allowed("stop being such a f*ggot", 200) is False


def test_allows_empty_message():
    assert is_allowed("", 200) is True


def test_custom_length_limit():
    assert is_allowed("hi", 5) is True
    assert is_allowed("hello world", 5) is False
```

Note: slurs are obfuscated above for readability — the actual test strings should use the real words so better-profanity can detect them. Update the strings in `test_rejects_racial_slur` and `test_rejects_homophobic_slur` with the unobfuscated words when implementing.

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_filter.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.filter'`

- [ ] **Step 3: Install better-profanity**

```bash
pip install better-profanity
```

- [ ] **Step 4: Implement src/filter.py**

```python
from better_profanity import profanity

# Whitelist common adult language — block only TOS-tier slurs and hate speech
_WHITELIST = [
    "sex", "sexy", "sexual", "penis", "vagina", "boob", "boobs",
    "butt", "ass", "arse", "fuck", "fucking", "fucked", "shit",
    "damn", "bitch", "crap", "hell", "piss", "cock", "dick",
    "pussy", "bastard", "whore", "slut", "horny",
]

profanity.load_censor_words(whitelist=_WHITELIST)


def is_allowed(message: str, max_length: int) -> bool:
    if len(message) > max_length:
        return False
    if profanity.contains_profanity(message):
        return False
    return True
```

- [ ] **Step 5: Run tests — expect pass**

```bash
pytest tests/test_filter.py -v
```

Expected: all 10 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/filter.py tests/test_filter.py
git commit -m "feat: content filter with TOS-tier blocklist and length cap"
```

---

## Task 4: TTS Generator

**Files:**
- Create: `src/tts.py`
- Create: `tests/test_tts.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tts.py
import os
import pytest
from unittest.mock import MagicMock, patch


def test_generate_calls_tts_to_file(tmp_path):
    mock_tts_instance = MagicMock()
    mock_tts_instance.tts_to_file.return_value = None

    with patch("src.tts._tts", mock_tts_instance):
        import src.tts as tts_mod
        tts_mod._tts = mock_tts_instance

        # tts_to_file writes a file; simulate that
        out_wav = str(tmp_path / "out.wav")
        def fake_tts_to_file(**kwargs):
            open(kwargs["file_path"], "w").close()
        mock_tts_instance.tts_to_file.side_effect = fake_tts_to_file

        result = tts_mod.generate("hello world", "/voice.wav")
        assert result.endswith(".wav")
        assert os.path.exists(result)

        mock_tts_instance.tts_to_file.assert_called_once()
        call_kwargs = mock_tts_instance.tts_to_file.call_args.kwargs
        assert call_kwargs["text"] == "hello world"
        assert call_kwargs["speaker_wav"] == "/voice.wav"
        assert call_kwargs["language"] == "en"


def test_generate_raises_when_model_not_loaded():
    import src.tts as tts_mod
    original = tts_mod._tts
    tts_mod._tts = None
    try:
        with pytest.raises(RuntimeError, match="Model not loaded"):
            tts_mod.generate("hello", "/voice.wav")
    finally:
        tts_mod._tts = original


def test_is_loaded_false_before_load():
    import src.tts as tts_mod
    original = tts_mod._tts
    tts_mod._tts = None
    try:
        assert tts_mod.is_loaded() is False
    finally:
        tts_mod._tts = original


def test_is_loaded_true_after_mock_load():
    import src.tts as tts_mod
    original = tts_mod._tts
    tts_mod._tts = MagicMock()
    try:
        assert tts_mod.is_loaded() is True
    finally:
        tts_mod._tts = original
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_tts.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.tts'`

- [ ] **Step 3: Implement src/tts.py**

```python
import logging
import os
import tempfile
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
_MODELS_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ShimaTTS" / "models"
)

_tts = None


def load_model(progress_callback: Optional[Callable[[str], None]] = None) -> None:
    global _tts
    from TTS.api import TTS
    import torch

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["COQUI_TOS_AGREED"] = "1"

    use_gpu = torch.cuda.is_available()
    device = "cuda" if use_gpu else "cpu"
    logger.info("Loading XTTS v2 on %s", device)

    if progress_callback:
        progress_callback(f"Loading XTTS v2 model on {device} (~1.8GB on first run)...")

    _tts = TTS(model_name=MODEL_NAME, gpu=use_gpu, progress_bar=True)

    if progress_callback:
        progress_callback("Model ready.")


def generate(text: str, voice_sample: str) -> str:
    if _tts is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name

    _tts.tts_to_file(
        text=text,
        speaker_wav=voice_sample,
        language="en",
        file_path=out_path,
    )
    return out_path


def is_loaded() -> bool:
    return _tts is not None
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_tts.py -v
```

Expected: 4 tests pass. (No TTS model download needed — model is mocked.)

- [ ] **Step 5: Commit**

```bash
git add src/tts.py tests/test_tts.py
git commit -m "feat: XTTS v2 TTS generator with CUDA support"
```

---

## Task 5: Audio Player

**Files:**
- Create: `src/audio.py`
- Create: `tests/test_audio.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audio.py
import asyncio
import struct
import wave
import pytest
from unittest.mock import patch, MagicMock


def make_test_wav(path: str, duration_ms: int = 500, rate: int = 22050) -> None:
    n_frames = int(rate * duration_ms / 1000)
    with wave.open(path, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"\x00\x00" * n_frames)


def test_get_wav_duration_ms(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    make_test_wav(wav_path, duration_ms=500)

    from src.audio import get_wav_duration_ms
    duration = get_wav_duration_ms(wav_path)
    assert 480 <= duration <= 520  # within 20ms tolerance


def test_play_wav_calls_sounddevice(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    make_test_wav(wav_path)

    with patch("src.audio.sd") as mock_sd:
        from src.audio import play_wav
        play_wav(wav_path)
        mock_sd.play.assert_called_once()
        mock_sd.wait.assert_called_once()


@pytest.mark.asyncio
async def test_play_with_notify_calls_on_start(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    make_test_wav(wav_path, duration_ms=200)

    notified_duration = []

    async def on_start(duration_ms: int) -> None:
        notified_duration.append(duration_ms)

    with patch("src.audio.sd"):
        from src.audio import play_with_notify
        await play_with_notify(wav_path, on_start)

    assert len(notified_duration) == 1
    assert notified_duration[0] > 0
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_audio.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.audio'`

- [ ] **Step 3: Install sounddevice**

```bash
pip install sounddevice numpy
```

- [ ] **Step 4: Implement src/audio.py**

```python
import asyncio
import wave
from typing import Awaitable, Callable

import numpy as np
import sounddevice as sd


def get_wav_duration_ms(wav_path: str) -> int:
    with wave.open(wav_path, "r") as f:
        return int(f.getnframes() / f.getframerate() * 1000)


def play_wav(wav_path: str) -> None:
    with wave.open(wav_path, "r") as f:
        rate = f.getframerate()
        channels = f.getnchannels()
        raw = f.readframes(f.getnframes())

    data = np.frombuffer(raw, dtype=np.int16)
    if channels == 2:
        data = data.reshape(-1, 2)

    sd.play(data, samplerate=rate)
    sd.wait()


async def play_with_notify(
    wav_path: str, on_start: Callable[[int], Awaitable[None]]
) -> None:
    duration_ms = get_wav_duration_ms(wav_path)
    await on_start(duration_ms)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, play_wav, wav_path)
```

- [ ] **Step 5: Add pytest-asyncio config to pyproject.toml or pytest.ini**

Create `pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 6: Run tests — expect pass**

```bash
pytest tests/test_audio.py -v
```

Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/audio.py tests/test_audio.py pytest.ini
git commit -m "feat: audio player with WAV playback and overlay notification"
```

---

## Task 6: Overlay Static Assets

**Files:**
- Create: `src/overlay/__init__.py`
- Create: `src/overlay/static/overlay.html`
- Create: `src/overlay/static/overlay.css`
- Create: `src/overlay/static/overlay.js`
- Create: `src/overlay/static/config.html`
- Create: `src/overlay/static/config.css`
- Create: `src/overlay/static/config.js`

No unit tests for static assets — they are tested visually via `--test-overlay` in Task 11.

- [ ] **Step 1: Create src/overlay/__init__.py** (empty)

- [ ] **Step 2: Create src/overlay/static/overlay.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ShimaTTS Overlay</title>
  <link rel="stylesheet" href="/static/overlay.css">
</head>
<body>
  <div id="alert" class="alert hidden">
    <img id="gif" src="/overlay-gif" alt="">
    <div id="username"></div>
    <div id="message"></div>
  </div>
  <script src="/static/overlay.js"></script>
</body>
</html>
```

- [ ] **Step 3: Create src/overlay/static/overlay.css**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: transparent;
  font-family: 'Segoe UI', Tahoma, sans-serif;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  height: 100vh;
  padding-bottom: 60px;
}

.alert {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  background: rgba(13, 13, 26, 0.88);
  border: 2px solid rgba(255, 110, 180, 0.55);
  border-radius: 18px;
  padding: 22px 32px;
  max-width: 500px;
  text-align: center;
  animation: slide-in 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.alert.hidden { display: none; }

.alert.fade-out { animation: fade-out 0.6s ease-in forwards; }

#gif {
  max-width: 160px;
  max-height: 160px;
  border-radius: 10px;
}

#username {
  color: #ff6eb4;
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 0.3px;
}

#message {
  color: #f0f0f0;
  font-size: 15px;
  line-height: 1.55;
  word-break: break-word;
}

@keyframes slide-in {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes fade-out {
  from { opacity: 1; transform: translateY(0); }
  to   { opacity: 0; transform: translateY(-10px); }
}
```

- [ ] **Step 4: Create src/overlay/static/overlay.js**

```javascript
const alertEl = document.getElementById('alert');
const gifEl   = document.getElementById('gif');
const userEl  = document.getElementById('username');
const msgEl   = document.getElementById('message');

let hideTimer = null;

function showAlert(username, message, durationMs) {
  if (hideTimer) clearTimeout(hideTimer);

  gifEl.src = '/overlay-gif?' + Date.now(); // bust GIF loop cache
  userEl.textContent = '@' + username;
  msgEl.textContent  = message;

  alertEl.classList.remove('hidden', 'fade-out');

  hideTimer = setTimeout(() => {
    alertEl.classList.add('fade-out');
    setTimeout(() => alertEl.classList.add('hidden'), 650);
  }, durationMs);
}

function connect() {
  const ws = new WebSocket('ws://' + location.host + '/ws');

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    showAlert(data.username, data.message, data.duration_ms);
  };

  ws.onclose = () => setTimeout(connect, 2000);
  ws.onerror = () => ws.close();
}

connect();
```

- [ ] **Step 5: Create src/overlay/static/config.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ShimaTTS Config</title>
  <link rel="stylesheet" href="/static/config.css">
</head>
<body>
  <div class="container">
    <div class="header">
      <img src="/static/logo.svg" alt="ShimaTTS" width="56">
      <div>
        <h1>ShimaTTS</h1>
        <p class="tagline">Local Twitch TTS alerts</p>
      </div>
    </div>

    <div id="status" class="status hidden"></div>

    <form id="config-form">
      <section>
        <h2>Twitch</h2>
        <label>
          OAuth Token
          <a href="https://twitchtokengenerator.com" target="_blank" rel="noopener">(get one)</a>
        </label>
        <input type="password" name="twitch_token" placeholder="oauth:xxxxxxxxxxxxxxxxxx" autocomplete="off">

        <label>
          Client ID
          <a href="https://dev.twitch.tv/console/apps" target="_blank" rel="noopener">(register app)</a>
        </label>
        <input type="text" name="twitch_client_id" placeholder="your app client_id">

        <label>Channel Name (your Twitch username)</label>
        <input type="text" name="channel_name" placeholder="your_username">

        <label>Channel Point Reward Name (exact)</label>
        <input type="text" name="reward_name" placeholder="TTS">
      </section>

      <section>
        <h2>Voice</h2>
        <label>Voice Sample Path (WAV or MP3, 10-30 seconds)</label>
        <input type="text" name="voice_sample" placeholder="C:\Users\you\voice_sample.wav">
      </section>

      <section>
        <h2>Overlay</h2>
        <label>GIF Path</label>
        <input type="text" name="overlay_gif" placeholder="C:\Users\you\shima.gif">
      </section>

      <section>
        <h2>Settings</h2>
        <label>Max Message Length</label>
        <input type="number" name="max_message_length" value="200" min="10" max="500">

        <label>Port</label>
        <input type="number" name="port" value="7878">
      </section>

      <button type="submit">Save &amp; Start</button>
    </form>
  </div>
  <script src="/static/config.js"></script>
</body>
</html>
```

- [ ] **Step 6: Create src/overlay/static/config.css**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: #0d0d1a;
  color: #e0e0e0;
  font-family: 'Segoe UI', Tahoma, sans-serif;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  padding: 40px 16px;
}

.container {
  width: 100%;
  max-width: 560px;
}

.header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

h1 { font-size: 28px; color: #fff; }
.tagline { color: #888; font-size: 13px; margin-top: 2px; }

h2 {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #ff6eb4;
  margin-bottom: 14px;
}

section {
  background: #13132a;
  border: 1px solid #2a2a48;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

label {
  font-size: 13px;
  color: #aaa;
}

label a { color: #a78bfa; text-decoration: none; font-size: 12px; margin-left: 6px; }
label a:hover { text-decoration: underline; }

input {
  width: 100%;
  background: #0d0d1a;
  border: 1px solid #2a2a48;
  border-radius: 8px;
  color: #f0f0f0;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

input:focus { border-color: #ff6eb4; }

button {
  width: 100%;
  background: #ff6eb4;
  color: #0d0d1a;
  border: none;
  border-radius: 10px;
  padding: 14px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s;
  margin-top: 8px;
}

button:hover { opacity: 0.88; }

.status {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 16px;
}

.status.hidden { display: none; }
.status.success { background: #0d2a1a; border: 1px solid #22c55e; color: #86efac; }
.status.error   { background: #2a0d0d; border: 1px solid #ef4444; color: #fca5a5; }
.status.info    { background: #13132a; border: 1px solid #6366f1; color: #a5b4fc; }
```

- [ ] **Step 7: Create src/overlay/static/config.js**

```javascript
async function loadConfig() {
  const res = await fetch('/config/data');
  if (!res.ok) return;
  const cfg = await res.json();
  Object.entries(cfg).forEach(([key, value]) => {
    const input = document.querySelector(`[name="${key}"]`);
    if (input) input.value = value;
  });
}

const form   = document.getElementById('config-form');
const status = document.getElementById('status');

function showStatus(msg, type) {
  status.textContent = msg;
  status.className = `status ${type}`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  showStatus('Saving...', 'info');

  const numericFields = ['max_message_length', 'port'];
  const data = {};
  new FormData(form).forEach((v, k) => {
    data[k] = numericFields.includes(k) ? parseInt(v, 10) : v;
  });

  try {
    const res = await fetch('/config/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (res.ok) {
      showStatus('Saved! ShimaTTS will apply your settings.', 'success');
    } else {
      showStatus('Save failed - check the console.', 'error');
    }
  } catch (err) {
    showStatus('Error: ' + err.message, 'error');
  }
});

loadConfig();
```

- [ ] **Step 8: Copy logo to static**

```bash
cp assets/logo.svg src/overlay/static/logo.svg
```

- [ ] **Step 9: Commit**

```bash
git add src/overlay/ 
git commit -m "feat: overlay HTML/CSS/JS and config UI static assets"
```

---

## Task 7: FastAPI Overlay Server

**Files:**
- Create: `src/overlay/server.py`
- Create: `tests/test_overlay_server.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_overlay_server.py
import json
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_config(basic_config):
    with patch("src.overlay.server.load_config", return_value=basic_config), \
         patch("src.overlay.server.save_config"):
        yield basic_config


@pytest.mark.asyncio
async def test_overlay_route_returns_html(mock_config):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/overlay")
    assert resp.status_code == 200
    assert "ShimaTTS" in resp.text


@pytest.mark.asyncio
async def test_config_page_returns_html(mock_config):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/config")
    assert resp.status_code == 200
    assert "<form" in resp.text


@pytest.mark.asyncio
async def test_config_data_returns_json(mock_config):
    from src.overlay.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/config/data")
    assert resp.status_code == 200
    data = resp.json()
    assert data["channel_name"] == "testchannel"
    assert data["port"] == 7878


@pytest.mark.asyncio
async def test_config_save_writes_config(mock_config, tmp_path):
    from src.overlay.server import app, save_config
    payload = {
        "twitch_token": "newtoken",
        "twitch_client_id": "newclient",
        "channel_name": "newchannel",
        "reward_name": "TTS",
        "voice_sample": "/voice.wav",
        "overlay_gif": "/gif.gif",
        "max_message_length": 150,
        "port": 7878,
    }
    with patch("src.overlay.server.save_config") as mock_save:
        from src.overlay.server import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/config/save", json=payload)
        assert resp.status_code == 200
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_broadcast_sends_to_websocket():
    from src.overlay.server import broadcast, _connections
    mock_ws = MagicMock()

    sent = []
    async def fake_send(payload):
        sent.append(json.loads(payload))

    mock_ws.send_text = fake_send
    _connections.add(mock_ws)
    try:
        await broadcast("viewer1", "hello world", 2000)
    finally:
        _connections.discard(mock_ws)

    assert len(sent) == 1
    assert sent[0]["username"] == "viewer1"
    assert sent[0]["message"] == "hello world"
    assert sent[0]["duration_ms"] == 2000
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_overlay_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.overlay.server'`

- [ ] **Step 3: Install FastAPI + uvicorn**

```bash
pip install fastapi uvicorn httpx
```

- [ ] **Step 4: Implement src/overlay/server.py**

```python
import json
import logging
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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
async def config_save(data: dict):
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
    _connections -= dead
```

- [ ] **Step 5: Run tests — expect pass**

```bash
pytest tests/test_overlay_server.py -v
```

Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/overlay/server.py tests/test_overlay_server.py
git commit -m "feat: FastAPI overlay server with WebSocket broadcast and config routes"
```

---

## Task 8: Twitch EventSub Listener

**Files:**
- Create: `src/twitch.py`
- Create: `tests/test_twitch.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_twitch.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.twitch import get_broadcaster_id, TwitchListener


def test_get_broadcaster_id_returns_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"id": "12345678", "login": "testchannel"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.twitch.requests.get", return_value=mock_resp):
        uid = get_broadcaster_id("token", "client_id", "testchannel")
    assert uid == "12345678"


def test_get_broadcaster_id_raises_for_unknown_channel():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.twitch.requests.get", return_value=mock_resp):
        with pytest.raises(ValueError, match="not found"):
            get_broadcaster_id("token", "client_id", "unknown")


@pytest.mark.asyncio
async def test_listener_calls_on_redemption_for_matching_reward():
    redemptions = []

    listener = TwitchListener(
        token="tok",
        client_id="cid",
        channel_name="chan",
        reward_name="TTS",
        on_redemption=lambda u, m: redemptions.append((u, m)),
        on_status_change=lambda s: None,
    )

    welcome_msg = json.dumps({
        "metadata": {"message_type": "session_welcome"},
        "payload": {"session": {"id": "sess_abc"}},
    })
    redemption_msg = json.dumps({
        "metadata": {"message_type": "notification"},
        "payload": {
            "event": {
                "user_login": "viewer1",
                "user_input": "hello from chat",
                "reward": {"title": "TTS"},
            }
        },
    })

    messages = [welcome_msg, redemption_msg]

    mock_ws = AsyncMock()
    mock_ws.__aiter__ = AsyncMock(return_value=iter(messages))
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=False)

    with patch("src.twitch.get_broadcaster_id", return_value="999"), \
         patch("src.twitch.subscribe_to_redemptions"), \
         patch("src.twitch.websockets.connect", return_value=mock_ws):
        listener._running = True
        try:
            await asyncio.wait_for(listener._connect("999"), timeout=1.0)
        except (StopAsyncIteration, asyncio.TimeoutError):
            pass

    assert len(redemptions) == 1
    assert redemptions[0] == ("viewer1", "hello from chat")


@pytest.mark.asyncio
async def test_listener_ignores_wrong_reward_name():
    redemptions = []

    listener = TwitchListener(
        token="tok",
        client_id="cid",
        channel_name="chan",
        reward_name="TTS",
        on_redemption=lambda u, m: redemptions.append((u, m)),
        on_status_change=lambda s: None,
    )

    wrong_reward_msg = json.dumps({
        "metadata": {"message_type": "notification"},
        "payload": {
            "event": {
                "user_login": "viewer1",
                "user_input": "hi",
                "reward": {"title": "Hydrate"},
            }
        },
    })

    messages = [wrong_reward_msg]
    mock_ws = AsyncMock()
    mock_ws.__aiter__ = AsyncMock(return_value=iter(messages))
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=False)

    with patch("src.twitch.get_broadcaster_id", return_value="999"), \
         patch("src.twitch.subscribe_to_redemptions"), \
         patch("src.twitch.websockets.connect", return_value=mock_ws):
        try:
            await asyncio.wait_for(listener._connect("999"), timeout=1.0)
        except (StopAsyncIteration, asyncio.TimeoutError):
            pass

    assert len(redemptions) == 0
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_twitch.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.twitch'`

- [ ] **Step 3: Install websockets and requests**

```bash
pip install websockets requests
```

- [ ] **Step 4: Implement src/twitch.py**

```python
import asyncio
import json
import logging
from typing import Callable

import requests
import websockets

logger = logging.getLogger(__name__)

EVENTSUB_WS = "wss://eventsub.wss.twitch.tv/ws"
HELIX_SUBS = "https://api.twitch.tv/helix/eventsub/subscriptions"
HELIX_USERS = "https://api.twitch.tv/helix/users"


def get_broadcaster_id(token: str, client_id: str, channel_name: str) -> str:
    resp = requests.get(
        HELIX_USERS,
        params={"login": channel_name},
        headers={"Authorization": f"Bearer {token}", "Client-Id": client_id},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        raise ValueError(f"Channel '{channel_name}' not found on Twitch")
    return data[0]["id"]


def subscribe_to_redemptions(
    token: str, client_id: str, broadcaster_id: str, session_id: str
) -> None:
    resp = requests.post(
        HELIX_SUBS,
        json={
            "type": "channel.channel_points_custom_reward_redemption.add",
            "version": "1",
            "condition": {"broadcaster_user_id": broadcaster_id},
            "transport": {"method": "websocket", "session_id": session_id},
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Client-Id": client_id,
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    resp.raise_for_status()


class TwitchListener:
    def __init__(
        self,
        token: str,
        client_id: str,
        channel_name: str,
        reward_name: str,
        on_redemption: Callable[[str, str], None],
        on_status_change: Callable[[str], None],
    ):
        self.token = token
        self.client_id = client_id
        self.channel_name = channel_name
        self.reward_name = reward_name
        self.on_redemption = on_redemption
        self.on_status_change = on_status_change
        self._running = False

    async def run(self) -> None:
        self._running = True
        broadcaster_id = get_broadcaster_id(
            self.token, self.client_id, self.channel_name
        )
        backoff = 1
        while self._running:
            try:
                self.on_status_change("connected")
                await self._connect(broadcaster_id)
                backoff = 1
            except Exception as e:
                logger.error("Twitch connection error: %s", e)
                self.on_status_change("reconnecting")
                await asyncio.sleep(min(backoff, 60))
                backoff = min(backoff * 2, 60)

    async def _connect(self, broadcaster_id: str) -> None:
        async with websockets.connect(EVENTSUB_WS) as ws:
            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get("metadata", {}).get("message_type")

                if msg_type == "session_welcome":
                    session_id = msg["payload"]["session"]["id"]
                    subscribe_to_redemptions(
                        self.token, self.client_id, broadcaster_id, session_id
                    )

                elif msg_type == "notification":
                    event = msg.get("payload", {}).get("event", {})
                    reward_title = event.get("reward", {}).get("title", "")
                    if reward_title == self.reward_name:
                        username = event.get("user_login", "")
                        text = event.get("user_input", "")
                        if username and text:
                            self.on_redemption(username, text)

    def stop(self) -> None:
        self._running = False
```

- [ ] **Step 5: Run tests — expect pass**

```bash
pytest tests/test_twitch.py -v
```

Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/twitch.py tests/test_twitch.py
git commit -m "feat: Twitch EventSub WebSocket listener with reconnect backoff"
```

---

## Task 9: Queue Manager

**Files:**
- Create: `src/queue_manager.py`
- Create: `tests/test_queue_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_queue_manager.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import Config
from src.queue_manager import QueueManager


@pytest.fixture
def cfg():
    return Config(
        twitch_token="t", twitch_client_id="c",
        channel_name="ch", reward_name="TTS",
        voice_sample="/voice.wav", overlay_gif="/gif.gif",
        max_message_length=200,
    )


@pytest.mark.asyncio
async def test_enqueue_filtered_message_is_dropped(cfg):
    overlay_events = []
    qm = QueueManager(cfg, on_overlay_event=AsyncMock(side_effect=overlay_events.append))
    # "a" * 201 exceeds max_message_length=200
    qm.enqueue("viewer", "a" * 201)
    assert qm._queue.empty()


@pytest.mark.asyncio
async def test_enqueue_clean_message_is_queued(cfg):
    qm = QueueManager(cfg, on_overlay_event=AsyncMock())
    qm.enqueue("viewer", "hello chat")
    assert not qm._queue.empty()
    username, message = qm._queue.get_nowait()
    assert username == "viewer"
    assert message == "hello chat"


@pytest.mark.asyncio
async def test_process_calls_tts_and_audio(cfg, tmp_path):
    fake_wav = str(tmp_path / "out.wav")
    open(fake_wav, "w").close()

    overlay_calls = []

    async def fake_overlay(u, m, d):
        overlay_calls.append((u, m, d))

    qm = QueueManager(cfg, on_overlay_event=fake_overlay)

    async def fake_play(wav, on_start):
        await on_start(1500)

    with patch("src.queue_manager.tts_module.generate", return_value=fake_wav), \
         patch("src.queue_manager.audio.play_with_notify", side_effect=fake_play):
        await qm._process("viewer1", "hello world")

    assert len(overlay_calls) == 1
    assert overlay_calls[0][0] == "viewer1"
    assert overlay_calls[0][1] == "hello world"


@pytest.mark.asyncio
async def test_process_cleans_up_wav_on_error(cfg, tmp_path):
    fake_wav = str(tmp_path / "out.wav")
    open(fake_wav, "w").close()

    qm = QueueManager(cfg, on_overlay_event=AsyncMock())

    with patch("src.queue_manager.tts_module.generate", return_value=fake_wav), \
         patch("src.queue_manager.audio.play_with_notify", new_callable=AsyncMock,
               side_effect=RuntimeError("audio fail")):
        with pytest.raises(RuntimeError):
            await qm._process("viewer1", "oops")

    import os
    assert not os.path.exists(fake_wav)
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_queue_manager.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.queue_manager'`

- [ ] **Step 3: Implement src/queue_manager.py**

```python
import asyncio
import logging
import os
from typing import Callable, Tuple

from src.config import Config
from src.filter import is_allowed
import src.tts as tts_module
import src.audio as audio

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(self, config: Config, on_overlay_event: Callable):
        self.config = config
        self.on_overlay_event = on_overlay_event
        self._queue: asyncio.Queue[Tuple[str, str]] = asyncio.Queue()

    def enqueue(self, username: str, message: str) -> None:
        if not is_allowed(message, self.config.max_message_length):
            logger.info("Filtered message from %s (length=%d)", username, len(message))
            return
        self._queue.put_nowait((username, message))

    async def run(self) -> None:
        while True:
            username, message = await self._queue.get()
            try:
                await self._process(username, message)
            except Exception as e:
                logger.error("TTS processing failed for %s: %s", username, e)
            finally:
                self._queue.task_done()

    async def _process(self, username: str, message: str) -> None:
        loop = asyncio.get_event_loop()
        wav_path = await loop.run_in_executor(
            None, tts_module.generate, message, self.config.voice_sample
        )

        async def on_start(duration_ms: int) -> None:
            await self.on_overlay_event(username, message, duration_ms)

        try:
            await audio.play_with_notify(wav_path, on_start)
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_queue_manager.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/queue_manager.py tests/test_queue_manager.py
git commit -m "feat: queue manager orchestrating filter, TTS, audio, and overlay"
```

---

## Task 10: System Tray

**Files:**
- Create: `src/tray.py`

No unit tests — pystray requires a display and Windows GUI. Tested manually when running the full app.

- [ ] **Step 1: Install pystray and Pillow**

```bash
pip install pystray Pillow
```

- [ ] **Step 2: Implement src/tray.py**

```python
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
        os.startfile(self.log_path)

    def _exit(self, icon=None, item=None) -> None:
        if self._icon:
            self._icon.stop()
        self.on_exit()
```

- [ ] **Step 3: Commit**

```bash
git add src/tray.py
git commit -m "feat: system tray with status indicator and config/log shortcuts"
```

---

## Task 11: Main Entry Point + CLI Flags

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: Implement src/main.py**

```python
import argparse
import asyncio
import json
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

_EXE_DIR = Path(os.path.dirname(os.path.abspath(sys.argv[0])))
LOG_PATH = _EXE_DIR / "ShimaTTS.log"

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
    return p.parse_args()


async def _run_test_tts(message: str, cfg: Config) -> None:
    logger.info("Loading model for TTS test...")
    tts_module.load_model(progress_callback=print)
    wav = tts_module.generate(message, cfg.voice_sample)
    from src.audio import play_wav
    logger.info("Playing: %s", message)
    play_wav(wav)
    os.unlink(wav)


async def _run_test_overlay(cfg: Config) -> None:
    import asyncio
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
    from src.twitch import TwitchListener

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

    logger.info("Loading XTTS v2 model...")
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
        logger.info("Config incomplete — opening setup page.")
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
```

- [ ] **Step 2: Run the full test suite one more time**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 3: Smoke-test the config page manually**

```bash
python -m src.main
```

Expected: browser opens to `http://localhost:7878/config`, the dark-themed config form loads, no errors in terminal.

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat: main entry point with CLI test flags and first-run config flow"
```

---

## Task 12: PyInstaller Packaging + GitHub Actions Build

**Files:**
- Create: `build.py`
- Create: `.github/workflows/build.yml`

**Important:** PyInstaller must run on Windows (not WSL2) to build a Windows `.exe`. Run `build.py` in PowerShell or Windows Terminal after installing Python on Windows.

- [ ] **Step 1: Create build.py**

```python
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
    str(ROOT / "src" / "main.py"),
]

print("Building ShimaTTS.exe...")
result = subprocess.run(cmd, cwd=str(ROOT))
if result.returncode == 0:
    print("\nBuild complete: dist/ShimaTTS/ShimaTTS.exe")
else:
    print("\nBuild failed.")
    sys.exit(1)
```

- [ ] **Step 2: Create a Windows icon**

Convert `assets/logo.svg` to `assets/icon.ico` using an online converter (e.g., convertio.co) or ImageMagick on Windows:
```powershell
magick convert assets/logo.svg -resize 256x256 assets/icon.ico
```

Or use Pillow in Python on Windows:
```python
from PIL import Image
img = Image.open("assets/logo.svg")  # or a PNG render
img.save("assets/icon.ico", format="ICO", sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])
```

Save the resulting `assets/icon.ico` and commit it.

- [ ] **Step 3: Create .github/workflows/build.yml**

```yaml
name: Build Windows EXE

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build exe
        run: python build.py

      - name: Zip dist folder
        run: Compress-Archive -Path dist\ShimaTTS -DestinationPath ShimaTTS.zip

      - name: Upload to release
        uses: softprops/action-gh-release@v2
        with:
          files: ShimaTTS.zip
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 4: Commit**

```bash
git add build.py .github/ assets/icon.ico
git commit -m "feat: PyInstaller build script and GitHub Actions release workflow"
```

- [ ] **Step 5: Push and verify**

```bash
git push
```

To trigger a build: `git tag v0.1.0 && git push --tags`

---

## Manual Test Checklist (run on Windows before tagging a release)

- [ ] `ShimaTTS.exe` opens config page in browser on first run
- [ ] Config saves correctly and `config.json` appears next to the exe
- [ ] `ShimaTTS.exe --test-tts "Hello world"` speaks the message in the cloned voice
- [ ] `ShimaTTS.exe --test-overlay` shows the GIF + text alert in OBS browser source
- [ ] `ShimaTTS.exe --test-twitch` prints redemption events to console
- [ ] A real channel point redemption triggers the full TTS + overlay flow
- [ ] A filtered message (over length limit) is silently dropped
- [ ] Tray icon turns yellow on Twitch disconnect, green when reconnected
- [ ] Right-click tray → Open Config opens the config page
- [ ] Right-click tray → View Logs opens `ShimaTTS.log`
- [ ] Right-click tray → Exit closes the app cleanly
