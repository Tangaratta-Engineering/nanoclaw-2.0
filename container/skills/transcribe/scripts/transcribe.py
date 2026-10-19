#!/usr/bin/env python3
"""Speech-to-text for NanoClaw agents.

Engine order (default `auto`): Groq Whisper (fast, accurate; API key injected by the
OneCLI gateway, never seen here) -> local faster-whisper on CPU (offline fallback).
Every result carries a reliability assessment so callers can say "I'm not sure"
instead of presenting a bad transcript as fact.

Usage: transcribe <audio-or-video-file> [--engine auto|cloud|local] [--language xx]
                  [--translate] [--timestamps] [--json] [--model small]
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time

HOME = os.environ.get("WHISPER_HOME", "/workspace/projects/.nanoclaw-tools/whisper")
sys.path.insert(0, os.path.join(HOME, "site"))
MODELS = os.path.join(HOME, "models")
HERE = os.path.dirname(os.path.abspath(__file__))
GROQ_BASE = "https://api.groq.com/openai/v1/audio"
CLOUD_PRIMARY = os.environ.get("GROQ_STT_MODEL", "whisper-large-v3")
CLOUD_CROSSCHECK = "whisper-large-v3-turbo"
MAX_CLOUD_BYTES = 20 * 1024 * 1024


def fmt_ts(t):
    m, s = divmod(int(t), 60)
    return f"{m:02d}:{s:02d}"


def vocabulary():
    try:
        with open(os.path.join(HERE, "..", "vocabulary.txt")) as f:
            return "Names: " + f.read().strip()
    except OSError:
        return ""


# ---------------------------------------------------------------- reliability
def assess(segments, duration, text):
    """Return (quality, [reasons]) from segment stats. quality: good | uncertain | poor."""
    issues, poor = [], False
    words = len(text.split())
    sents = [s.strip().lower() for s in re.split(r"[.!?]+", text) if s.strip()]
    run = best = 1
    for a, b in zip(sents, sents[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    if best >= 3:
        issues.append("the same sentence repeats (typical of a hallucination)")
        poor = True
    if duration >= 4 and words / duration < 0.6:
        issues.append("very little text for the audio length (speech may have been missed)")
    weights = [max(s.get("end", 0) - s.get("start", 0), 0.01) for s in segments]
    lps = [s.get("avg_logprob") for s in segments]
    if segments and all(isinstance(x, (int, float)) for x in lps):
        mean_lp = sum(lp * w for lp, w in zip(lps, weights)) / sum(weights)
        if mean_lp < -1.0:
            issues.append(f"low model confidence (avg logprob {mean_lp:.2f})")
            poor = True
        elif mean_lp < -0.7:
            issues.append(f"modest model confidence (avg logprob {mean_lp:.2f})")
    if any((s.get("compression_ratio") or 0) > 2.4 for s in segments):
        issues.append("repetitive text pattern")
    if text and any((s.get("no_speech_prob") or 0) > 0.6 for s in segments):
        issues.append("part of the audio may not be speech")
    return ("poor" if poor else "uncertain" if issues else "good"), issues


# --------------------------------------------------------------------- cloud
def cloud(path, model, language, translate, use_prompt=True):
    if os.path.getsize(path) > MAX_CLOUD_BYTES:
        raise RuntimeError("file too large for the cloud engine")
    endpoint = "translations" if translate else "transcriptions"
    cmd = ["curl", "-sS", "-m", "90", "-w", "\n%{http_code}", f"{GROQ_BASE}/{endpoint}",
           "-F", f"file=@{path}", "-F", f"model={model}", "-F", "response_format=verbose_json",
           "-F", "temperature=0"]
    if language and not translate:
        cmd += ["-F", f"language={language}"]
    prompt = vocabulary() if use_prompt else ""
    if prompt:
        cmd += ["-F", f"prompt={prompt}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"network error ({r.stderr.strip()[:120] or r.returncode})")
    body, _, code = r.stdout.rpartition("\n")
    if code != "200":
        try:
            msg = json.loads(body)["error"]["message"]
        except Exception:
            msg = body[:120]
        raise RuntimeError(f"HTTP {code}: {msg}")
    d = json.loads(body)
    segs = [{"start": round(s.get("start", 0), 2), "end": round(s.get("end", 0), 2),
             "text": s.get("text", "").strip(), "avg_logprob": s.get("avg_logprob"),
             "compression_ratio": s.get("compression_ratio"), "no_speech_prob": s.get("no_speech_prob")}
            for s in d.get("segments", [])]
    text = (d.get("text") or " ".join(s["text"] for s in segs)).strip()
    duration = float(d.get("duration") or (segs[-1]["end"] if segs else 0))
    return {"engine": f"groq {model}", "language": d.get("language", "unknown"), "duration": duration,
            "text": text, "segments": segs}


# --------------------------------------------------------------------- local
def local(path, model_name, language, translate, download_only=False):
    if not download_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8",
                         cpu_threads=int(os.environ.get("WHISPER_THREADS", "3")),
                         download_root=MODELS, local_files_only=not download_only)
    if download_only:
        return None
    segs, info = model.transcribe(path, language=language, task="translate" if translate else "transcribe",
                                  vad_filter=True, beam_size=5, condition_on_previous_text=False)
    out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
            "avg_logprob": s.avg_logprob, "compression_ratio": s.compression_ratio,
            "no_speech_prob": s.no_speech_prob} for s in segs]
    return {"engine": f"local faster-whisper {model_name}", "language": info.language,
            "language_probability": round(info.language_probability, 3), "duration": info.duration,
            "text": " ".join(s["text"] for s in out).strip(), "segments": out}


def finish(res, started, notes):
    quality, issues = assess(res["segments"], res["duration"], res["text"])
    res.update(quality=quality, issues=issues, notes=notes, seconds_to_process=round(time.time() - started, 1))
    return res


def main():
    ap = argparse.ArgumentParser(description="Transcribe speech to text (cloud first, local fallback).")
    ap.add_argument("audio", nargs="?", help="audio or video file (ogg/opus, mp3, m4a, wav, webm, mp4, ...)")
    ap.add_argument("--engine", choices=["auto", "cloud", "local"], default=os.environ.get("TRANSCRIBE_ENGINE", "auto"))
    ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", "small"),
                    help="local model: tiny|base|small|medium (default small)")
    ap.add_argument("--language", help="ISO code such as en, es, zh; default: auto-detect")
    ap.add_argument("--translate", action="store_true", help="speech -> English translation")
    ap.add_argument("--timestamps", action="store_true", help="prefix each segment with [mm:ss]")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--download-only", action="store_true", help="fetch the local model and exit (setup)")
    args = ap.parse_args()

    if args.download_only:
        try:
            local(None, args.model, None, False, download_only=True)
        except Exception as e:
            print(f"transcribe: could not download model '{args.model}': {e}", file=sys.stderr)
            return 3
        print(f"model '{args.model}' ready in {MODELS}")
        return 0
    if not args.audio:
        ap.error("an audio file is required")
    if not os.path.isfile(args.audio):
        print(f"transcribe: file not found: {args.audio}", file=sys.stderr)
        return 2

    started, notes, res = time.time(), [], None
    if args.engine in ("auto", "cloud"):
        try:
            res = finish(cloud(args.audio, CLOUD_PRIMARY, args.language, args.translate), started, notes)
            # Always cross-check with the second Groq model (about 0.3 s), WITHOUT the name-hint
            # prompt (on unclear audio the prompt gets echoed back as invented names): one model's
            # own confidence cannot catch a confident-but-wrong transcript, disagreement can.
            if res["duration"] <= 180:
                try:
                    alt = finish(cloud(args.audio, CLOUD_CROSSCHECK, args.language, args.translate, use_prompt=False), started, [])
                    a = re.findall(r"[a-z0-9']+", res["text"].lower())
                    b = re.findall(r"[a-z0-9']+", alt["text"].lower())
                    agree = difflib.SequenceMatcher(None, a, b).ratio() if (a or b) else 1.0
                    res["agreement"] = round(agree, 2)
                    if agree < 0.6:
                        res["issues"].append(f"the two Whisper models disagree ({agree:.0%} similar)")
                        if res["quality"] == "good":
                            res["quality"] = "uncertain"
                    res["alternative"] = {"engine": alt["engine"], "text": alt["text"], "quality": alt["quality"]}
                    if res["quality"] != "good" and alt["quality"] == "good" and agree >= 0.6:
                        res, alt = alt, res
                        res["alternative"] = {"engine": alt["engine"], "text": alt["text"], "quality": alt["quality"]}
                except RuntimeError:
                    pass
        except RuntimeError as e:
            if args.engine == "cloud":
                print(f"transcribe: cloud engine failed: {e}", file=sys.stderr)
                return 4
            notes.append(f"cloud engine unavailable ({e}); used the local model")
    if res is None:
        if not os.path.isdir(os.path.join(HOME, "site", "faster_whisper")):
            print("transcribe: no engine available (cloud failed and local model is not installed).", file=sys.stderr)
            print("Ask George to run container/skills/transcribe/setup.sh on the host.", file=sys.stderr)
            return 3
        try:
            res = finish(local(args.audio, args.model, args.language, args.translate), started, notes)
        except Exception as e:
            print(f"transcribe: could not load model '{args.model}': {e}", file=sys.stderr)
            return 3

    if args.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    head = (f"[engine={res['engine']} · language={res['language']} · audio={res['duration']:.1f}s · "
            f"took={res['seconds_to_process']}s · reliability={res['quality']}]")
    print(head)
    for n in res["notes"]:
        print(f"note: {n}")
    if res["issues"]:
        print("reliability warnings: " + "; ".join(res["issues"]))
    if not res["text"]:
        print("(no speech detected)")
    elif args.timestamps:
        for s in res["segments"]:
            print(f"[{fmt_ts(s['start'])}] {s['text']}")
    else:
        print(res["text"])
    if res.get("alternative") and res["alternative"]["text"].strip() != res["text"].strip():
        print(f"alternative ({res['alternative']['engine']}, {res['alternative']['quality']}): {res['alternative']['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
