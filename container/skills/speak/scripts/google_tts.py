"""Google Cloud Text-to-Speech (Chirp 3 HD) backend for `speak`.

Calls the REST API with curl. The credential is NOT here: the OneCLI gateway injects the API key into requests
to texttospeech.googleapis.com, so nothing secret is in this file, the image, voices.json or the environment.
Every failure raises GoogleTtsError with a short reason; `speak` then falls back to the local Piper voice.
"""
import base64
import concurrent.futures
import fcntl
import json
import os
import re
import subprocess
import tempfile
import time
import wave

URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
TIMEOUT_SECS = int(os.environ.get("SPEAK_GOOGLE_TIMEOUT", "8"))
CHUNK_CHARS = int(os.environ.get("SPEAK_GOOGLE_CHUNK", "320"))  # Chirp 3 HD takes ~1 s per 100 characters, so long text is split
MAX_PARALLEL = 4
MONTHLY_LIMIT = int(os.environ.get("SPEAK_GOOGLE_MONTHLY_LIMIT", "900000"))  # stay under Google's 1,000,000 free characters
USAGE_FILE = os.environ.get("SPEAK_GOOGLE_USAGE", "/workspace/projects/.nanoclaw-data/voice/google-usage.json")


class GoogleTtsError(Exception):
    pass


def month_key(now=None):
    return time.strftime("%Y-%m", time.gmtime(now if now is not None else time.time()))


def _read_usage(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def used_this_month(path=None, now=None):
    return int(_read_usage(path or USAGE_FILE).get(month_key(now), 0))


def check_budget(chars, path=None, limit=None, now=None):
    """Raise before calling Google when this request would take the month past the character limit."""
    limit = MONTHLY_LIMIT if limit is None else limit
    used = used_this_month(path, now)
    if used + chars > limit:
        raise GoogleTtsError(f"monthly character limit reached ({used} of {limit} used)")


def record_usage(chars, path=None, now=None):
    """Add `chars` to this month's counter (locked, so two agents speaking at once don't lose updates)."""
    path = path or USAGE_FILE
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = _read_usage(path)
            key = month_key(now)
            data = {key: int(data.get(key, 0)) + chars}  # older months are dropped
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, path)
    except OSError:
        pass  # a counter that can't be written must never stop speech


def language_of(voice):
    """en-US-Chirp3-HD-Aoede -> en-US"""
    parts = voice.split("-")
    if len(parts) < 3:
        raise GoogleTtsError(f"unrecognised Google voice name '{voice}'")
    return f"{parts[0]}-{parts[1]}"


def split_for_google(text, target=None):
    """Split at sentence ends into chunks of about `target` characters (never mid-sentence unless one sentence is longer)."""
    target = target or CHUNK_CHARS
    sentences = re.findall(r"[^.!?]+[.!?]+\s*|[^.!?]+$", text) or [text]
    chunks, cur = [], ""
    for sent in sentences:
        while len(sent) > target * 1.5:  # a run-on sentence: cut at a space
            cut = sent.rfind(" ", 0, target)
            cut = cut if cut > target * 0.4 else target
            sent, rest = sent[:cut], sent[cut:]
            if cur:
                chunks.append(cur.strip()); cur = ""
            chunks.append(sent.strip())
            sent = rest.lstrip()
        if cur and len(cur) + len(sent) > target:
            chunks.append(cur.strip()); cur = ""
        cur += sent
    if cur.strip():
        chunks.append(cur.strip())
    return [c for c in chunks if c]


def _request(text, voice, encoding, runner):
    """One synthesize call; returns the raw audio bytes. Raises GoogleTtsError."""
    body = {
        "input": {"text": text},
        "voice": {"languageCode": language_of(voice), "name": voice},
        "audioConfig": {"audioEncoding": encoding},
    }
    cmd = ["curl", "-sS", "--max-time", str(TIMEOUT_SECS), "-X", "POST", URL,
           "-H", "Content-Type: application/json", "--data-binary", "@-", "-w", "\n%{http_code}"]
    try:
        p = runner(cmd, input=json.dumps(body), capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as e:
        raise GoogleTtsError(f"could not run curl: {e}")
    if p.returncode == 28:
        raise GoogleTtsError(f"timed out after {TIMEOUT_SECS}s")
    if p.returncode != 0:
        raise GoogleTtsError(f"network error: {(p.stderr or '').strip()[:160] or p.returncode}")
    payload, _, code = p.stdout.rpartition("\n")
    try:
        data = json.loads(payload) if payload.strip() else {}
    except ValueError:
        raise GoogleTtsError(f"HTTP {code}: unreadable response")
    if code != "200":
        err = data.get("error", {}) if isinstance(data, dict) else {}
        reason = err.get("status") or err.get("message") or "error"
        if code == "429" or reason == "RESOURCE_EXHAUSTED":
            raise GoogleTtsError(f"quota exceeded (HTTP {code})")
        raise GoogleTtsError(f"HTTP {code}: {str(reason)[:120]}")
    audio = data.get("audioContent") if isinstance(data, dict) else None
    if not audio:
        raise GoogleTtsError("empty audio in the response")
    try:
        return base64.b64decode(audio)
    except ValueError:
        raise GoogleTtsError("audio was not valid base64")


def _join_wavs(parts, out_wav):
    """Concatenate WAV byte strings (same format) into one file."""
    params, frames = None, []
    for raw in parts:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            tmp.write(raw); tmp.close()
            with wave.open(tmp.name, "rb") as w:
                if params is None:
                    params = w.getparams()
                elif (w.getnchannels(), w.getsampwidth(), w.getframerate()) != params[:3]:
                    raise GoogleTtsError("audio chunks had different formats")
                frames.append(w.readframes(w.getnframes()))
        except wave.Error as e:
            raise GoogleTtsError(f"bad audio chunk: {e}")
        finally:
            os.unlink(tmp.name)
    with wave.open(out_wav, "wb") as w:
        w.setparams(params)
        w.writeframes(b"".join(frames))


def synthesize(text, voice, out_path, runner=subprocess.run, encoder=None):
    """Write an Ogg Opus file for `text` in `voice`. Raises GoogleTtsError on any problem.

    Short text is one request that returns Ogg Opus directly. Long text is split into sentence chunks that are
    synthesised in parallel (each takes ~1 s per 100 characters), joined, and encoded with `encoder(wav, out)`
    (speak.py's Piper-shared Opus encoder, needs PyAV). Without an encoder, long text is one slower request.
    """
    chunks = split_for_google(text)
    if len(chunks) <= 1 or encoder is None:
        raw = _request(text, voice, "OGG_OPUS", runner)
        if not raw.startswith(b"OggS"):
            raise GoogleTtsError("audio was not an Ogg file")
        with open(out_path, "wb") as f:
            f.write(raw)
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(chunks))) as ex:
        parts = list(ex.map(lambda c: _request(c, voice, "LINEAR16", runner), chunks))  # order is preserved
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "joined.wav")
        _join_wavs(parts, wav)
        try:
            encoder(wav, out_path)
        except Exception as e:  # noqa: BLE001
            raise GoogleTtsError(f"could not encode the joined audio: {e}")
