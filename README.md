<div align="center">
  <img src="assets/logo.svg" alt="ShimaTTS" width="160" height="160"/>

  <h1>ShimaTTS</h1>
  <p><strong>Local Twitch TTS alerts with AI voice cloning - no cloud, no subscriptions</strong></p>

  [![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
  [![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](#installation)
  [![Twitch](https://img.shields.io/badge/Twitch-Channel%20Points-9146FF?style=flat-square&logo=twitch&logoColor=white)](https://twitch.tv)
  [![OBS](https://img.shields.io/badge/OBS-Browser%20Source-302E31?style=flat-square&logo=obsstudio&logoColor=white)](https://obsproject.com)
  [![GPU](https://img.shields.io/badge/CUDA-Required-76B900?style=flat-square&logo=nvidia&logoColor=white)](#requirements)
  [![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

Channel point redeems trigger an AI TTS alert in OBS. Your viewer types a message, ShimaTTS speaks it in a cloned voice, and an animated overlay appears on stream - GIF on top, username and message below. Runs entirely on your machine using XTTS v2 on your GPU.

## Features

- **AI Voice Cloning** - Clone any voice from a 6-30 second audio sample (XTTS v2)
- **Animated OBS Overlay** - Transparent browser source with your GIF + viewer name + message
- **Twitch Channel Points** - Listens to a specific reward via EventSub WebSocket
- **TTS Queue** - Multiple redemptions play one at a time, no audio overlap
- **Content Filtering** - TOS blocklist (hate speech/slurs) + configurable message length cap
- **Web Config UI** - Browser-based setup page, saves to local `config.json`
- **System Tray** - Runs quietly in the background with live connection status

## Requirements

- Windows 10 / 11
- Nvidia GPU with CUDA (8GB+ VRAM recommended, tested on RTX 3060)
- [OBS Studio](https://obsproject.com)
- ~2GB free disk space (for the XTTS v2 model, downloaded on first run)

## Installation

1. Grab the latest `ShimaTTS.zip` from [Releases](https://github.com/JiroDavid/ShimaTTS/releases)
2. Extract it anywhere (e.g. `C:\ShimaTTS\`)
3. Run `ShimaTTS.exe`
4. A config page opens in your browser - fill in your credentials, voice sample path, and GIF path
5. Click **Save & Start** - the XTTS v2 model downloads automatically (~1.8GB, one time only)

> First launch takes a few minutes while the model downloads and warms up. After that, startup is ~5 seconds.

## OBS Setup

This is the only manual step - takes about 30 seconds:

1. In OBS, add a **Browser Source** to your scene
2. URL: `http://localhost:7878/overlay`
3. Width/Height: match your canvas (e.g. `1920` x `1080`)
4. Enable **Refresh browser when scene becomes active**
5. Leave background transparent (default)

The overlay is fully transparent - it floats over your stream and only appears when a redemption fires.

## Voice Sample Tips

| | Recommendation |
|---|---|
| **Length** | 10-30 seconds |
| **Format** | WAV or MP3 |
| **Content** | Clear speech, no background music or reverb |
| **Mic distance** | Close-mic for best clone quality |

## Configuration

Settings are saved in `config.json` next to the exe. You can edit it directly or reopen the config page from the system tray.

| Key | Description | Default |
|---|---|---|
| `twitch_token` | OAuth token ([get one here](https://twitchtokengenerator.com)) | - |
| `channel_name` | Your Twitch username | - |
| `reward_name` | Exact name of the channel point reward to watch | - |
| `voice_sample` | Path to your voice sample file (WAV/MP3) | - |
| `overlay_gif` | Path to the GIF shown in the alert | - |
| `max_message_length` | Max characters before a message is trimmed | `200` |
| `port` | Local server port | `7878` |

## Testing

Before going live, you can test everything without Twitch:

**Test TTS generation**
```
ShimaTTS.exe --test-tts "Hello chat, this is a test message"
```
Generates audio and plays it immediately. No Twitch connection needed.

**Test the overlay**
```
ShimaTTS.exe --test-overlay
```
Fires a fake redemption alert in OBS so you can check positioning and timing without touching your channel points.

**Test Twitch connection**
```
ShimaTTS.exe --test-twitch
```
Connects to EventSub and prints incoming redemption events to console without generating TTS - useful for confirming your reward name is correct.

## vs. Other TTS Tools

| | ShimaTTS | StreamElements TTS | ElevenLabs | Amazon Polly |
|---|:---:|:---:|:---:|:---:|
| **Voice cloning** | Yes | No | Yes (paid) | No |
| **Runs locally** | Yes | No | No | No |
| **Cost** | Free | Free | $5-$99/mo | Pay-per-use |
| **Privacy** | Full - no data leaves your PC | Messages sent to cloud | Messages sent to cloud | Messages sent to cloud |
| **Custom GIF overlay** | Yes | Limited | No | No |
| **Latency** | ~1-3s (GPU) | ~0.5s | ~1-2s | ~0.5s |
| **Voice quality** | High (XTTS v2) | Robotic | Very High | Good |
| **Channel points native** | Yes | Yes | No | No |
| **Setup difficulty** | One-time download | Instant | API key | API key |

ShimaTTS trades a slightly higher first-run setup cost for complete privacy, zero ongoing cost, and a voice that actually sounds like someone you chose.

## License

MIT - do whatever you want with it.
