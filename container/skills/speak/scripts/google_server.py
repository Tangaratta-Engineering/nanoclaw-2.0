#!/usr/bin/env python3
"""Long-running Google TTS worker for the live voice service (same line protocol as speak_server.py).

Run it under the OneCLI gateway so the API key is injected into the requests (the host service starts it as
`onecli run --agent <id> -- python3 google_server.py --voice <name>`). Standard library only.

in : {"id": 1, "text": "Hello there.", "out": "/tmp/a.ogg"}      one JSON request per line on stdin
out: {"id": 1, "path": "/tmp/a.ogg", "ms": 740}  or  {"id": 1, "error": "..."}  one JSON line on stdout

Requests run in parallel (the service synthesises the next sentence while the current one plays). Each one
checks and updates the shared monthly character counter, so `speak` and the live calls count together.
"""
import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import google_tts  # noqa: E402

lock = threading.Lock()


def reply(obj):
    with lock:
        print(json.dumps(obj), flush=True)


def handle(req, voice):
    rid = req.get("id")
    t0 = time.time()
    try:
        text = req["text"]
        google_tts.check_budget(len(text))
        google_tts.synthesize(text, voice, req["out"])  # encoder=None: one request, Ogg Opus straight back
        google_tts.record_usage(len(text))
        reply({"id": rid, "path": req["out"], "ms": int((time.time() - t0) * 1000)})
    except Exception as e:  # noqa: BLE001 - one bad request must not kill the worker
        reply({"id": rid, "error": f"{type(e).__name__}: {e}"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True, help="e.g. en-US-Chirp3-HD-Aoede")
    args = ap.parse_args()
    google_tts.language_of(args.voice)  # fail fast on a malformed name
    reply({"ready": True, "voice": args.voice})
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except ValueError:
                continue
            ex.submit(handle, req, args.voice)


if __name__ == "__main__":
    main()
