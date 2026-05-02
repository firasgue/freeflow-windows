#!/usr/bin/env python3
"""
FreeFlow Windows — KI-Sprachtranskription für Windows
Inspiriert von zachlatta/freeflow (macOS)

Halte die konfigurierte Taste → Aufnahme startet
Taste loslassen → Text wird transkribiert und eingefügt
"""

import json
import os
import sys
import tempfile
import threading
import time
import wave
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

import numpy as np
import requests
import keyboard
import sounddevice as sd
import pyperclip
import pystray
from PIL import Image, ImageDraw

try:
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

# ── Konfiguration ─────────────────────────────────────────────────────────────

CONFIG_DIR  = Path.home() / ".freeflow-windows"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_key":                   "",
    "hotkey":                    "right ctrl",
    "groq_transcription_model":  "whisper-large-v3-turbo",
    "groq_llm_model":            "llama-3.3-70b-versatile",
    "groq_api_base":             "https://api.groq.com/openai/v1",
    "custom_vocabulary":         [],
    "sample_rate":               16000,
    "post_processing":           True,
    "hold_threshold_ms":         300,   # Mindest-Haltezeit in ms vor Aufnahmestart
}

SYSTEM_PROMPT = (
    "You are a dictation post-processor. "
    "You receive raw speech-to-text output and return clean text "
    "ready to be typed into an application.\n\n"
    "Your job:\n"
    "- Remove filler words (um, uh, you know, like, so) unless they carry meaning\n"
    "- Fix punctuation and capitalisation naturally\n"
    "- Use context clues (active window title, clipboard) to correctly spell "
    "proper names and technical terms\n"
    "- When the transcript contains a close misspelling of a name from context, "
    "correct it\n"
    "- Return ONLY the cleaned text — no explanations, no quotes, no preamble"
)

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_window_context() -> str:
    """Gibt Titel des aktiven Fensters + Clipboard-Vorschau zurück."""
    parts = []

    if WIN32_AVAILABLE:
        try:
            hwnd  = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            if title:
                parts.append(f"Active window: {title}")
        except Exception:
            pass

    try:
        clip = pyperclip.paste()
        if clip and clip.strip():
            preview = clip.strip()[:500]
            parts.append(f"Clipboard content:\n{preview}")
    except Exception:
        pass

    return "\n".join(parts)


def transcribe_audio(audio_path: str, config: dict) -> str:
    """Sendet WAV an Groq Whisper API und gibt Rohtranskript zurück."""
    url     = f"{config['groq_api_base']}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {config['api_key']}"}

    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
        data  = {
            "model":           config["groq_transcription_model"],
            "response_format": "text",
        }
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)

    resp.raise_for_status()
    return resp.text.strip()


def post_process(transcript: str, context: str, config: dict) -> str:
    """LLM bereinigt Transkript und nutzt Fensterkontext."""
    url     = f"{config['groq_api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type":  "application/json",
    }

    user_content = transcript
    if context:
        user_content = f"Context:\n{context}\n\nTranscript:\n{transcript}"

    system = SYSTEM_PROMPT
    vocab  = config.get("custom_vocabulary", [])
    if vocab:
        system += f"\n\nCustom vocabulary (preserve exactly): {', '.join(vocab)}"

    payload = {
        "model":       config["groq_llm_model"],
        "messages":    [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens":  1024,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def paste_text(text: str) -> None:
    """Legt Text in Zwischenablage und simuliert Strg+V."""
    old_clip = ""
    try:
        old_clip = pyperclip.paste()
    except Exception:
        pass

    pyperclip.copy(text)
    time.sleep(0.08)
    keyboard.send("ctrl+v")

    # Original-Clipboard nach kurzem Delay wiederherstellen
    def restore():
        time.sleep(0.5)
        try:
            pyperclip.copy(old_clip)
        except Exception:
            pass
    threading.Thread(target=restore, daemon=True).start()


def play_beep(freq: float = 880, duration: float = 0.07, vol: float = 0.25) -> None:
    """Kurzer Ton als akustisches Feedback."""
    try:
        t    = np.linspace(0, duration, int(44100 * duration), False)
        data = (np.sin(freq * t * 2 * np.pi) * vol * 32767).astype(np.int16)
        sd.play(data, 44100, blocking=False)
    except Exception:
        pass


def make_tray_image() -> Image.Image:
    """Zeichnet ein einfaches Mikrofon-Icon für die Taskleiste."""
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Hintergrundkreis
    draw.ellipse([2, 2, 62, 62], fill=(79, 70, 229))
    # Mikrofon-Kopf
    draw.rounded_rectangle([22, 10, 42, 38], radius=8, fill="white")
    # Stiel
    draw.rectangle([29, 38, 35, 50], fill="white")
    # Basis
    draw.line([20, 50, 44, 50], fill="white", width=3)
    return img


# ── Haupt-Applikation ─────────────────────────────────────────────────────────

class FreeFlowWindows:

    def __init__(self):
        self.config      = load_config()
        self.recording   = False
        self.frames      = []
        self.stream      = None
        self.tray        = None
        self.status      = "idle"       # idle | recording | processing
        self._press_time = 0.0

    # ── Aufnahme ──────────────────────────────────────────────────────────────

    def _on_key_press(self, _event):
        if self.recording or self.status == "processing":
            return
        self._press_time = time.monotonic()
        # Kurzes Warten gegen versehentliche Trigger
        threshold = self.config.get("hold_threshold_ms", 300) / 1000
        threading.Timer(threshold, self._check_start).start()

    def _check_start(self):
        """Startet Aufnahme nur wenn Taste noch gehalten wird."""
        if not self.recording and keyboard.is_pressed(self.config["hotkey"]):
            self._start_recording()

    def _on_key_release(self, _event):
        if self.recording:
            self._stop_recording()

    def _start_recording(self):
        self.recording = True
        self.frames    = []
        self.status    = "recording"
        self._update_tray()
        play_beep(660, 0.06)

        def callback(indata, _frames, _time, _status):
            if self.recording:
                self.frames.append(indata.copy())

        self.stream = sd.InputStream(
            samplerate = self.config["sample_rate"],
            channels   = 1,
            dtype      = "int16",
            callback   = callback,
        )
        self.stream.start()

    def _stop_recording(self):
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        play_beep(880, 0.06)
        self.status = "processing"
        self._update_tray()
        threading.Thread(target=self._process, daemon=True).start()

    # ── Verarbeitung ──────────────────────────────────────────────────────────

    def _process(self):
        try:
            if not self.frames:
                return

            audio = np.concatenate(self.frames, axis=0)
            min_samples = int(self.config["sample_rate"] * 0.5)
            if len(audio) < min_samples:
                return  # Zu kurz → ignorieren

            # WAV temporär speichern
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.config["sample_rate"])
                wf.writeframes(audio.tobytes())

            # Kontext erfassen (vor API-Call, damit Fenster noch aktiv ist)
            context = ""
            if self.config.get("post_processing"):
                context = get_window_context()

            # Transkription via Groq Whisper
            transcript = transcribe_audio(tmp_path, self.config)
            os.unlink(tmp_path)

            if not transcript:
                return

            # LLM Post-Processing
            if self.config.get("post_processing"):
                final = post_process(transcript, context, self.config)
            else:
                final = transcript

            paste_text(final)
            play_beep(1100, 0.05)

        except requests.HTTPError as e:
            print(f"[FreeFlow] API-Fehler: {e.response.status_code} {e.response.text}")
            play_beep(220, 0.25)
        except Exception as e:
            print(f"[FreeFlow] Fehler: {e}")
            play_beep(220, 0.25)
        finally:
            self.status = "idle"
            self._update_tray()

    # ── Tray ──────────────────────────────────────────────────────────────────

    def _update_tray(self):
        if not self.tray:
            return
        labels = {
            "idle":       "FreeFlow Windows – Bereit",
            "recording":  "FreeFlow Windows – ● Aufnahme läuft...",
            "processing": "FreeFlow Windows – ⏳ Verarbeite...",
        }
        self.tray.title = labels.get(self.status, "FreeFlow Windows")

    def _build_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Einstellungen",   self._open_settings),
            pystray.MenuItem("Beenden",         self._quit),
        )
        self.tray = pystray.Icon(
            "FreeFlow Windows",
            make_tray_image(),
            "FreeFlow Windows – Bereit",
            menu,
        )
        return self.tray

    def _open_settings(self, _icon=None, _item=None):
        threading.Thread(target=self._settings_window, daemon=True).start()

    def _settings_window(self):
        SettingsDialog(self.config, on_save=self._apply_settings)

    def _apply_settings(self, new_cfg: dict):
        old_hotkey = self.config["hotkey"]
        self.config = new_cfg
        save_config(new_cfg)
        if old_hotkey != new_cfg["hotkey"]:
            keyboard.unhook_all()
            self._register_hotkey()

    def _quit(self, _icon=None, _item=None):
        keyboard.unhook_all()
        if self.tray:
            self.tray.stop()
        sys.exit(0)

    # ── Hotkey & Start ────────────────────────────────────────────────────────

    def _register_hotkey(self):
        hk = self.config["hotkey"]
        keyboard.on_press_key(hk,   self._on_key_press,   suppress=False)
        keyboard.on_release_key(hk, self._on_key_release, suppress=False)
        print(f"[FreeFlow] Hotkey: '{hk}' halten zum Aufnehmen")

    def run(self):
        if not self.config["api_key"]:
            if not self._run_setup():
                sys.exit(0)

        print("[FreeFlow] Gestartet — Tray-Icon in der Taskleiste")
        self._register_hotkey()

        icon = self._build_tray()
        icon.run_detached()

        # Hauptthread am Leben halten
        try:
            keyboard.wait()
        except KeyboardInterrupt:
            self._quit()

    def _run_setup(self) -> bool:
        """Erstes-Start-Dialog auf dem Hauptthread."""
        root = tk.Tk()
        root.withdraw()
        dlg  = SetupDialog(root)
        root.wait_window(dlg.window)
        root.destroy()

        if dlg.result:
            self.config.update(dlg.result)
            save_config(self.config)
            return True
        return False


# ── Setup-Dialog (Erster Start) ───────────────────────────────────────────────

class SetupDialog:
    def __init__(self, parent):
        self.result = None
        w = tk.Toplevel(parent)
        w.title("FreeFlow Windows – Einrichtung")
        w.geometry("500x340")
        w.resizable(False, False)
        w.grab_set()
        self.window = w
        self._hotkey_var = tk.StringVar(value="right ctrl")
        self._build(w)

    def _build(self, w):
        tk.Label(w, text="🎙️ FreeFlow Windows",
                 font=("Segoe UI", 16, "bold")).pack(pady=(22, 3))
        tk.Label(w, text="Kostenlose KI-Sprachtranskription für Windows",
                 font=("Segoe UI", 10), fg="gray").pack()

        frm = tk.Frame(w, padx=36, pady=18)
        frm.pack(fill="x")

        # API-Key
        tk.Label(frm, text="Groq API-Key:", font=("Segoe UI", 10, "bold"),
                 anchor="w").grid(row=0, column=0, sticky="w", pady=5)
        self._key_var = tk.StringVar()
        tk.Entry(frm, textvariable=self._key_var, show="•", width=36,
                 font=("Segoe UI", 10)).grid(row=0, column=1, padx=(12, 0), pady=5)

        tk.Label(frm, text="Kostenlos unter console.groq.com",
                 fg="#6366f1", font=("Segoe UI", 9)).grid(
                 row=1, column=1, sticky="w", padx=(12, 0))

        # Hotkey
        tk.Label(frm, text="Aufnahme-Taste:", font=("Segoe UI", 10, "bold"),
                 anchor="w").grid(row=2, column=0, sticky="w", pady=(18, 5))

        hk_frm = tk.Frame(frm)
        hk_frm.grid(row=2, column=1, padx=(12, 0), pady=(18, 5), sticky="w")

        self._hk_label = tk.Label(hk_frm, text="Rechte Strg-Taste",
                                   relief="sunken", width=22,
                                   font=("Segoe UI", 10), bg="white", anchor="w",
                                   padx=6)
        self._hk_label.pack(side="left")
        tk.Button(hk_frm, text="Andere Taste wählen",
                  command=self._capture_hotkey).pack(side="left", padx=(8, 0))

        tk.Label(w, text="Taste halten → aufnehmen  |  Loslassen → Text wird eingefügt",
                 font=("Segoe UI", 9), fg="gray").pack()

        tk.Button(w, text="  Loslegen →  ",
                  command=self._save,
                  font=("Segoe UI", 11), bg="#4f46e5", fg="white",
                  padx=10, pady=8, relief="flat", cursor="hand2").pack(pady=22)

    def _capture_hotkey(self):
        cap = tk.Toplevel(self.window)
        cap.title("Taste drücken")
        cap.geometry("300x110")
        cap.resizable(False, False)
        cap.grab_set()
        tk.Label(cap, text="Drücken Sie jetzt die gewünschte Taste…\n"
                            "(Fn-Taste funktioniert leider nicht unter Windows)",
                 font=("Segoe UI", 10), wraplength=270, justify="center").pack(
                 expand=True)

        KEYMAP = {
            "control_r": "right ctrl",  "control_l": "left ctrl",
            "alt_r":     "right alt",   "alt_l":     "left alt",
            "shift_r":   "right shift", "shift_l":   "left shift",
            "scroll_lock":"scroll lock","pause":      "pause",
            "capital":   "caps lock",
        }

        def on_key(event):
            name   = event.keysym.lower()
            hotkey = KEYMAP.get(name, name)
            self._hotkey_var.set(hotkey)
            self._hk_label.config(text=hotkey.title())
            cap.destroy()

        cap.bind("<KeyPress>", on_key)
        cap.focus_set()

    def _save(self):
        api_key = self._key_var.get().strip()
        if not api_key:
            messagebox.showerror("Fehler", "Bitte Groq API-Key eingeben.", parent=self.window)
            return
        self.result = {"api_key": api_key, "hotkey": self._hotkey_var.get()}
        self.window.destroy()


# ── Einstellungen-Dialog ──────────────────────────────────────────────────────

class SettingsDialog:
    def __init__(self, config: dict, on_save=None):
        self._config  = config
        self._on_save = on_save
        root = tk.Tk()
        root.title("FreeFlow Windows – Einstellungen")
        root.geometry("500x430")
        root.resizable(False, False)
        self._build(root)
        root.mainloop()

    def _build(self, root):
        frm = tk.Frame(root, padx=36, pady=24)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Einstellungen",
                 font=("Segoe UI", 13, "bold")).grid(
                 row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))

        row = 1

        def lbl(text, r):
            tk.Label(frm, text=text, font=("Segoe UI", 10),
                     anchor="w").grid(row=r, column=0, sticky="w", pady=7)

        # API-Key
        lbl("Groq API-Key:", row)
        self._key = tk.StringVar(value=self._config.get("api_key", ""))
        tk.Entry(frm, textvariable=self._key, show="•", width=32,
                 font=("Segoe UI", 10)).grid(row=row, column=1, padx=(12, 0)); row += 1

        # Hotkey
        lbl("Aufnahme-Taste:", row)
        self._hk = tk.StringVar(value=self._config.get("hotkey", "right ctrl"))
        tk.Entry(frm, textvariable=self._hk, width=22,
                 font=("Segoe UI", 10)).grid(row=row, column=1, sticky="w",
                 padx=(12, 0)); row += 1
        tk.Label(frm, text="Gültige Namen: right ctrl, f9, scroll lock, pause …",
                 fg="gray", font=("Segoe UI", 8)).grid(row=row, column=1,
                 sticky="w", padx=(12, 0)); row += 1

        # Post-Processing
        lbl("LLM Post-Processing:", row)
        self._pp = tk.BooleanVar(value=self._config.get("post_processing", True))
        tk.Checkbutton(frm, variable=self._pp).grid(row=row, column=1,
                       sticky="w", padx=(12, 0)); row += 1

        # Modelle
        lbl("Transkriptions-Modell:", row)
        self._tm = tk.StringVar(value=self._config.get(
            "groq_transcription_model", "whisper-large-v3-turbo"))
        tk.Entry(frm, textvariable=self._tm, width=32,
                 font=("Segoe UI", 10)).grid(row=row, column=1, padx=(12, 0)); row += 1

        lbl("LLM-Modell:", row)
        self._lm = tk.StringVar(value=self._config.get(
            "groq_llm_model", "llama-3.3-70b-versatile"))
        tk.Entry(frm, textvariable=self._lm, width=32,
                 font=("Segoe UI", 10)).grid(row=row, column=1, padx=(12, 0)); row += 1

        # Vokabular
        lbl("Eigenes Vokabular:", row)
        self._vocab = tk.Text(frm, width=32, height=5, font=("Segoe UI", 10))
        self._vocab.grid(row=row, column=1, padx=(12, 0), pady=6); row += 1
        vocab_str = "\n".join(self._config.get("custom_vocabulary", []))
        self._vocab.insert("1.0", vocab_str)
        tk.Label(frm, text="Ein Begriff pro Zeile",
                 fg="gray", font=("Segoe UI", 8)).grid(row=row, column=1,
                 sticky="w", padx=(12, 0)); row += 1

        # Buttons
        bf = tk.Frame(frm)
        bf.grid(row=row, column=0, columnspan=2, pady=18)
        tk.Button(bf, text="Speichern", command=lambda: self._save(root),
                  bg="#4f46e5", fg="white", padx=16, pady=6,
                  relief="flat", font=("Segoe UI", 10)).pack(side="left", padx=8)
        tk.Button(bf, text="Abbrechen", command=root.destroy,
                  padx=16, pady=6, font=("Segoe UI", 10)).pack(side="left")

    def _save(self, root):
        new = self._config.copy()
        new["api_key"]                  = self._key.get().strip()
        new["hotkey"]                   = self._hk.get().strip()
        new["post_processing"]          = self._pp.get()
        new["groq_transcription_model"] = self._tm.get().strip()
        new["groq_llm_model"]           = self._lm.get().strip()
        raw_vocab = self._vocab.get("1.0", "end").strip()
        new["custom_vocabulary"] = [v.strip() for v in raw_vocab.splitlines() if v.strip()]
        save_config(new)
        if self._on_save:
            self._on_save(new)
        root.destroy()


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Hinweis bei fehlenden Admin-Rechten
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("[FreeFlow] Hinweis: Bei Problemen mit Hotkeys als Administrator starten.")
    except Exception:
        pass

    app = FreeFlowWindows()
    app.run()
