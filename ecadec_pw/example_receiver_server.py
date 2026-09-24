"""Minimal example HTTP server that receives forwarded messages and prints them.

Run: python -m ecadec_pw.example_receiver_server
Then point forwarder.py's FORWARD_URL env variable to http://localhost:8000/messages
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "0.0.0.0"
PORT = 8000


class MessageHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = body.decode("utf-8", errors="replace")

        print(f"\nReceived on '{self.path}':")
        print(json.dumps(payload, indent=2))

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format, *args):  # noqa: A002 (BaseHTTPRequestHandler API)
        pass  # suppress default access-log noise; the payload print above is enough


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), MessageHandler)
    print(f"Listening for forwarded messages on http://{HOST}:{PORT}")
    server.serve_forever()
