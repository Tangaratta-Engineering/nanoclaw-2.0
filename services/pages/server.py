#!/usr/bin/env python3
"""Serve the published pages folder on the home network (read only, no directory listings).

The pages folder is ~/projects/.nanoclaw-data/pages (agents write to it through the `publish` skill). nginx shows it as
https://pages.home. Binds to the LAN address only.
"""
import http.server, os, sys

ROOT = os.environ.get("PAGES_DIR", os.path.expanduser("~/projects/.nanoclaw-data/pages"))
HOST = os.environ.get("PAGES_HOST", "192.168.3.13")
PORT = int(os.environ.get("PAGES_PORT", "8088"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def list_directory(self, path):  # no browsing of other pages
        self.send_error(404)
        return None

    def do_GET(self):
        # never serve bookkeeping files such as .publish.json
        if any(part.startswith(".") for part in self.path.split("?")[0].split("/")):
            return self.send_error(404)
        return super().do_GET()

    do_HEAD = do_GET

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
