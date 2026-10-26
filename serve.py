"""PULSE-LTE classroom server: run the live dashboard from your laptop.

Phones on the same Wi-Fi or hotspot join by scanning the QR code. No accounts, no app,
no internet needed. Python 3.8+ standard library only.

    python serve.py              # then open http://localhost:8000 on the laptop
    python serve.py --port 9000
    python serve.py --ip 192.168.43.12   # if the QR code shows the wrong address
"""
import argparse
import json
import os
import socket
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "dashboard", "index.html")
QRJS = os.path.join(HERE, "dashboard", "vendor", "qrcode.min.js")
CDN_QR = "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"

# The dashboard file is page content; wrap it in a document with a phone-friendly viewport.
PAGE_HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
             '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
             'body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}img{max-width:100%}'
             '[hidden]{display:none!important}</style></head><body>')

PEER_TIMEOUT = 6.0     # seconds without a poll before a phone is dropped
MAX_MESSAGES = 30
MAX_BODY = 64 * 1024
ALLOWED_TOPICS = {"ue"}

state = {"peers": {}, "messages": [], "seq": 0}
lock = threading.Lock()
JOIN_URL = ""


def lan_addresses():
    """Best guess at the addresses phones can reach this laptop on."""
    found = []
    try:  # the interface that holds the default route (no packet is actually sent)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        found.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in found:
                found.append(ip)
    except OSError:
        pass
    return [ip for ip in found if not ip.startswith("127.")] or ["127.0.0.1"]


class Handler(BaseHTTPRequestHandler):
    server_version = "PULSE-LTE"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    def _send(self, code, body, ctype):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, separators=(",", ":")), "application/json")

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            raise ValueError("bad body size")
        data = json.loads(self.rfile.read(n))
        if not isinstance(data, dict):
            raise ValueError("body must be an object")
        return data

    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0]
        if path in ("/", "/index.html"):
            with open(DASH, encoding="utf-8") as f:
                html = f.read().replace(CDN_QR, "/vendor/qrcode.min.js")
            self._send(200, PAGE_HEAD + html + "</body></html>", "text/html; charset=utf-8")
        elif path == "/vendor/qrcode.min.js":
            with open(QRJS, "rb") as f:
                self._send(200, f.read(), "application/javascript")
        elif path == "/api/info":
            self._json({"pulse": True, "join_url": JOIN_URL})
        else:
            self._send(404, "Not found", "text/plain")

    def do_POST(self):
        try:
            body = self._body()
            pid = str(body.get("id", ""))[:32]
            if not pid:
                raise ValueError("missing id")
        except (ValueError, json.JSONDecodeError):
            self._json({"error": "bad request"}, 400)
            return
        now = time.time()
        if self.path == "/api/sync":
            presence = body.get("presence") if isinstance(body.get("presence"), dict) else {}
            if len(json.dumps(presence)) > 4096:
                presence = {}
            since = body.get("since", -1)
            since = since if isinstance(since, int) else -1
            with lock:
                state["peers"][pid] = {"presence": presence, "seen": now}
                for k in [k for k, v in state["peers"].items() if now - v["seen"] > PEER_TIMEOUT]:
                    del state["peers"][k]
                peers = [{"id": k, "presence": v["presence"]} for k, v in state["peers"].items()]
                msgs = state["messages"]
                msgs = msgs[-1:] if since < 0 else [m for m in msgs if m["seq"] > since]
            self._json({"peers": peers, "messages": msgs})
        elif self.path == "/api/emit":
            topic = body.get("topic")
            if topic not in ALLOWED_TOPICS or len(json.dumps(body.get("data"))) > 16384:
                self._json({"error": "bad topic or too large"}, 400)
                return
            with lock:
                state["seq"] += 1
                state["messages"].append({"seq": state["seq"], "topic": topic,
                                          "data": body.get("data"), "from": pid})
                del state["messages"][:-MAX_MESSAGES]
            self._json({"ok": True})
        else:
            self._json({"error": "not found"}, 404)


def main():
    global JOIN_URL
    ap = argparse.ArgumentParser(description="Serve the PULSE-LTE dashboard to phones on your network.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--ip", help="address phones should use (default: auto-detect)")
    ap.add_argument("--no-browser", action="store_true", help="don't open the dashboard automatically")
    a = ap.parse_args()

    ips = [a.ip] if a.ip else lan_addresses()
    JOIN_URL = f"http://{ips[0]}:{a.port}/#join"
    server = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)

    print("\n  PULSE-LTE control room is running\n")
    print(f"  Laptop (projector):  http://localhost:{a.port}/")
    print(f"  Phones join at:      {JOIN_URL}   (also shown as a QR code on the page)")
    if len(ips) > 1 and not a.ip:
        print("  Other addresses:     " + ", ".join(f"http://{ip}:{a.port}/#join" for ip in ips[1:]))
        print("  If phones can't connect, restart with --ip <the address on your hotspot/Wi-Fi>")
    print("\n  Phones must be on the same Wi-Fi or hotspot as this laptop.")
    print("  Windows: click 'Allow access' if the firewall asks.  Press Ctrl+C to stop.\n")

    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{a.port}/")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
