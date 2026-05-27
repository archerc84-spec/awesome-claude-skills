#!/usr/bin/env python3
"""
🍍 Pineapple STT — Voice Dictation with Custom Wake Word

A TypeLess-style speech-to-text tool.
Say your wake word (default: "pineapple"), speak freely, and your words
are transcribed by OpenAI Whisper and typed wherever your cursor sits.

All Python dependencies install automatically on first run.

Usage:
  python3 pineapple_stt.py                        default (wake: 'pineapple')
  python3 pineapple_stt.py -k banana              custom wake word
  python3 pineapple_stt.py -m small               more accurate transcription
  python3 pineapple_stt.py -m medium --vad 3      max quality
  python3 pineapple_stt.py --no-inject            print only, don't type
"""
from __future__ import annotations

# ── stdlib (always available) ──────────────────────────────────────────────────
import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# AUTO-INSTALL: missing Python packages are installed on first run
# ─────────────────────────────────────────────────────────────────────────────

_DEPS: dict = {
    "pyaudio":        "pyaudio",
    "webrtcvad":      "webrtcvad-wheels",
    "numpy":          "numpy",
    "faster_whisper": "faster-whisper",
    "sounddevice":    "sounddevice",
    "pyperclip":      "pyperclip",
    "colorama":       "colorama",
    "pynput":         "pynput",
}


def _importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _ensure_deps() -> None:
    missing = [pkg for mod, pkg in _DEPS.items() if not _importable(mod)]
    if missing:
        print(f"[setup] Installing: {', '.join(missing)} …")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        )
        print("[setup] Done. Restarting …")
        os.execv(sys.executable, [sys.executable] + sys.argv)


_ensure_deps()

# ── third-party (auto-installed above if needed) ───────────────────────────
import numpy as np                                    # type: ignore
import pyaudio                                         # type: ignore
import webrtcvad                                       # type: ignore
import sounddevice as sd                               # type: ignore
import pyperclip                                       # type: ignore
from colorama import Fore, Back, Style, init as _ci   # type: ignore
from faster_whisper import WhisperModel               # type: ignore
from pynput.keyboard import Key, Controller as _KCtrl # type: ignore

_ci(autoreset=True)


# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════

class Config:
    """All tunable parameters in one place."""
    # ── wake word ──────────────────────────────────────────────────
    wake_word: str          = "pineapple"
    wake_model_size: str    = "tiny"      # tiny is fast enough for kw detection

    # ── dictation ─────────────────────────────────────────────────
    main_model_size: str    = "base"      # base = good accuracy, reasonable speed

    # ── audio / VAD ───────────────────────────────────────────────
    sample_rate: int        = 16_000
    frame_ms: int           = 30          # must be 10, 20, or 30 (webrtcvad req)
    vad_aggressiveness: int = 2           # 0 = permissive … 3 = strict
    pre_roll_frames: int    = 8           # frames buffered before speech onset

    # ── wake-word phase ───────────────────────────────────────────
    wake_silence_sec: float = 0.8         # silence that ends the wake phrase
    wake_max_sec: float     = 5.0         # max length before we give up

    # ── dictation phase ───────────────────────────────────────────
    dict_silence_sec: float = 1.5         # silence that commits the dictation
    dict_max_sec: float     = 60.0        # hard cap per dictation

    # ── output ─────────────────────────────────────────────────────
    no_inject: bool         = False       # True = print only, never type


# ═════════════════════════════════════════════════════════════════════════════
# AUDIO CAPTURE
# ═════════════════════════════════════════════════════════════════════════════

class AudioCapture:
    """Continuous microphone capture with Voice Activity Detection."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.frame_size = int(cfg.sample_rate * cfg.frame_ms / 1000)
        self._vad    = webrtcvad.Vad(cfg.vad_aggressiveness)
        self._pa     = pyaudio.PyAudio()
        self._stream: Optional[object] = None

    # ── lifecycle ───────────────────────────────────────────────────

    def open(self) -> "AudioCapture":
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.cfg.sample_rate,
            input=True,
            frames_per_buffer=self.frame_size,
        )
        return self

    def close(self) -> None:
        try:
            self._stream.stop_stream()  # type: ignore
            self._stream.close()        # type: ignore
        except Exception:
            pass
        try:
            self._pa.terminate()
        except Exception:
            pass

    def __enter__(self) -> "AudioCapture":
        return self.open()

    def __exit__(self, *_) -> None:
        self.close()

    # ── primitives ──────────────────────────────────────────────────

    def read_frame(self) -> bytes:
        return self._stream.read(self.frame_size, exception_on_overflow=False)  # type: ignore

    def is_speech(self, frame: bytes) -> bool:
        try:
            return self._vad.is_speech(frame, self.cfg.sample_rate)
        except Exception:
            return False

    # ── high-level recorder ──────────────────────────────────────────

    def record_until_silence(
        self,
        silence_sec: float,
        max_sec: float,
        stop: Optional[threading.Event] = None,
    ) -> bytes:
        """
        Wait for speech to begin, then record until silence.
        Returns raw int16 PCM at sample_rate Hz.
        Respects *stop* event for clean shutdown.
        """
        frames: list = []
        silent  = 0
        started = False
        max_f   = int(max_sec     * 1000 / self.cfg.frame_ms)
        sil_thr = int(silence_sec * 1000 / self.cfg.frame_ms)
        pre_roll: deque = deque(maxlen=self.cfg.pre_roll_frames)

        while True:
            if stop and stop.is_set():
                return b""
            frame = self.read_frame()
            if not started:
                pre_roll.append(frame)
                if self.is_speech(frame):
                    started = True
                    frames.extend(pre_roll)
            else:
                frames.append(frame)
                if len(frames) >= max_f:
                    break
                if self.is_speech(frame):
                    silent = 0
                else:
                    silent += 1
                    if silent >= sil_thr:
                        break

        return b"".join(frames)


# ═════════════════════════════════════════════════════════════════════════════
# TRANSCRIBER
# ═════════════════════════════════════════════════════════════════════════════

class Transcriber:
    """faster-whisper speech-to-text engine (fully offline)."""

    def __init__(self, cfg: Config) -> None:
        self.cfg   = cfg
        self._wake: Optional[WhisperModel] = None
        self._main: Optional[WhisperModel] = None

    def load(self) -> "Transcriber":
        """Download and load Whisper models (called once at startup)."""
        print(f"{Fore.CYAN}⬇️  Downloading / loading wake-word model [{self.cfg.wake_model_size}] …{Style.RESET_ALL}")
        self._wake = WhisperModel(
            self.cfg.wake_model_size, device="cpu", compute_type="int8"
        )
        if self.cfg.main_model_size == self.cfg.wake_model_size:
            self._main = self._wake
        else:
            print(f"{Fore.CYAN}⬇️  Downloading / loading dictation model  [{self.cfg.main_model_size}] …{Style.RESET_ALL}")
            self._main = WhisperModel(
                self.cfg.main_model_size, device="cpu", compute_type="int8"
            )
        print(f"{Fore.GREEN}✅  Models ready!{Style.RESET_ALL}")
        return self

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _to_f32(raw: bytes) -> "np.ndarray":
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    def _run(self, model: WhisperModel, audio: "np.ndarray", fast: bool) -> str:
        segs, _ = model.transcribe(
            audio,
            language="en",
            beam_size=1 if fast else 5,
            best_of=1  if fast else 5,
            temperature=0.0,
            condition_on_previous_text=not fast,
            vad_filter=not fast,
        )
        return " ".join(s.text for s in segs).strip()

    # ── public ───────────────────────────────────────────────────────────

    def find_wake_word(self, raw: bytes) -> Tuple[bool, str]:
        """
        Returns (found, inline_text).
        inline_text = any text the user spoke *after* the wake word in the same
        breath, e.g. "pineapple remind me to buy milk" -> "remind me to buy milk".
        """
        if not raw:
            return False, ""
        text = self._run(self._wake, self._to_f32(raw), fast=True).lower()  # type: ignore
        kw   = self.cfg.wake_word.lower()
        idx  = text.find(kw)
        if idx < 0:
            return False, ""
        tail = text[idx + len(kw):].strip(" .,!?-")
        return True, tail

    def transcribe(self, raw: bytes) -> str:
        """High-quality dictation transcription."""
        if not raw:
            return ""
        return self._run(self._main, self._to_f32(raw), fast=False)  # type: ignore


# ═════════════════════════════════════════════════════════════════════════════
# TEXT INJECTOR
# ═════════════════════════════════════════════════════════════════════════════

class TextInjector:
    """
    Types transcribed text at the current cursor position.

    Injection priority:
      1. xdotool   — X11 desktops (most Linux)
      2. wtype     — Wayland
      3. ydotool   — Wayland fallback
      4. clipboard — universal fallback (copy + Ctrl+V via pynput)
    """

    _TOOLS = ("xdotool", "wtype", "ydotool")

    def __init__(self) -> None:
        self.method = self._detect()
        self._kbd   = _KCtrl()

    def _detect(self) -> str:
        for tool in self._TOOLS:
            try:
                r = subprocess.run(["which", tool], capture_output=True, timeout=2)
                if r.returncode == 0:
                    return tool
            except Exception:
                pass
        return "clipboard"

    def type_text(self, text: str) -> None:
        if not text.strip():
            return
        t = text.strip()
        # ── try native tool first ────────────────────────────────────────────
        if self.method == "xdotool":
            try:
                subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--delay", "0", "--", t],
                    timeout=15, check=True,
                )
                return
            except Exception:
                pass
        if self.method == "wtype":
            try:
                subprocess.run(["wtype", "--", t], timeout=15, check=True)
                return
            except Exception:
                pass
        if self.method == "ydotool":
            try:
                subprocess.run(["ydotool", "type", "--", t], timeout=15, check=True)
                return
            except Exception:
                pass
        # ── clipboard + paste fallback (works everywhere) ───────────────────
        self._clipboard_paste(t)

    def _clipboard_paste(self, text: str) -> None:
        try:
            prev = pyperclip.paste() or ""
        except Exception:
            prev = ""
        try:
            pyperclip.copy(text)
            time.sleep(0.08)
            self._kbd.press(Key.ctrl)
            self._kbd.press("v")
            self._kbd.release("v")
            self._kbd.release(Key.ctrl)
            time.sleep(0.08)
        except Exception:
            print(f"\n[OUTPUT]: {text}")   # absolute last resort
        finally:
            try:
                pyperclip.copy(prev)
            except Exception:
                pass


# ═════════════════════════════════════════════════════════════════════════════
# AUDIO FEEDBACK
# ═════════════════════════════════════════════════════════════════════════════

class Sounds:
    """Non-blocking audio feedback tones via sounddevice."""
    _SR = 44_100

    @classmethod
    def _tone(cls, freq: float, dur: float, vol: float = 0.25, fade: float = 0.015) -> "np.ndarray":
        t = np.linspace(0, dur, int(cls._SR * dur), endpoint=False)
        w = (np.sin(2 * np.pi * freq * t) * vol).astype(np.float32)
        n = int(cls._SR * fade)
        if len(w) > 2 * n:
            w[:n]  *= np.linspace(0, 1, n, dtype=np.float32)
            w[-n:] *= np.linspace(1, 0, n, dtype=np.float32)
        return w

    @classmethod
    def _play(cls, wave: "np.ndarray") -> None:
        def _go() -> None:
            try:
                sd.play(wave, cls._SR)
                sd.wait()
            except Exception:
                pass
        threading.Thread(target=_go, daemon=True).start()

    @classmethod
    def activate(cls) -> None:
        """Rising two-note chime — wake word heard, now recording."""
        cls._play(np.concatenate([
            cls._tone(880,  0.08),
            np.zeros(int(cls._SR * 0.02), dtype=np.float32),
            cls._tone(1320, 0.12),
        ]))

    @classmethod
    def done(cls) -> None:
        """Single tone — dictation transcribed and injected."""
        cls._play(cls._tone(660, 0.13))

    @classmethod
    def reject(cls) -> None:
        """Low tone — nothing usable was captured."""
        cls._play(cls._tone(220, 0.20, vol=0.15))


# ═════════════════════════════════════════════════════════════════════════════
# TERMINAL UI
# ═════════════════════════════════════════════════════════════════════════════

class UI:
    def banner(self, cfg: Config) -> None:
        kw  = cfg.wake_word
        pad = " " * max(0, 17 - len(kw))
        print(f"""
{Fore.YELLOW}╔══════════════════════════════════════════════════════╗
║   🍍  Pineapple STT  —  Voice Dictation Assistant    ║
║   Say  {Fore.WHITE}"{kw}"{Fore.YELLOW}  then speak freely{pad}║
║   Ctrl-C to quit{" " * 38}║
╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}""")

    def idle(self, kw: str) -> None:
        sys.stdout.write(
            f"\r{Fore.CYAN}\U0001f3a4  Listening for ‘{kw}’…{' ' * 12}{Style.RESET_ALL}"
        )
        sys.stdout.flush()

    def wake_detected(self, kw: str) -> None:
        print(f"\n{Fore.GREEN}✅  ‘{kw}’ detected — speak your dictation!{Style.RESET_ALL}")

    def recording(self, secs: float) -> None:
        sys.stdout.write(
            f"\r{Fore.RED}\U0001f534  Recording  {secs:5.1f}s …{' ' * 12}{Style.RESET_ALL}"
        )
        sys.stdout.flush()

    def transcribing(self) -> None:
        sys.stdout.write(
            f"\r{Fore.YELLOW}⚡  Transcribing…{' ' * 20}{Style.RESET_ALL}"
        )
        sys.stdout.flush()

    def result(self, text: str) -> None:
        print(f"\n{Back.BLUE}{Fore.WHITE} \U0001f4dd  {text} {Style.RESET_ALL}\n")

    def info(self, msg: str) -> None:
        print(f"{Fore.CYAN}ℹ   {msg}{Style.RESET_ALL}")

    def warn(self, msg: str) -> None:
        print(f"\n{Fore.YELLOW}⚠   {msg}{Style.RESET_ALL}")

    def err(self, msg: str) -> None:
        print(f"\n{Fore.RED}✗   {msg}{Style.RESET_ALL}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

class PineappleSTT:

    def __init__(self, cfg: Config) -> None:
        self.cfg         = cfg
        self.ui          = UI()
        self.transcriber = Transcriber(cfg)
        self.injector    = TextInjector()
        self._running    = False
        self._stop       = threading.Event()
        self._rec_start  = 0.0

    # ── startup ───────────────────────────────────────────────────────

    def setup(self) -> "PineappleSTT":
        self.ui.banner(self.cfg)
        print()
        self.ui.info(f"Wake word     : '{self.cfg.wake_word}'")
        self.ui.info(f"Wake model    : whisper-{self.cfg.wake_model_size}")
        self.ui.info(f"Dictation mdl : whisper-{self.cfg.main_model_size}")
        self.ui.info(f"Injection     : {self.injector.method}")
        self.ui.info(f"Output        : {'print only' if self.cfg.no_inject else 'type at cursor'}")
        print()
        self.transcriber.load()
        print()
        return self

    # ── main loop ──────────────────────────────────────────────────────

    def run(self) -> None:
        self._running = True
        signal.signal(signal.SIGINT, self._on_sigint)

        with AudioCapture(self.cfg) as audio:
            self.ui.info("Ready — waiting for wake word …")
            print()

            while self._running:
                self.ui.idle(self.cfg.wake_word)
                try:
                    raw = audio.record_until_silence(
                        silence_sec=self.cfg.wake_silence_sec,
                        max_sec=self.cfg.wake_max_sec,
                        stop=self._stop,
                    )
                    if not raw:
                        continue

                    found, inline = self.transcriber.find_wake_word(raw)
                    if not found:
                        continue

                    # User said "pineapple <dictation>" in one breath
                    if inline and len(inline.split()) >= 2:
                        Sounds.activate()
                        time.sleep(0.05)
                        Sounds.done()
                        self.ui.result(inline)
                        self._emit(inline)
                    else:
                        # Two-stage: wake word alone, then wait for dictation
                        self._dictation_phase(audio)

                except OSError as exc:
                    if self._running:
                        self.ui.err(f"Audio error: {exc}")
                        time.sleep(1)
                except Exception as exc:
                    if self._running:
                        self.ui.err(str(exc))
                        time.sleep(0.5)

    # ── dictation phase ─────────────────────────────────────────────

    def _dictation_phase(self, audio: AudioCapture) -> None:
        self.ui.wake_detected(self.cfg.wake_word)
        Sounds.activate()
        self._rec_start = time.time()

        ticker_stop = threading.Event()

        def _tick() -> None:
            while not ticker_stop.is_set():
                self.ui.recording(time.time() - self._rec_start)
                time.sleep(0.1)

        threading.Thread(target=_tick, daemon=True).start()

        try:
            raw = audio.record_until_silence(
                silence_sec=self.cfg.dict_silence_sec,
                max_sec=self.cfg.dict_max_sec,
                stop=self._stop,
            )
        finally:
            ticker_stop.set()

        dur = time.time() - self._rec_start
        if dur < 0.4 or not raw:
            self.ui.warn("Too short — ignoring.")
            Sounds.reject()
            return

        self.ui.transcribing()
        text = self.transcriber.transcribe(raw)
        Sounds.done()

        if text.strip():
            self.ui.result(text)
            self._emit(text)
        else:
            self.ui.warn("Nothing transcribed.")
            Sounds.reject()

    # ── output ─────────────────────────────────────────────────────────

    def _emit(self, text: str) -> None:
        if self.cfg.no_inject:
            return
        time.sleep(0.15)   # small pause so focus returns to the target window
        self.injector.type_text(text + " ")

    # ── signal ─────────────────────────────────────────────────────────

    def _on_sigint(self, *_) -> None:
        print(f"\n\n{Fore.YELLOW}🍍  Pineapple STT stopped. Goodbye!{Style.RESET_ALL}")
        self._running = False
        self._stop.set()
        sys.exit(0)


# ═════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def _parse() -> Config:
    p = argparse.ArgumentParser(
        prog="pineapple-stt",
        description="🍍 Pineapple STT — say a wake word and speak; text appears at your cursor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples
  python3 pineapple_stt.py                         default (wake: 'pineapple')
  python3 pineapple_stt.py -k orange               custom wake word
  python3 pineapple_stt.py -m small                more accurate dictation
  python3 pineapple_stt.py -m medium --vad 3       best quality + strict VAD
  python3 pineapple_stt.py --no-inject             print only, don't type
        """,
    )
    p.add_argument("-k", "--keyword", default="pineapple", metavar="WORD",
                   help="wake word to listen for (default: pineapple)")
    p.add_argument("-m", "--model", default="base",
                   choices=["tiny", "base", "small", "medium", "large"],
                   help="dictation transcription model (default: base)")
    p.add_argument("--wake-model", default="tiny",
                   choices=["tiny", "base", "small"],
                   help="wake-word detection model (default: tiny)")
    p.add_argument("--vad", type=int, default=2, choices=[0, 1, 2, 3],
                   help="VAD mic sensitivity 0-3 (default: 2)")
    p.add_argument("--no-inject", action="store_true",
                   help="print transcription only; do not type it")

    args = p.parse_args()
    cfg = Config()
    cfg.wake_word           = args.keyword
    cfg.main_model_size     = args.model
    cfg.wake_model_size     = args.wake_model
    cfg.vad_aggressiveness  = args.vad
    cfg.no_inject           = args.no_inject
    return cfg


if __name__ == "__main__":
    PineappleSTT(_parse()).setup().run()
