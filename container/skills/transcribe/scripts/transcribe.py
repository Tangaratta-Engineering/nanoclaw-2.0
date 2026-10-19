#!/usr/bin/env python3
"""Local, offline speech-to-text for NanoClaw agents (faster-whisper on CPU).

Usage: transcribe <audio-or-video-file> [--language xx] [--translate] [--timestamps] [--json]
Model files and Python packages live under WHISPER_HOME (see setup.sh); nothing is
sent over the network when transcribing.
"""
import argparse
import json
import os
import sys
import time

HOME = os.environ.get("WHISPER_HOME", "/workspace/projects/.nanoclaw-tools/whisper")
sys.path.insert(0, os.path.join(HOME, "site"))
MODELS = os.path.join(HOME, "models")


def fmt_ts(t: float) -> str:
    m, s = divmod(int(t), 60)
    return f"{m:02d}:{s:02d}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe speech to text (offline, CPU).")
    ap.add_argument("audio", nargs="?", help="audio or video file (ogg/opus, mp3, m4a, wav, webm, mp4, ...)")
    ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", "base"),
                    help="tiny|base|small|medium (default base; larger = slower, more accurate)")
    ap.add_argument("--language", help="ISO code such as en, es, zh; default: auto-detect")
    ap.add_argument("--translate", action="store_true",
                    help="use Whisper's built-in speech->English translation (otherwise transcribe in the spoken language)")
    ap.add_argument("--timestamps", action="store_true", help="prefix each segment with [mm:ss]")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--download-only", action="store_true", help="fetch the model into the cache and exit (setup)")
    args = ap.parse_args()

    if not args.download_only:
        if not args.audio:
            ap.error("an audio file is required")
        if not os.path.isfile(args.audio):
            print(f"transcribe: file not found: {args.audio}", file=sys.stderr)
            return 2
        os.environ["HF_HUB_OFFLINE"] = "1"  # transcribing never touches the network

    from faster_whisper import WhisperModel

    threads = int(os.environ.get("WHISPER_THREADS", "3"))
    try:
        model = WhisperModel(
            args.model,
            device="cpu",
            compute_type="int8",
            cpu_threads=threads,
            download_root=MODELS,
            local_files_only=not args.download_only,
        )
    except Exception as e:  # model missing in offline mode, corrupt cache, etc.
        print(f"transcribe: could not load model '{args.model}': {e}", file=sys.stderr)
        print("Ask George to run container/skills/transcribe/setup.sh on the host.", file=sys.stderr)
        return 3

    if args.download_only:
        print(f"model '{args.model}' ready in {MODELS}")
        return 0

    started = time.time()
    segments, info = model.transcribe(
        args.audio,
        language=args.language,
        task="translate" if args.translate else "transcribe",
        vad_filter=True,
        beam_size=5,
    )
    segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]
    text = " ".join(s["text"] for s in segs).strip()
    took = time.time() - started

    meta = {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration_seconds": round(info.duration, 1),
        "model": args.model,
        "task": "translate" if args.translate else "transcribe",
        "seconds_to_process": round(took, 1),
    }
    if args.json:
        print(json.dumps({**meta, "text": text, "segments": segs}, ensure_ascii=False))
        return 0

    print(f"[language={meta['language']} ({meta['language_probability']:.0%}) · audio={meta['duration_seconds']}s · "
          f"model={args.model} · took={meta['seconds_to_process']}s]")
    if not text:
        print("(no speech detected)")
    elif args.timestamps:
        for s in segs:
            print(f"[{fmt_ts(s['start'])}] {s['text']}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
