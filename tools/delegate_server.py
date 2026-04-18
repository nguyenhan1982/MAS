"""
delegate_server.py
HTTP server đơn giản để Agent gọi qua web_fetch.
Nhận task, chạy delegate.py, trả kết quả.

Chạy: python tools/delegate_server.py
Lắng nghe: http://127.0.0.1:19788

API:
  POST /delegate
  Body: {"agent": "votranh", "message": "[TASK] ..."}
  Response: {"result": "...", "success": true}

  GET /ping
  Response: {"ok": true}
"""

import json
import subprocess
import sys
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DELEGATE_PY = Path(__file__).parent / "delegate.py"
PORT = 19788


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

    def send_json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/ping":
            self.send_json(200, {"ok": True, "service": "delegate_server"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/delegate":
            self.send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")

        try:
            data = json.loads(body)
        except Exception:
            self.send_json(400, {"error": "invalid JSON"})
            return

        agent = data.get("agent", "votranh")
        message = data.get("message", "")

        if not message:
            self.send_json(400, {"error": "message is required"})
            return

        print(f"→ Delegate to {agent}: {message[:80]}...")

        try:
            result = subprocess.run(
                [sys.executable, str(DELEGATE_PY), agent, message],
                capture_output=True,
                text=True,
                timeout=180,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout.strip()
            # Bỏ dòng đầu "→ Giao task..." và "  Message:..."
            lines = output.split("\n")
            clean = "\n".join(l for l in lines if not l.startswith("→") and not l.startswith("  Message:")).strip()

            self.send_json(200, {
                "success": result.returncode == 0,
                "result": clean or output,
                "agent": agent,
            })
        except subprocess.TimeoutExpired:
            self.send_json(200, {"success": False, "result": "[ERROR] Timeout sau 180 giây", "agent": agent})
        except Exception as e:
            self.send_json(500, {"success": False, "result": str(e), "agent": agent})


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Delegate server running on http://127.0.0.1:{PORT}")
    print(f"Test: curl http://127.0.0.1:{PORT}/ping")
    print("Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
