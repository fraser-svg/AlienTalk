#!/usr/bin/env python3
"""Alchemist API Proxy — sits between any client and Anthropic's API.

Intercepts POST /v1/messages requests, compiles all user message content
through Alchemist Prime, then forwards to Anthropic. Works with any
language, framework, or tool that calls the Anthropic API.

Usage:
    # Start the proxy (default: localhost:8080)
    python integrations/proxy.py

    # Start on custom port
    python integrations/proxy.py --port 9090

    # With echo directive
    python integrations/proxy.py --echo

    # Verbose mode (prints compression stats)
    python integrations/proxy.py --verbose

    # Then point your client at the proxy instead of api.anthropic.com:
    #   export ANTHROPIC_BASE_URL=http://localhost:8080

    # Python SDK:
    #   client = Anthropic(base_url="http://localhost:8080")

    # curl:
    #   curl http://localhost:8080/v1/messages -H "x-api-key: ..." -d '{...}'
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alchemist import count_tokens
from alchemist_prime import AlchemistPrime

ANTHROPIC_API = "https://api.anthropic.com"
MIN_TOKENS = 20

_prime: AlchemistPrime = None  # type: ignore
_verbose: bool = False


class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler that intercepts /v1/messages and compiles prompts."""

    def do_POST(self) -> None:
        if self.path.startswith("/v1/messages"):
            self._handle_messages()
        else:
            self._passthrough("POST")

    def do_GET(self) -> None:
        self._passthrough("GET")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _handle_messages(self) -> None:
        body = self._read_body()

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._forward(body)
            return

        # Compile user messages
        total_orig = 0
        total_comp = 0
        compiled_count = 0

        if "messages" in data:
            for msg in data["messages"]:
                if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    original = msg["content"]
                    orig_tokens = count_tokens(original)

                    if orig_tokens >= MIN_TOKENS:
                        compiled = _prime.compile(original)
                        msg["content"] = compiled
                        total_orig += orig_tokens
                        total_comp += count_tokens(compiled)
                        compiled_count += 1
                    else:
                        total_orig += orig_tokens
                        total_comp += orig_tokens

        if _verbose and compiled_count > 0:
            pct = round((1 - total_comp / total_orig) * 100, 1) if total_orig else 0
            print(f"[alchemist-proxy] {total_orig}→{total_comp} tokens "
                  f"({pct}% saved, {compiled_count} messages)", flush=True)

        self._forward(json.dumps(data).encode())

    def _forward(self, body: bytes) -> None:
        """Forward request to Anthropic API."""
        url = f"{ANTHROPIC_API}{self.path}"

        headers = {}
        for key in self.headers:
            if key.lower() not in ("host", "content-length"):
                headers[key] = self.headers[key]
        headers["Content-Length"] = str(len(body))

        req = Request(url, data=body, headers=headers, method="POST")

        try:
            with urlopen(req) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for key, val in resp.getheaders():
                    if key.lower() not in ("transfer-encoding",):
                        self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp_body)
        except HTTPError as e:
            self.send_response(e.code)
            for key, val in e.headers.items():
                if key.lower() not in ("transfer-encoding",):
                    self.send_header(key, val)
            self.end_headers()
            self.wfile.write(e.read())

    def _passthrough(self, method: str) -> None:
        body = self._read_body() if method == "POST" else b""
        self._forward(body)

    def log_message(self, format, *args) -> None:
        if _verbose:
            super().log_message(format, *args)


def main() -> None:
    global _prime, _verbose

    parser = argparse.ArgumentParser(
        description="Alchemist API Proxy — auto-compiles prompts before forwarding to Anthropic"
    )
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--echo", action="store_true", help="Append echo directive")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print compression stats")
    args = parser.parse_args()

    _prime = AlchemistPrime(echo=args.echo)
    _verbose = args.verbose

    server = HTTPServer(("127.0.0.1", args.port), ProxyHandler)
    print(f"Alchemist proxy listening on http://127.0.0.1:{args.port}")
    print(f"  Echo: {'on' if args.echo else 'off'}")
    print(f"  Point your client at: http://127.0.0.1:{args.port}")
    print(f"  export ANTHROPIC_BASE_URL=http://127.0.0.1:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
