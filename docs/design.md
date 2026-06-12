# ShimaTTS - Design Spec

**Date:** 2026-06-10
**Status:** Approved

---

## Overview

ShimaTTS is a local Windows application that listens for Twitch channel point redemptions and plays an AI TTS alert in OBS. When a viewer redeems a configured reward with a text message, the app clones a preset voice (defined by the streamer's audio sample) to speak the message, while an OBS browser source overlay animates a GIF and displays the viewer's username and message.

The app runs as a single `.exe` (PyInstaller onedir bundle), sits in the system tray, and requires no cloud services after initial model download.

---

## Architecture

One Python process with five internal components communicating via an in-process asyncio queue:

```
Twitch EventSub (WebSocket)
        |
   [Queue]
        |
   [TTS Generator]  <-- voice sample on disk
        |
   [Audio Player]
        |
   [Overlay Server] <--> OBS Browser Source (localhost:7878)
        |
   [System Tray + Config]
```

---

## Components

### 1. Twitch Listener

- Connects to Twitch EventSub via WebSocket
- Subscribes to `channel.channel_points_custom_reward_redemption.add` for the configured channel and reward name
- On redemption: extracts `user_login` and `user_input`, passes to the TTS queue
- Auto-reconnects with exponential backoff on disconnect; tray icon turns yellow while reconnecting

### 2. TTS Generator

- Engine: **XTTS v2** via the `TTS` library (Coqui fork)
- Model stored in `%LOCALAPPDATA%\ShimaTTS\models\` (~1.8GB, downloaded on first run)
- Voice cloning: `tts.tts_to_file(text, speaker_wav=voice_sample_path, ...)`
- Runs inference on CUDA (RTX 3060, 12GB VRAM); falls back to CPU if CUDA unavailable
- Output: WAV file in a temp directory, handed to Audio Player

### 3. Audio Player

- Plays the generated WAV using `pygame.mixer` or `sounddevice`
- Sends a WebSocket message to the Overlay Server at audio start: `{ "username", "message", "duration_ms" }`
- Waits for playback to complete before dequeuing the next item (enforcing sequential queue)

### 4. Overlay Server

- FastAPI app serving two routes:
  - `GET /overlay` - serves the transparent HTML/JS/CSS overlay page
  - `WebSocket /ws` - pushes TTS events to the OBS browser source
  - `GET /config` - serves the web-based config form
  - `POST /config` - saves config JSON and restarts the Twitch listener
- Overlay page behavior:
  - Idle: fully transparent, nothing visible
  - On event: animates in (GIF + username + message, stacked vertical), stays for `duration_ms`, fades out
  - Layout: GIF centered on top, username in accent color, message text below

### 5. System Tray

- `pystray` tray icon with status colors: green (connected), yellow (reconnecting), red (error)
- Right-click menu: Open Config, View Logs, Exit
- On launch: if no `config.json` exists, auto-opens `http://localhost:7878/config` in the default browser

---

## Data Flow (single redemption)

1. Viewer redeems reward on Twitch
2. EventSub WebSocket fires → Twitch Listener receives event
3. `(username, message)` tuple pushed to asyncio queue
4. TTS Generator picks up from queue, runs XTTS v2 inference (~1-3s on 3060)
5. Audio Player sends overlay event via WebSocket, starts WAV playback
6. OBS browser source receives event, GIF + text animates in and stays for duration
7. Audio finishes → Audio Player signals queue → next item dequeues

---

## Config Schema (`config.json`)

```json
{
  "twitch_token": "",
  "channel_name": "",
  "reward_name": "",
  "voice_sample": "",
  "overlay_gif": "",
  "port": 7878
}
```

Stored in the same directory as the exe. On first run, config page opens automatically if the file doesn't exist or `twitch_token` is empty.

---

## Packaging

- **Tool:** PyInstaller `--onedir` mode
- **Output:** `dist/ShimaTTS/ShimaTTS.exe` + supporting files
- **Model download:** handled at runtime on first launch (not bundled - too large)
- **Distribution:** zip the `dist/ShimaTTS/` folder, upload to GitHub Releases
- **Pinning to taskbar:** works natively - right-click `ShimaTTS.exe` → Pin to taskbar

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Twitch disconnect | Auto-reconnect with backoff, tray turns yellow |
| TTS generation error | Skip item, log to `ShimaTTS.log`, continue queue |
| OBS not open | Overlay events drop after 30s timeout, app keeps running |
| Model not downloaded | Queue blocks, progress shown in config page |

All errors log to `ShimaTTS.log` next to the exe. No crash dialogs or popups during a live stream.

---

## OBS Integration

- OBS adds a Browser Source at `http://localhost:7878/overlay`
- Recommended: 1920x1080, transparent background, refresh on scene activate
- ShimaTTS must be running before OBS loads the source

---

## CLI Test Flags

- `--test-tts "message"` - generate and play TTS without Twitch
- `--test-overlay` - fire a fake redemption alert in OBS
- `--test-twitch` - connect to EventSub and print events without generating TTS
