import json
import webbrowser
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

from token_anatomy.config import CLAUDE_DIR, PORT, RATES
from token_anatomy.parser import parse_data

TEMPLATE_PATH = Path(__file__).parent / "template.html"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass   # silence request logging

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(TEMPLATE_PATH.read_bytes())

        elif path == "/api/stats":
            try:
                data = parse_data()
            except Exception as exc:
                data = {"error": str(exc)}
            body = json.dumps(data, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


def main():
    url = f"http://localhost:{PORT}"
    print(f"\n  ⬡  Token Anatomy")
    print(f"  Reading from : {CLAUDE_DIR}")
    print(f"  Dashboard    : {url}")
    print(f"  Rates        : input=${RATES['input']}/1M  output=${RATES['output']}/1M  "
          f"cache_read=${RATES['cache_read']}/1M  cache_write=${RATES['cache_write']}/1M")
    print(f"\n  Press Ctrl+C to stop.\n")

    def _open():
        import time; time.sleep(0.8)
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()

    server = HTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")

if __name__ == "__main__":
    main()
