import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def resource_root():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "frontend"
    return Path(__file__).resolve().parents[2] / "src" / "frontend"


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
PORT_FILE = DATA_ROOT / ".practice_log_server.json"


def read_log():
    if not LOG_PATH.exists():
        return {}
    try:
        data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    normalized = {}
    for day, entry in data.items():
        if isinstance(entry, dict):
            normalized[day] = {
                "seconds": float(entry.get("seconds", 0.0)),
                "note": str(entry.get("note", "")),
            }
        else:
            normalized[day] = {"seconds": float(entry or 0.0), "note": ""}
    return normalized


def write_log(data):
    LOG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def process_alive(pid):
    if not pid:
        return True
    if os.name == "nt":
        try:
            import ctypes

            synchronize = 0x00100000
            wait_timeout = 0x00000102
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(synchronize, False, pid)
            if not handle:
                return False
            try:
                return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self.send_json({"ok": True})
            return
        if path == "/api/log":
            self.send_json(read_log())
            return

        if path == "/":
            path = "/records.html"
        file_path = (ROOT / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(ROOT.resolve())) or not file_path.exists():
            self.send_error(404)
            return

        content_type = "text/plain; charset=utf-8"
        if file_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/shutdown":
            self.send_json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        if path != "/api/log":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self.send_error(400)
            return

        current = read_log()
        for day, entry in payload.items():
            current_entry = current.get(day, {"seconds": 0.0, "note": ""})
            current_seconds = float(current_entry.get("seconds", 0.0))
            incoming_seconds = float(entry.get("seconds", 0.0))
            current[day] = {
                "seconds": max(0.0, current_seconds, incoming_seconds),
                "note": str(entry.get("note", "")),
            }
        write_log(current)
        self.send_json(current)

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def main():
    ThreadingHTTPServer.allow_reuse_address = True
    parent_pid = int(os.environ.get("PRACTICE_FLOAT_PID", "0") or "0")
    port = int(os.environ.get("PRACTICE_LOG_PORT", "0") or "0")
    candidates = [port] if port else [0]

    server = None
    for candidate in candidates:
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), Handler)
            port = server.server_address[1]
            break
        except OSError:
            continue

    if server is None:
        raise SystemExit(1)

    PORT_FILE.write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")

    def watch_parent():
        if not parent_pid:
            return
        while True:
            time.sleep(1.0)
            if not process_alive(parent_pid):
                server.shutdown()
                break

    threading.Thread(target=watch_parent, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        try:
            if PORT_FILE.exists():
                PORT_FILE.unlink()
        except OSError:
            pass
        try:
            server.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
