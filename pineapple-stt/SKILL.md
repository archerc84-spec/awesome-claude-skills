---
name: pineapple-stt
description: A TypeLess-style offline voice dictation tool with a custom wake word. Say "pineapple" (or any keyword you choose), then speak freely — OpenAI Whisper transcribes your speech and types it wherever your cursor is, just like Siri for the desktop. Use this when someone wants offline voice dictation, speech-to-text, a custom wake word, or a hands-free typing tool.
---

# 🍍 Pineapple STT — Voice Dictation with Custom Wake Word

A fully offline, Siri-style speech-to-text tool. Say your wake word, speak freely, and your words appear at your cursor — just like the TypeLess app.

## Quick Start

```bash
# 1. Install system dependencies (Linux / macOS)
bash scripts/setup.sh

# 2. Run — Python packages install automatically on first launch
python3 scripts/pineapple_stt.py
```

## How It Works

1. The app listens continuously for your **wake word** (`pineapple` by default)
2. When detected it plays a rising chime 🎵 and starts recording
3. You speak your dictation — it records until you pause for ~1.5 s
4. [faster-whisper](https://github.com/SYSTRAN/faster-whisper) transcribes your speech fully offline
5. The text is typed at your cursor position automatically

You can also say the wake word **and** your dictation in one breath:
> *"Pineapple send an email to John tomorrow"*  
→ immediately types: `send an email to John tomorrow`

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-k / --keyword` | `pineapple` | Wake word to listen for |
| `-m / --model` | `base` | Whisper model: `tiny` `base` `small` `medium` `large` |
| `--wake-model` | `tiny` | Model used only for wake-word detection |
| `--vad` | `2` | Mic sensitivity 0 (loose) – 3 (strict) |
| `--no-inject` | off | Print transcription only; don't type it |

## Examples

```bash
# Use a different wake word
python3 scripts/pineapple_stt.py -k "computer"

# Higher accuracy dictation
python3 scripts/pineapple_stt.py -m small

# Best quality (larger model, slower first load)
python3 scripts/pineapple_stt.py -m medium --vad 3

# Test / demo mode — shows text without typing anywhere
python3 scripts/pineapple_stt.py --no-inject
```

## Whisper Model Guide

| Model | Download | Speed | Accuracy |
|-------|----------|-------|----------|
| tiny  | 39 MB  | ⚡⚡⚡ | Good |
| base  | 74 MB  | ⚡⚡  | Great ← **default** |
| small | 244 MB | ⚡   | Excellent |
| medium | 769 MB | 🐢  | Near-perfect |

Models download automatically from Hugging Face on first use.

## Text Injection Priority

| Method | When used |
|--------|-----------|
| `xdotool` | X11 (most Linux desktops) |
| `wtype` | Wayland |
| `ydotool` | Wayland fallback |
| clipboard + paste | Universal fallback |

## System Requirements

Installed automatically by `setup.sh`:
- Python 3.8+
- PortAudio (`portaudio19-dev` on Debian/Ubuntu)
- `xdotool` (X11) or `wtype` / `ydotool` (Wayland)

Python packages auto-installed on first run:
`faster-whisper`, `pyaudio`, `webrtcvad-wheels`, `numpy`, `sounddevice`, `pyperclip`, `colorama`, `pynput`
