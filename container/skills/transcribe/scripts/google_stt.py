"""Google Cloud Speech-to-Text engine for the transcribe skill (optional: `--engine google`).

Opt-in alternative to Groq for live calls. Uses the v1 REST API; the API key is injected by the
OneCLI gateway (vault secret for speech.googleapis.com), never seen here. WAV input only (the voice
service sends 16 kHz mono WAV); anything else raises so the caller falls back to Groq.

A month's usage is counted from the `totalBilledTime` Google returns (billed to the second, measured: a
6.6 s clip billed 7 s) in a small shared file, and a monthly limit sends calls back to Groq.
"""
import base64
import json
import math
import os
import subprocess
import time
import wave

URL = os.environ.get("GOOGLE_STT_URL", "https://speech.googleapis.com/v1/speech:recognize")
MODEL = os.environ.get("GOOGLE_STT_MODEL", "latest_long")
DEFAULT_LANGUAGE = os.environ.get("GOOGLE_STT_LANGUAGE", "en-AU")
USAGE_FILE = os.environ.get("STT_GOOGLE_USAGE") or os.path.join(
    os.environ.get("HOME", ""), "projects/.nanoclaw-data/voice/stt-google-usage.json")
MAX_MINUTES = float(os.environ.get("STT_GOOGLE_MAX_MINUTES", "300"))
MAX_BYTES = 9_000_000      # the synchronous API takes up to 10 MB and 60 s of audio
MAX_SECONDS = 58


class Unavailable(RuntimeError):
    """Google cannot be used for this clip (limit reached, unsupported file, API error)."""


def language_code(lang):
    """`None` or a bare `en` means the configured default (en-AU); `fr-FR` style codes pass through."""
    if not lang or ("-" not in lang and lang.lower() == "en"):
        return DEFAULT_LANGUAGE
    return lang


def wav_seconds(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError):
        raise Unavailable("the Google engine only takes WAV audio")


def phrases(vocabulary_text):
    """Names for the speech hint, from the skill's vocabulary.txt ("Names: Tiff, Timmy, ...")."""
    body = vocabulary_text.split(":", 1)[-1]
    return [p.strip() for p in body.split(",") if p.strip()][:100]


def build_request(audio_bytes, language, hint_phrases, model=MODEL):
    cfg = {"languageCode": language_code(language), "model": model, "enableAutomaticPunctuation": True}
    if hint_phrases:
        cfg["speechContexts"] = [{"phrases": hint_phrases, "boost": 10}]
    return {"config": cfg, "audio": {"content": base64.b64encode(audio_bytes).decode("ascii")}}


def billed_seconds(resp, duration):
    t = str(resp.get("totalBilledTime", "")).rstrip("s")
    try:
        return float(t)
    except ValueError:
        return float(math.ceil(max(duration, 1.0)))


def parse_response(resp, duration, model=MODEL):
    segs, texts, confs = [], [], []
    for r in resp.get("results", []):
        alts = r.get("alternatives") or []
        if not alts or not alts[0].get("transcript", "").strip():
            continue
        a = alts[0]
        end = str(r.get("resultEndTime", "")).rstrip("s")
        segs.append({"start": segs[-1]["end"] if segs else 0.0, "end": float(end) if end else duration,
                     "text": a["transcript"].strip(), "avg_logprob": None,
                     "compression_ratio": None, "no_speech_prob": None})
        texts.append(a["transcript"].strip())
        if a.get("confidence") is not None:
            confs.append(float(a["confidence"]))
    return {"engine": f"google v1 {model}", "language": "en", "duration": duration, "text": " ".join(texts),
            "segments": segs, "confidence": round(sum(confs) / len(confs), 3) if confs else None,
            "billed_seconds": billed_seconds(resp, duration)}


def confidence_quality(conf, current):
    """Fold Google's own confidence into the skill's good / uncertain / poor rating. Returns (quality, issue|None)."""
    if conf is None:
        return current, None
    if conf < 0.6:
        return "poor", f"low Google confidence ({conf:.2f})"
    if conf < 0.8 and current == "good":
        return "uncertain", f"modest Google confidence ({conf:.2f})"
    return current, None


# ---------------------------------------------------------------------- usage
def _month(now):
    return time.strftime("%Y-%m", time.gmtime(now))


def used_seconds(path=None, now=None):
    path = path or USAGE_FILE
    try:
        with open(path) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return 0.0
    return float(d.get("seconds", 0)) if d.get("month") == _month(now or time.time()) else 0.0


def add_usage(seconds, path=None, now=None):
    path = path or USAGE_FILE
    now = now or time.time()
    total = used_seconds(path, now) + seconds
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump({"month": _month(now), "seconds": total, "minutes": round(total / 60, 1)}, f)
    os.replace(tmp, path)
    return total


# ------------------------------------------------------------------ recognise
def transcribe(path, language, hint_phrases, runner=subprocess.run, usage_path=None, max_minutes=None, now=None):
    max_minutes = MAX_MINUTES if max_minutes is None else max_minutes
    if used_seconds(usage_path, now) >= max_minutes * 60:
        raise Unavailable(f"monthly Google limit of {max_minutes:g} minutes reached")
    if os.path.getsize(path) > MAX_BYTES:
        raise Unavailable("clip too large for the Google engine")
    duration = wav_seconds(path)
    if duration > MAX_SECONDS:
        raise Unavailable("clip too long for the Google engine")
    with open(path, "rb") as f:
        body = json.dumps(build_request(f.read(), language, hint_phrases))
    r = runner(["curl", "-sS", "-m", "30", "-w", "\n%{http_code}", "-H", "Content-Type: application/json",
                "--data-binary", "@-", URL], input=body, capture_output=True, text=True)
    if r.returncode != 0:
        raise Unavailable(f"network error ({r.stderr.strip()[:120] or r.returncode})")
    out, _, code = r.stdout.rpartition("\n")
    if code != "200":
        try:
            msg = json.loads(out)["error"]["message"]
        except Exception:
            msg = out[:120]
        raise Unavailable(f"HTTP {code}: {msg[:160]}")
    res = parse_response(json.loads(out), duration)
    add_usage(res["billed_seconds"], usage_path, now)
    return res
