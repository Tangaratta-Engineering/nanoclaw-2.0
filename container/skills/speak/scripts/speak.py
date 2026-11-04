#!/usr/bin/env python3
"""Text-to-speech for NanoClaw agents: Google Chirp 3 HD when configured, otherwise (or on any Google problem)
local Piper (offline, CPU; no system ffmpeg needed).

Usage: speak "<spoken text>" [--voice google:en-US-Chirp3-HD-Aoede | piper:en_GB-alan-medium | en_GB-alan-medium] [--out file.ogg]
Prints one JSON line {path, duration_secs, voice, provider, fallback_used, chars, truncated}; attach the file with send_file.
The voice defaults to the one configured for this agent in voices.json (by assistant name): a plain string is a
Piper voice, an object {"provider": "google", "voice": "...", "fallback": "<piper id>"} is a Google voice.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.environ.get("PIPER_HOME", "/workspace/projects/.nanoclaw-tools/piper")
VOICES = os.path.join(ROOT, "voices")
HERE = os.path.dirname(os.path.abspath(__file__))
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
MAX_CHARS = int(os.environ.get("SPEAK_MAX_CHARS", "1200"))  # about 80-90 s of speech


def voice_url(name):
    lang_region, speaker, quality = name.split("-", 2)  # en_GB-alan-medium
    lang = lang_region.split("_")[0]
    return f"{HF}/{lang}/{lang_region}/{speaker}/{quality}/{name}"


def config():
    with open(os.path.join(HERE, "..", "voices.json")) as f:
        return json.load(f)


def piper_ids(cfg):
    """Every Piper voice id the config can need: plain strings and the fallbacks of Google entries."""
    ids = set()
    for v in cfg.values():
        if isinstance(v, str):
            ids.add(v)
        elif isinstance(v, dict) and v.get("fallback"):
            ids.add(v["fallback"])
    return ids


def resolve_voice(override, cfg, name):
    """Return (provider, voice, fallback_piper_id). `override` is the --voice flag or None."""
    default_piper = cfg["default"] if isinstance(cfg.get("default"), str) else (cfg["default"].get("fallback") or "en_US-hfc_female-medium")
    if override:
        if override.startswith("google:"):
            entry = cfg.get(name)
            fb = entry.get("fallback") if isinstance(entry, dict) else (entry if isinstance(entry, str) else None)
            return "google", override[len("google:"):], fb or default_piper
        if override.startswith("piper:"):
            return "piper", override[len("piper:"):], None
        return "piper", override, None
    entry = cfg.get(name) or cfg["default"]
    if isinstance(entry, dict):
        fb = entry.get("fallback") or default_piper
        if entry.get("provider", "piper") == "google":
            return "google", entry["voice"], fb
        return "piper", entry.get("voice") or fb, None
    return "piper", entry, None


def assistant_name():
    for p in ("/workspace/agent/container.json",):
        try:
            with open(p) as f:
                return json.load(f).get("assistantName") or ""
        except (OSError, ValueError):
            pass
    return os.environ.get("ASSISTANT_NAME", "")


def clean_for_speech(text):
    """Make text speakable: no markdown, links, code or emoji."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)                 # code blocks
    t = re.sub(r"`([^`]*)`", r"\1", t)                               # inline code
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)                      # images
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)                   # [label](url) -> label
    t = re.sub(r"\(\s*https?://[^\s)]+\s*\)", " ", t)                # (link) in brackets
    t = re.sub(r"https?://[^\s)]+", " ", t)                          # bare links are not read aloud
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)              # headings
    t = re.sub(r"^\s*[>*\-•]\s+", "", t, flags=re.M)                 # quotes and bullets
    t = re.sub(r"(\*\*|__|\*|_|~~)", "", t)                          # emphasis
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", t)  # emoji / symbols
    t = re.sub(r"\$\s?(\d[\d,]*(?:\.\d+)?)", r"\1 dollars", t)       # $1,789 -> 1,789 dollars
    t = t.replace("&", " and ").replace("→", " to ").replace("—", ", ").replace("–", " to ")
    t = re.sub(r"\s*\n+\s*", ". ", t)                                # line breaks -> sentence breaks
    t = re.sub(r"\.\s*\.", ".", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)                          # no space before punctuation
    t = re.sub(r"\(\s*\)", "", t)                                  # empty brackets
    return re.sub(r"\s+", " ", t).strip(" .") + "."


def truncate(text, limit):
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return (cut[: end + 1] if end > limit * 0.5 else cut), True


def download_voices():
    os.makedirs(VOICES, exist_ok=True)
    names = sorted(piper_ids(config()))
    for n in names:
        for ext in (".onnx", ".onnx.json"):
            dest = os.path.join(VOICES, n + ext)
            if not os.path.exists(dest):
                print(f"downloading {n}{ext} ...", flush=True)
                urllib.request.urlretrieve(voice_url(n) + ext, dest)
        print(f"voice '{n}' ready")
    return 0


def to_opus_ogg(wav_path, out_path):
    """Convert a WAV file to Opus-in-Ogg, 48 kHz mono, 32 kbit/s. Returns the duration in seconds."""
    sys.path.insert(0, os.path.join(ROOT, "site"))
    import av

    samples = 0
    with av.open(wav_path) as src, av.open(out_path, "w", format="ogg") as dst:
        out = dst.add_stream("libopus", rate=48000, layout="mono")
        out.bit_rate = 32000
        resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)

        def push(frames):
            nonlocal samples
            for f in frames:
                samples += f.samples
                for pkt in out.encode(f):
                    dst.mux(pkt)

        for frame in src.decode(audio=0):
            push(resampler.resample(frame))
        push(resampler.resample(None))
        for pkt in out.encode(None):
            dst.mux(pkt)
    return samples / 48000.0


class SpeakError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def synth_piper(text, voice, out):
    """Synthesise with local Piper into `out` (Ogg Opus). Returns the duration in seconds."""
    model = os.path.join(VOICES, voice + ".onnx")
    site = os.path.join(ROOT, "site")
    if not os.path.isfile(model) or not os.path.isdir(os.path.join(site, "piper")):
        raise SpeakError(3, "text-to-speech is not installed on this host.\n"
                            "Ask George to run container/skills/speak/setup.sh on the host (one-time, free, local).")
    env = dict(os.environ, PYTHONPATH=site + os.pathsep + os.environ.get("PYTHONPATH", ""))
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "speech.wav")
        r = subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", wav, "--", text],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0 or not os.path.isfile(wav):
            raise SpeakError(4, f"synthesis failed: {r.stderr.strip()[-300:]}")
        # Opus in Ogg at 48 kHz mono: plays everywhere and is the format Discord voice messages use.
        # Encoded with PyAV's bundled codecs so no system ffmpeg is needed (the agent image has none).
        try:
            return to_opus_ogg(wav, out)
        except Exception as e:
            raise SpeakError(4, f"audio conversion failed: {e}")


def ogg_seconds(path):
    """Duration of an Ogg file, using PyAV when available; otherwise 0.0."""
    try:
        sys.path.insert(0, os.path.join(ROOT, "site"))
        import av

        with av.open(path) as c:
            return (c.duration or 0) / 1_000_000
    except Exception:
        return 0.0


def speak(text, provider, voice, fallback, out):
    """Run the chosen provider; any Google problem falls back to Piper. Returns (seconds, provider, voice, fallback_used)."""
    if provider == "google":
        try:
            import google_tts

            google_tts.check_budget(len(text))
            google_tts.synthesize(text, voice, out, encoder=to_opus_ogg)
            google_tts.record_usage(len(text))
            return ogg_seconds(out), "google", voice, False
        except Exception as e:  # noqa: BLE001 - whatever went wrong, the user still gets a voice reply
            print(f"speak: Google voice failed ({e}); using the local voice instead", file=sys.stderr)
            if not fallback:
                raise SpeakError(4, "Google voice failed and no fallback voice is configured")
            return synth_piper(text, fallback, out), "piper", fallback, True
    return synth_piper(text, voice, out), "piper", voice, False


def main():
    ap = argparse.ArgumentParser(description="Speak text with a Google or local Piper voice.")
    ap.add_argument("text", nargs="?", help='text to speak, or "-" to read stdin')
    ap.add_argument("--voice", help="google:<name> | piper:<id> | <piper id> (default: this agent's voice from voices.json)")
    ap.add_argument("--out", help="output .ogg path (default: a new file under /workspace/agent/voice-replies/)")
    ap.add_argument("--keep-links", action="store_true", help="do not strip links (not recommended)")
    ap.add_argument("--download-voices", action="store_true", help="fetch the Piper voices named in voices.json and exit (setup)")
    args = ap.parse_args()

    if args.download_voices:
        return download_voices()
    if not args.text:
        ap.error("text is required")
    raw = sys.stdin.read() if args.text == "-" else args.text

    cfg = config()
    provider, voice, fallback = resolve_voice(args.voice, cfg, assistant_name())

    text = clean_for_speech(raw)
    text, truncated = truncate(text, MAX_CHARS)
    if len(text) < 2:
        print("speak: nothing speakable in that text", file=sys.stderr)
        return 2

    out = args.out
    if not out:
        d = "/workspace/agent/voice-replies"
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, f"reply-{int(time.time() * 1000)}.ogg")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    try:
        seconds, provider, voice, fallback_used = speak(text, provider, voice, fallback, out)
    except SpeakError as e:
        print(f"speak: {e}", file=sys.stderr)
        return e.code
    print(json.dumps({"path": out, "duration_secs": round(seconds, 1), "voice": voice, "provider": provider,
                      "fallback_used": fallback_used, "chars": len(text), "truncated": truncated}))
    if truncated:
        print("speak: text was cut to ~%d characters; send the full text as a normal message." % MAX_CHARS, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
