import math
import json
import os
import random
import subprocess
import sys
import time
import tkinter as tk
import traceback
import webbrowser
from collections import deque
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

try:
    import numpy as np
    import sounddevice as sd
except Exception:
    np = None
    sd = None


WIDTH = 420
HEIGHT = 250
BG = "#080d12"
PANEL = "#111923"
GRID = "#20303a"
TEXT = "#dce9e4"
MUTED = "#70858a"
GREEN = "#47f0a0"
CYAN = "#55d7ff"
AMBER = "#ffd166"
RED = "#ff6565"
IS_MAC = sys.platform == "darwin"


def resource_root():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def data_root():
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        app_bundle = next((parent for parent in executable.parents if parent.suffix == ".app"), None)
        if app_bundle:
            return app_bundle.parent / "data"
        return Path(sys.executable).parent / "data"
    return Path(__file__).resolve().parents[2] / "data"


ROOT = resource_root()
DATA_ROOT = data_root()
DATA_ROOT.mkdir(parents=True, exist_ok=True)
LOG_PATH = DATA_ROOT / "practice_log.json"
LOG_PORT_FILE = DATA_ROOT / ".practice_log_server.json"
CRASH_LOG_PATH = DATA_ROOT / "crash.log"


def write_crash_log():
    try:
        CRASH_LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


class PracticeLog:
    def __init__(self):
        self.path = LOG_PATH
        self.today = date.today().isoformat()
        self.data = self.load()
        self.ensure_today()
        self.last_save = time.perf_counter()

    def ensure_today(self):
        entry = self.data.get(self.today)
        if isinstance(entry, dict):
            entry.setdefault("seconds", 0.0)
            entry.setdefault("note", "")
        else:
            self.data[self.today] = {"seconds": float(entry or 0.0), "note": ""}

    def load(self):
        try:
            if self.path.exists():
                return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def add(self, seconds):
        if seconds <= 0:
            return
        self.reload()
        current = date.today().isoformat()
        if current != self.today:
            self.today = current
            self.ensure_today()
        self.data[self.today]["seconds"] = float(self.data[self.today].get("seconds", 0.0)) + seconds
        now = time.perf_counter()
        if now - self.last_save >= 1:
            self.save()
            self.last_save = now

    def today_entry(self):
        self.ensure_today()
        return self.data[self.today]

    def entries(self):
        normalized = []
        for key in sorted(self.data.keys(), reverse=True):
            try:
                date.fromisoformat(key)
            except ValueError:
                continue
            entry = self.data[key]
            if not isinstance(entry, dict):
                entry = {"seconds": float(entry or 0.0), "note": ""}
                self.data[key] = entry
            normalized.append((key, entry))
        return normalized

    def update_entry(self, day, seconds=None, note=None):
        entry = self.data.get(day)
        if not isinstance(entry, dict):
            entry = {"seconds": float(entry or 0.0), "note": ""}
        if seconds is not None:
            entry["seconds"] = max(0.0, float(seconds))
        if note is not None:
            entry["note"] = note.strip()
        self.data[day] = entry
        self.save()

    def minutes_today(self):
        return int(self.seconds_today() // 60)

    def seconds_today(self):
        self.ensure_today()
        return float(self.data[self.today].get("seconds", 0.0))

    def note_today(self):
        self.ensure_today()
        return str(self.data[self.today].get("note", ""))

    def set_note_today(self, note):
        self.ensure_today()
        self.data[self.today]["note"] = note.strip()
        self.save()

    def seconds_this_week(self):
        today = date.today()
        year, week, _ = today.isocalendar()
        total = 0.0
        for key, entry in self.data.items():
            try:
                day = date.fromisoformat(key)
            except ValueError:
                continue
            day_year, day_week, _ = day.isocalendar()
            if day_year == year and day_week == week:
                total += self.entry_seconds(entry)
        return total

    def seconds_this_month(self):
        today = date.today()
        total = 0.0
        for key, entry in self.data.items():
            try:
                day = date.fromisoformat(key)
            except ValueError:
                continue
            if day.year == today.year and day.month == today.month:
                total += self.entry_seconds(entry)
        return total

    def entry_seconds(self, entry):
        if isinstance(entry, dict):
            return float(entry.get("seconds", 0.0))
        return float(entry or 0.0)

    def save(self):
        try:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def reload(self):
        latest = self.load()
        if latest:
            self.data = latest
            self.ensure_today()


class MetronomeSound:
    def __init__(self):
        self.sample_rate = 44100
        self.tone = self.make_tone(620, 0.045, 0.12)

    def make_tone(self, frequency, duration, volume):
        if np is None:
            return None
        t = np.linspace(0, duration, int(self.sample_rate * duration), endpoint=False)
        attack = np.minimum(1.0, t / 0.004)
        release = np.exp(-t * 46.0)
        envelope = attack * release
        tone = np.sin(2 * np.pi * frequency * t)
        tone += np.sin(2 * np.pi * frequency * 1.5 * t) * 0.18
        return (tone * envelope * volume).astype(np.float32)

    def play(self, fallback=None):
        if sd is not None and np is not None:
            try:
                sd.play(self.tone, self.sample_rate, blocking=False)
                return
            except Exception:
                pass
        if fallback:
            fallback()


class AudioProbe:
    def __init__(self, kind):
        self.kind = kind
        self.stream = None
        self.samples = deque([0.0] * 8192, maxlen=8192)
        self.level = 0.0
        self.active = False
        self.error = ""
        self.device_id = None
        self.device_name = "SIM"
        self.sample_rate = 44100

    def stop(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        self.stream = None
        self.active = False

    def start(self, device_id=None, device_name=None):
        self.stop()
        self.device_id = device_id
        if device_name:
            self.device_name = device_name

        if sd is None or np is None:
            self.error = "SIM"
            return False

        try:
            if self.kind == "mic":
                channels = 1
                if device_id is not None:
                    info = sd.query_devices(device_id)
                    channels = max(1, min(2, int(info["max_input_channels"] or 1)))
                    self.device_name = str(info["name"])
                    self.sample_rate = int(info["default_samplerate"] or self.sample_rate)
                self.stream = sd.InputStream(device=device_id, channels=channels, samplerate=self.sample_rate, callback=self._callback)
            else:
                hostapis = sd.query_hostapis()
                wasapi = next((i for i, api in enumerate(hostapis) if "WASAPI" in api["name"]), None)
                if wasapi is None:
                    raise RuntimeError("WASAPI not available")

                device = device_id if device_id is not None else sd.default.device[1]
                info = sd.query_devices(device)
                self.device_name = str(info["name"])
                self.sample_rate = int(info["default_samplerate"] or self.sample_rate)
                channels = max(1, min(2, int(info["max_output_channels"] or 1)))
                settings = sd.WasapiSettings(loopback=True)
                self.stream = sd.InputStream(
                    device=device,
                    channels=channels,
                    samplerate=self.sample_rate,
                    callback=self._callback,
                    extra_settings=settings,
                )

            self.stream.start()
            self.active = True
            self.error = ""
            return True
        except Exception as exc:
            self.error = str(exc)
            self.active = False
            return False

    def _callback(self, indata, frames, callback_time, status):
        data = np.asarray(indata, dtype=np.float32)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if data.size == 0:
            return

        self.samples.extend(float(x) for x in data)
        self.level = min(1.0, float(np.sqrt(np.mean(data * data)) * 7.0))


def list_audio_devices(kind):
    if sd is None:
        return []

    devices = []
    try:
        for index, device in enumerate(sd.query_devices()):
            if kind == "mic" and int(device["max_input_channels"] or 0) <= 0:
                continue
            if kind == "system" and int(device["max_output_channels"] or 0) <= 0:
                continue

            hostapi = sd.query_hostapis(device["hostapi"])["name"]
            label = f"{device['name']}  ·  {hostapi}"
            devices.append((index, label))
    except Exception:
        return []

    return devices


NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
CHORD_TYPES = [
    ("", [0, 4, 7]),
    ("m", [0, 3, 7]),
    ("7", [0, 4, 7, 10]),
    ("maj7", [0, 4, 7, 11]),
    ("m7", [0, 3, 7, 10]),
    ("sus4", [0, 5, 7]),
    ("sus2", [0, 2, 7]),
    ("dim", [0, 3, 6]),
    ("aug", [0, 4, 8]),
]


def detect_chord(samples, sample_rate, level):
    if np is None or level < 0.028 or len(samples) < 2048:
        return "--", 0.0

    data = np.asarray(samples, dtype=np.float32)[-3072:]
    data = data - float(np.mean(data))
    if float(np.max(np.abs(data))) < 0.002:
        return "--", 0.0

    fft_size = 8192
    window = np.hanning(data.size)
    spectrum = np.abs(np.fft.rfft(data * window, n=fft_size))
    freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
    mask = (freqs >= 70.0) & (freqs <= 1500.0)
    freqs = freqs[mask]
    mags = spectrum[mask]
    if mags.size == 0 or float(np.max(mags)) <= 0:
        return "--", 0.0

    threshold = float(np.max(mags)) * 0.12
    peak_indices = []
    for i in range(1, mags.size - 1):
        if mags[i] >= threshold and mags[i] >= mags[i - 1] and mags[i] >= mags[i + 1]:
            peak_indices.append(i)
    peak_indices = sorted(peak_indices, key=lambda i: float(mags[i]), reverse=True)[:28]
    peak_indices = sorted(peak_indices, key=lambda i: float(freqs[i]))

    chroma = np.zeros(12, dtype=np.float64)
    bass_pc = -1
    for index in peak_indices:
        freq = freqs[index]
        mag = mags[index]
        if bass_pc < 0:
            bass_midi = 69 + 12 * math.log2(float(freq) / 440.0)
            bass_pc = int(round(bass_midi)) % 12
        midi = 69 + 12 * math.log2(float(freq) / 440.0)
        pitch_class = int(round(midi)) % 12
        energy = float(mag) ** 0.62
        chroma[pitch_class] += energy

    total = float(np.sum(chroma))
    if total <= 0:
        return "--", 0.0
    chroma = chroma / total

    best_name = "--"
    best_score = -1.0
    for root in range(12):
        for suffix, intervals in CHORD_TYPES:
            template = np.zeros(12, dtype=np.float64)
            for interval in intervals:
                template[(root + interval) % 12] = 1.0
            hit = float(np.mean([chroma[(root + interval) % 12] for interval in intervals]))
            miss = float(np.sum(chroma * (1.0 - template)))
            root_energy = float(chroma[root])
            score = hit + root_energy * 0.22 - miss * 0.10 - max(0, len(intervals) - 3) * 0.018
            if root == bass_pc:
                score += 0.085
            elif bass_pc >= 0 and (bass_pc - root) % 12 not in intervals:
                score -= 0.025
            if score > best_score:
                best_score = score
                best_name = f"{NOTE_NAMES[root]}{suffix}"

    confidence = max(0.0, min(1.0, best_score * 4.2))
    if confidence < 0.24:
        return "--", confidence
    return best_name, confidence


class DevicePicker:
    def __init__(self, parent, title, devices, on_select):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("+%s+%s" % (parent.winfo_x() + 24, parent.winfo_y() + 42))
        self.window.configure(bg=BG)
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.on_select = on_select
        self.devices = devices

        tk.Label(
            self.window,
            text=title,
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))

        self.listbox = tk.Listbox(
            self.window,
            width=58,
            height=min(9, max(3, len(devices))),
            bg=PANEL,
            fg=TEXT,
            selectbackground="#25465a",
            selectforeground=TEXT,
            highlightthickness=1,
            highlightbackground="#263743",
            bd=0,
            font=("Segoe UI", 9),
        )
        self.listbox.pack(padx=12, pady=(0, 10))

        if devices:
            for _, label in devices:
                self.listbox.insert("end", label)
            self.listbox.selection_set(0)
        else:
            self.listbox.insert("end", "没有可用设备，当前只能显示模拟波形")

        button_row = tk.Frame(self.window, bg=BG)
        button_row.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(button_row, text="OK", command=self.confirm, **self.button_style(GREEN)).pack(side="right", padx=(8, 0))
        tk.Button(button_row, text="Cancel", command=self.window.destroy, **self.button_style("#26343d")).pack(side="right")

        self.listbox.bind("<Double-Button-1>", lambda event: self.confirm())
        self.window.bind("<Return>", lambda event: self.confirm())
        self.window.bind("<Escape>", lambda event: self.window.destroy())

    def button_style(self, color):
        return {
            "bg": color,
            "fg": TEXT,
            "activebackground": color,
            "activeforeground": TEXT,
            "bd": 0,
            "font": ("Segoe UI", 8, "bold"),
            "padx": 12,
            "pady": 5,
            "cursor": "hand2",
        }

    def confirm(self):
        if not self.devices:
            self.window.destroy()
            return
        selection = self.listbox.curselection()
        if not selection:
            return
        device_id, label = self.devices[selection[0]]
        self.on_select(device_id, label)
        self.window.destroy()


class LogWindow:
    def __init__(self, parent, log):
        self.log = log
        self.window = tk.Toplevel(parent)
        self.window.title("Practice Log")
        self.window.geometry("+%s+%s" % (parent.winfo_x() + 24, parent.winfo_y() + 42))
        self.window.configure(bg=BG)
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.selected_day = None

        tk.Label(
            self.window,
            text="PRACTICE LOG",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))

        body = tk.Frame(self.window, bg=BG)
        body.pack(fill="both", padx=12, pady=(0, 10))

        self.listbox = tk.Listbox(
            body,
            width=18,
            height=9,
            bg=PANEL,
            fg=TEXT,
            selectbackground="#25465a",
            selectforeground=TEXT,
            highlightthickness=1,
            highlightbackground="#263743",
            bd=0,
            font=("Segoe UI", 9),
        )
        self.listbox.pack(side="left", fill="y", padx=(0, 10))

        editor = tk.Frame(body, bg=BG)
        editor.pack(side="left", fill="both")

        tk.Label(editor, text="MIN", bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        self.minutes_var = tk.StringVar(value="0")
        self.minutes_entry = tk.Entry(
            editor,
            textvariable=self.minutes_var,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            bd=0,
            justify="center",
            font=("Segoe UI", 11, "bold"),
            width=8,
        )
        self.minutes_entry.pack(anchor="w", pady=(0, 8))

        tk.Label(editor, text="NOTE", bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        self.text = tk.Text(
            editor,
            width=36,
            height=6,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            highlightthickness=1,
            highlightbackground="#263743",
            bd=0,
            font=("Segoe UI", 9),
            wrap="word",
        )
        self.text.pack()

        row = tk.Frame(self.window, bg=BG)
        row.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(row, text="Save", command=self.save, **self.button_style(GREEN)).pack(side="right", padx=(8, 0))
        tk.Button(row, text="Cancel", command=self.window.destroy, **self.button_style("#26343d")).pack(side="right")
        self.window.bind("<Escape>", lambda event: self.window.destroy())
        self.listbox.bind("<<ListboxSelect>>", lambda event: self.load_selected())
        self.refresh()

    def button_style(self, color):
        return {
            "bg": color,
            "fg": TEXT,
            "activebackground": color,
            "activeforeground": TEXT,
            "bd": 0,
            "font": ("Segoe UI", 8, "bold"),
            "padx": 12,
            "pady": 5,
            "cursor": "hand2",
        }

    def save(self):
        if not self.selected_day:
            return
        try:
            seconds = max(0, int(float(self.minutes_var.get().strip())) * 60)
        except ValueError:
            seconds = self.log.entry_seconds(self.log.data.get(self.selected_day, {}))
        self.log.update_entry(self.selected_day, seconds=seconds, note=self.text.get("1.0", "end").strip())
        self.refresh(keep_day=self.selected_day)

    def refresh(self, keep_day=None):
        self.entries = self.log.entries()
        self.listbox.delete(0, "end")
        selected_index = 0
        for index, (day, entry) in enumerate(self.entries):
            minutes = int(self.log.entry_seconds(entry) // 60)
            self.listbox.insert("end", f"{day[5:]}  {minutes}m")
            if day == keep_day:
                selected_index = index
        if self.entries:
            self.listbox.selection_set(selected_index)
            self.load_day(self.entries[selected_index][0])

    def load_selected(self):
        selection = self.listbox.curselection()
        if not selection or not self.entries:
            return
        self.load_day(self.entries[selection[0]][0])

    def load_day(self, day):
        self.selected_day = day
        entry = self.log.data.get(day, {"seconds": 0.0, "note": ""})
        self.minutes_var.set(str(int(self.log.entry_seconds(entry) // 60)))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", str(entry.get("note", "") if isinstance(entry, dict) else ""))


class PracticeFloat:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Guitar Practice Monitor")
        screen_width = self.root.winfo_screenwidth()
        x = max(20, min(screen_width - WIDTH - 20, 1420))
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+120")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        if not IS_MAC:
            self.root.overrideredirect(True)

        self.mic = AudioProbe("mic")
        self.mic_bars = [0.0] * 48
        self.waterfall = deque(maxlen=18)
        self.visual_gain = 1.0
        self.practice_log = PracticeLog()
        self.last_practice_tick = time.perf_counter()
        self.practice_pending_seconds = 0.0
        self.tempo = 84
        self.metro_on = False
        self.pulse_at = 0.0
        self.next_tick = time.perf_counter()
        self.metro_job = None
        self.log_server_process = None
        self.log_server_port = None
        self.metro_sound = MetronomeSound()
        self.chord = "--"
        self.chord_confidence = 0.0
        self.chord_candidate = "--"
        self.chord_candidate_at = time.perf_counter()
        self.drag_start = None

        self.canvas = tk.Canvas(self.root, width=WIDTH, height=HEIGHT, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)

        self.root.bind("<Escape>", lambda event: self.root.destroy())
        self.root.bind("<space>", lambda event: self.toggle_metro())
        self.root.bind("<Up>", lambda event: self.set_tempo(self.tempo + 2))
        self.root.bind("<Down>", lambda event: self.set_tempo(self.tempo - 2))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.make_buttons()
        self.ensure_log_server()
        self.animate()

    def make_buttons(self):
        self.mic_button = tk.Button(self.root, text="MIC", command=self.start_mic, **self.button_style(GREEN))
        self.log_button = tk.Button(self.root, text="LOG", command=self.open_log, **self.button_style("#2f4652"))
        self.metro_button = tk.Button(self.root, text="▶", command=self.toggle_metro, **self.button_style(AMBER, "#1d1600"))
        self.down_button = tk.Button(self.root, text="-", command=lambda: self.set_tempo(self.tempo - 5), **self.button_style(MUTED))
        self.up_button = tk.Button(self.root, text="+", command=lambda: self.set_tempo(self.tempo + 5), **self.button_style(MUTED))
        self.close_button = tk.Button(self.root, text="×", command=self.close, **self.button_style("#24313a"))
        self.tempo_var = tk.StringVar(value=str(self.tempo))
        self.tempo_entry = tk.Entry(
            self.root,
            textvariable=self.tempo_var,
            bg="#111923",
            fg=TEXT,
            insertbackground=TEXT,
            justify="center",
            bd=0,
            font=("Segoe UI", 17, "bold"),
        )
        self.tempo_entry.bind("<Return>", lambda event: self.commit_tempo())
        self.tempo_entry.bind("<FocusOut>", lambda event: self.commit_tempo())

        self.canvas.create_window(250, 24, window=self.mic_button, width=44, height=26, tags="ui")
        self.canvas.create_window(304, 24, window=self.log_button, width=48, height=26, tags="ui")
        self.canvas.create_window(360, 24, window=self.metro_button, width=34, height=26, tags="ui")
        self.canvas.create_window(138, 220, window=self.down_button, width=28, height=24, tags="ui")
        self.canvas.create_window(178, 220, window=self.up_button, width=28, height=24, tags="ui")
        self.canvas.create_window(404, 16, window=self.close_button, width=24, height=24, tags="ui")
        self.canvas.create_window(58, 220, window=self.tempo_entry, width=66, height=32, tags="ui")

    def button_style(self, color, fg=TEXT):
        return {
            "bg": color,
            "fg": fg,
            "activebackground": color,
            "activeforeground": fg,
            "bd": 0,
            "font": ("Segoe UI", 8, "bold"),
            "cursor": "hand2",
        }

    def start_drag(self, event):
        self.drag_start = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

    def drag(self, event):
        if not self.drag_start:
            return
        start_x, start_y, win_x, win_y = self.drag_start
        self.root.geometry(f"+{win_x + event.x_root - start_x}+{win_y + event.y_root - start_y}")

    def start_mic(self):
        devices = list_audio_devices("mic")
        DevicePicker(self.root, "MIC INPUT", devices, self.use_mic_device)

    def use_mic_device(self, device_id, label):
        ok = self.mic.start(device_id, label)
        self.mic_button.configure(text="ON" if ok else "SIM")
        self.last_practice_tick = time.perf_counter()
        self.practice_pending_seconds = 0.0

    def open_log(self):
        self.practice_log.save()
        url = self.ensure_log_server()
        if url:
            webbrowser.open(url)

    def ensure_log_server(self):
        if self.log_server_port and self.log_server_alive(self.log_server_port):
            return self.log_url(self.log_server_port)

        env = os.environ.copy()
        env["PRACTICE_FLOAT_PID"] = str(os.getpid())
        env.pop("PRACTICE_LOG_PORT", None)
        try:
            command = [sys.executable, "--log-server"] if getattr(sys, "frozen", False) else [sys.executable, str(ROOT / "src" / "backend" / "log_server.py")]
            self.log_server_process = subprocess.Popen(
                command,
                cwd=str(DATA_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=env,
            )
        except Exception:
            return None

        deadline = time.perf_counter() + 2.0
        while time.perf_counter() < deadline:
            actual_port = self.read_log_server_port()
            if self.log_server_alive(actual_port):
                self.log_server_port = actual_port
                return self.log_url(actual_port)
            time.sleep(0.05)
        return None

    def log_server_alive(self, port):
        if not port:
            return False
        base = self.log_url(port)
        for url in (base + "health", base + "api/log"):
            try:
                with urlopen(url, timeout=0.35) as response:
                    if response.status == 200:
                        return True
            except (OSError, URLError):
                continue
        return False

    def log_url(self, port):
        return f"http://127.0.0.1:{port}/"

    def read_log_server_port(self):
        try:
            if LOG_PORT_FILE.exists():
                data = json.loads(LOG_PORT_FILE.read_text(encoding="utf-8"))
                return int(data.get("port"))
        except Exception:
            return None
        return None

    def toggle_metro(self):
        self.metro_on = not self.metro_on
        self.metro_button.configure(text="■" if self.metro_on else "▶")
        self.next_tick = time.perf_counter()
        if self.metro_job:
            self.root.after_cancel(self.metro_job)
            self.metro_job = None
        if self.metro_on:
            self.schedule_metronome(0)

    def set_tempo(self, tempo):
        self.tempo = max(40, min(220, int(tempo)))
        self.tempo_var.set(str(self.tempo))
        if self.metro_on:
            self.next_tick = time.perf_counter() + 60.0 / self.tempo

    def commit_tempo(self):
        text = self.tempo_var.get().strip()
        try:
            self.set_tempo(int(float(text)))
        except ValueError:
            self.tempo_var.set(str(self.tempo))
        self.root.focus_set()

    def schedule_metronome(self, delay_ms=None):
        if not self.metro_on:
            return
        now = time.perf_counter()
        if delay_ms is None:
            delay_ms = max(1, int((self.next_tick - now) * 1000))
        self.metro_job = self.root.after(delay_ms, self.metronome_tick)

    def metronome_tick(self):
        if not self.metro_on:
            return
        self.metro_sound.play(fallback=self.root.bell)
        self.pulse_at = time.perf_counter()
        self.next_tick += 60.0 / self.tempo

        now = time.perf_counter()
        if self.next_tick < now:
            self.next_tick = now + 60.0 / self.tempo
        self.schedule_metronome()

    def demo_samples(self, phase, flavor):
        values = []
        loud = 0.06 + 0.03 * math.sin(phase * 1.7 + (0 if flavor == "mic" else 1.8))
        for i in range(512):
            x = i / 512
            wave = math.sin(x * math.tau * 5 + phase)
            wave += math.sin(x * math.tau * 17 + phase * 1.8) * 0.26
            wave += random.uniform(-0.02, 0.02)
            values.append(wave * loud)
        return values, min(1.0, abs(loud) * 1.5)

    def source_data(self, probe, phase, flavor):
        if probe.active:
            return list(probe.samples), probe.level
        return self.demo_samples(phase, flavor)

    def spectrum_bars(self, samples, previous, level):
        count = len(previous)
        if not samples:
            return previous

        if level < 0.018:
            return [old * 0.82 for old in previous]

        if np is not None and len(samples) >= 256:
            data = np.asarray(samples[-4096:], dtype=np.float32)
            data = data - float(np.mean(data))
            fft_size = 4096
            spectrum = np.abs(np.fft.rfft(data * np.hanning(data.size), n=fft_size))
            freqs = np.fft.rfftfreq(fft_size, 1.0 / self.mic.sample_rate)
            raw = []
            edges = np.geomspace(80, 3800, count + 1)
            for low, high in zip(edges[:-1], edges[1:]):
                band = spectrum[(freqs >= low) & (freqs < high)]
                raw.append(float(np.mean(band)) if band.size else 0.0)
            peak = max(raw) or 1.0
            level_weight = min(1.0, max(0.0, (level - 0.012) / 0.22))
            raw = [
                (math.tanh((value / peak) * 1.55) ** 0.82) * (0.28 + 0.72 * level_weight)
                for value in raw
            ]
        else:
            chunk = max(1, len(samples) // count)
            raw = []
            for i in range(count):
                block = samples[i * chunk : (i + 1) * chunk]
                peak = max((abs(x) for x in block), default=0.0)
                raw.append(math.tanh(peak * 2.2) ** 0.72)

        return [old * 0.62 + float(new) * 0.38 for old, new in zip(previous, raw)]

    def draw_scope(self, y, h, label, level, color, accent, bars):
        self.canvas.create_rectangle(12, y, WIDTH - 12, y + h, fill=PANEL, outline="#1e2b33", width=1, tags="viz")
        self.canvas.create_text(24, y + 16, anchor="w", text=label, fill=color, font=("Segoe UI", 8, "bold"), tags="viz")
        name = self.short_name(self.mic.device_name)
        self.canvas.create_text(WIDTH - 24, y + 16, anchor="e", text=name, fill=MUTED, font=("Segoe UI", 7, "bold"), tags="viz")

        left = 26
        right = WIDTH - 26
        usable_w = right - left
        top = y + 31
        bottom = y + h - 13
        waterfall_bottom = bottom - 24
        bar_w = usable_w / len(bars)

        rows = list(self.waterfall)
        row_h = max(2, (waterfall_bottom - top) / max(1, len(rows)))
        for age, row in enumerate(reversed(rows)):
            fade = 1.0 - age / max(1, len(rows))
            row_y = top + age * row_h
            for i, value in enumerate(row):
                if value < 0.08:
                    continue
                x1 = left + i * bar_w
                x2 = x1 + max(1, bar_w - 1)
                fill = self.energy_color(value, fade * 0.62)
                self.canvas.create_rectangle(x1, row_y, x2, row_y + row_h + 1, fill=fill, outline="", tags="viz")

        baseline = bottom - 1
        for i, value in enumerate(bars):
            x1 = left + i * bar_w
            x2 = x1 + max(1, bar_w - 2)
            height = 3 + (value ** 0.72) * 22
            fill = accent if value > 0.72 else color
            self.canvas.create_rectangle(x1, baseline - height, x2, baseline, fill="#17362f", outline="", tags="viz")
            self.canvas.create_rectangle(x1, baseline - height, x2, baseline - height + 3, fill=fill, outline="", tags="viz")

        meter_w = int((WIDTH - 48) * level)
        meter_color = RED if level > 0.82 else AMBER if level > 0.62 else color
        self.canvas.create_rectangle(24, y + h - 6, WIDTH - 24, y + h - 3, fill="#1d2a32", outline="", tags="viz")
        self.canvas.create_rectangle(24, y + h - 6, 24 + meter_w, y + h - 3, fill=meter_color, outline="", tags="viz")

    def energy_color(self, value, fade):
        cold = (16, 28, 33)
        warm = (77, 247, 168) if value < 0.72 else (255, 209, 102)
        mix = min(1.0, max(0.0, value * fade))
        rgb = tuple(int(cold[i] + (warm[i] - cold[i]) * mix) for i in range(3))
        return "#%02x%02x%02x" % rgb

    def short_name(self, name):
        clean = name.split("  ·  ")[0] if name else "SIM"
        if len(clean) <= 24:
            return clean
        return clean[:21] + "..."

    def draw_metronome(self):
        self.canvas.create_rectangle(12, 166, 204, 238, fill=PANEL, outline="#1e2b33", width=1, tags="viz")
        self.canvas.create_text(24, 184, anchor="w", text="METRO", fill=AMBER, font=("Segoe UI", 8, "bold"), tags="viz")
        self.canvas.create_text(96, 222, anchor="w", text="BPM", fill=MUTED, font=("Segoe UI", 8, "bold"), tags="viz")
        pulse = max(0.0, 1.0 - (time.perf_counter() - self.pulse_at) / 0.16) if self.metro_on else 0.0
        radius = 8 + pulse * 8
        fill = AMBER if pulse > 0 else "#23313a"
        self.canvas.create_oval(146 - radius, 196 - radius, 146 + radius, 196 + radius, fill="#302a17", outline="", tags="viz")
        self.canvas.create_oval(146 - radius * 0.62, 196 - radius * 0.62, 146 + radius * 0.62, 196 + radius * 0.62, fill=fill, outline="", tags="viz")

    def update_chord(self, samples, level):
        detected, confidence = detect_chord(samples, self.mic.sample_rate, level)
        now = time.perf_counter()
        if detected != self.chord_candidate:
            self.chord_candidate = detected
            self.chord_candidate_at = now

        if detected == "--" or now - self.chord_candidate_at > 0.08:
            self.chord = detected
            self.chord_confidence = confidence

    def draw_chord(self):
        self.canvas.create_rectangle(216, 166, WIDTH - 12, 238, fill=PANEL, outline="#1e2b33", width=1, tags="viz")
        self.canvas.create_text(228, 184, anchor="w", text="CHORD", fill=GREEN, font=("Segoe UI", 8, "bold"), tags="viz")
        color = TEXT if self.chord != "--" else "#42535a"
        self.canvas.create_text(
            WIDTH - 24,
            212,
            anchor="e",
            text=self.chord,
            fill=color,
            font=("Segoe UI", 34, "bold"),
            tags="viz",
        )

    def update_practice_time(self):
        now = time.perf_counter()
        if self.mic.active:
            self.practice_pending_seconds += now - self.last_practice_tick
            if self.practice_pending_seconds >= 1.0:
                whole_seconds = int(self.practice_pending_seconds)
                self.practice_log.add(whole_seconds)
                self.practice_pending_seconds -= whole_seconds
        else:
            self.practice_pending_seconds = 0.0
        self.last_practice_tick = now

    def draw_practice_time(self):
        pending = self.practice_pending_seconds if self.mic.active else 0.0
        today = self.format_duration(self.practice_log.seconds_today() + pending)
        week = self.format_duration(self.practice_log.seconds_this_week() + pending)
        month = self.format_duration(self.practice_log.seconds_this_month() + pending)
        color = GREEN
        self.canvas.create_text(
            18,
            38,
            anchor="w",
            text=f"D {today}   W {week}   M {month}",
            fill=color,
            font=("Segoe UI", 8, "bold"),
            tags="viz",
        )

    def format_duration(self, seconds):
        seconds = int(seconds)
        minutes = seconds // 60
        rest_seconds = seconds % 60
        if minutes < 60:
            return f"{minutes}m{rest_seconds:02d}s"
        hours = minutes // 60
        if hours < 100:
            rest = minutes % 60
            return f"{hours}h{rest:02d}m"
        if hours < 1000:
            return f"{hours}h"
        return "999h+"
    def animate(self):
        self.canvas.delete("viz")
        phase = time.perf_counter()
        mic_samples, mic_level = self.source_data(self.mic, phase, "mic")
        self.update_practice_time()
        self.mic_bars = self.spectrum_bars(mic_samples, self.mic_bars, mic_level)
        self.waterfall.append(list(self.mic_bars))
        self.update_chord(mic_samples, mic_level)

        self.draw_scope(48, 106, "INPUT", mic_level, GREEN, AMBER, self.mic_bars)
        self.draw_metronome()
        self.draw_chord()
        status = "PRACTICING" if self.mic.active else "WAITING"
        status_color = GREEN if self.mic.active else MUTED
        self.canvas.create_text(18, 22, anchor="w", text=status, fill=status_color, font=("Segoe UI", 12, "bold"), tags="viz")
        self.draw_practice_time()
        self.canvas.create_text(128, 24, anchor="w", text=time.strftime("%H:%M:%S"), fill=AMBER, font=("Segoe UI", 10, "bold"), tags="viz")
        self.canvas.tag_raise("ui")

        self.root.after(33, self.animate)

    def run(self):
        self.root.mainloop()

    def close(self):
        if self.practice_pending_seconds > 0:
            self.practice_log.add(self.practice_pending_seconds)
            self.practice_pending_seconds = 0.0
        self.practice_log.save()
        if self.log_server_process and self.log_server_process.poll() is None:
            try:
                self.log_server_process.terminate()
                self.log_server_process.wait(timeout=1.0)
            except Exception:
                try:
                    self.log_server_process.kill()
                except Exception:
                    pass
        self.root.destroy()


if __name__ == "__main__":
    try:
        if "--log-server" in sys.argv:
            if not getattr(sys, "frozen", False):
                sys.path.insert(0, str(ROOT / "src" / "backend"))
            import log_server

            log_server.main()
        else:
            PracticeFloat().run()
    except Exception:
        write_crash_log()
        raise
