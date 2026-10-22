#!/usr/bin/env python3
"""Long-running Piper worker for low-latency speech (used by the live voice service).

Loads the voice once, then reads one JSON request per line on stdin and answers one JSON line on stdout:
  in : {"id": 1, "text": "Hello there.", "out": "/out/a.ogg"}
  out: {"id": 1, "path": "/out/a.ogg", "duration_secs": 1.2, "ms": 380}   or   {"id": 1, "error": "..."}
Same text cleaning and Opus/Ogg output as `speak`; see speak.py.
"""
import argparse
import json
import os
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speak  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True)
    args = ap.parse_args()
    site = os.path.join(speak.ROOT, "site")
    sys.path.insert(0, site)
    from piper import PiperVoice  # noqa: E402

    voice = PiperVoice.load(os.path.join(speak.VOICES, args.voice + ".onnx"))
    print(json.dumps({"ready": True, "voice": args.voice}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        rid = None
        try:
            req = json.loads(line)
            rid = req.get("id")
            t0 = time.time()
            text, _ = speak.truncate(speak.clean_for_speech(req["text"]), speak.MAX_CHARS)
            if len(text) < 2:
                raise ValueError("nothing speakable")
            with tempfile.TemporaryDirectory() as tmp:
                wav = os.path.join(tmp, "s.wav")
                with wave.open(wav, "wb") as wf:
                    voice.synthesize_wav(text, wf)
                seconds = speak.to_opus_ogg(wav, req["out"])
            print(json.dumps({"id": rid, "path": req["out"], "duration_secs": round(seconds, 2), "ms": int((time.time() - t0) * 1000)}), flush=True)
        except Exception as e:  # noqa: BLE001 - one bad request must not kill the worker
            print(json.dumps({"id": rid, "error": f"{type(e).__name__}: {e}"}), flush=True)


if __name__ == "__main__":
    main()
