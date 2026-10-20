#!/usr/bin/env python3
"""Text-to-speech for NanoClaw agents (Piper, local, offline, CPU; no system ffmpeg needed).

Usage: speak "<spoken text>" [--voice en_GB-alan-medium] [--out file.ogg]
Prints one JSON line {path, duration_secs, voice, chars, truncated}; attach the file with send_file.
The voice defaults to the one configured for this agent in voices.json (by assistant name).
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
    names = sorted({v for v in config().values()})
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


def main():
    ap = argparse.ArgumentParser(description="Speak text with a local Piper voice.")
    ap.add_argument("text", nargs="?", help='text to speak, or "-" to read stdin')
    ap.add_argument("--voice", help="voice id, e.g. en_GB-alan-medium (default: this agent's voice from voices.json)")
    ap.add_argument("--out", help="output .ogg path (default: a new file under /workspace/agent/voice-replies/)")
    ap.add_argument("--keep-links", action="store_true", help="do not strip links (not recommended)")
    ap.add_argument("--download-voices", action="store_true", help="fetch the voices named in voices.json and exit (setup)")
    args = ap.parse_args()

    if args.download_voices:
        return download_voices()
    if not args.text:
        ap.error("text is required")
    raw = sys.stdin.read() if args.text == "-" else args.text

    cfg = config()
    voice = args.voice or cfg.get(assistant_name()) or cfg["default"]
    model = os.path.join(VOICES, voice + ".onnx")
    site = os.path.join(ROOT, "site")
    if not os.path.isfile(model) or not os.path.isdir(os.path.join(site, "piper")):
        print("speak: text-to-speech is not installed on this host.", file=sys.stderr)
        print("Ask George to run container/skills/speak/setup.sh on the host (one-time, free, local).", file=sys.stderr)
        return 3

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

    env = dict(os.environ, PYTHONPATH=site + os.pathsep + os.environ.get("PYTHONPATH", ""))
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "speech.wav")
        r = subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", wav, "--", text],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0 or not os.path.isfile(wav):
            print(f"speak: synthesis failed: {r.stderr.strip()[-300:]}", file=sys.stderr)
            return 4
        # Opus in Ogg at 48 kHz mono: plays everywhere and is the format Discord voice messages use.
        # Encoded with PyAV's bundled codecs so no system ffmpeg is needed (the agent image has none).
        try:
            seconds = to_opus_ogg(wav, out)
        except Exception as e:
            print(f"speak: audio conversion failed: {e}", file=sys.stderr)
            return 4
    duration = round(seconds, 1)
    print(json.dumps({"path": out, "duration_secs": duration, "voice": voice, "chars": len(text), "truncated": truncated}))
    if truncated:
        print("speak: text was cut to ~%d characters; send the full text as a normal message." % MAX_CHARS, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
