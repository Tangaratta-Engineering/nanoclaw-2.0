---
name: speak
description: Reply with a spoken voice message (Google Chirp 3 HD voices, falling back to a local offline voice) instead of only text. Use when George sent a voice note, or asks for a voice reply, so you can talk back to him.
allowed-tools: Bash(/app/skills/speak/scripts/speak:*)
---

# Speak (text-to-speech)

```bash
/app/skills/speak/scripts/speak "Good morning George. Your flights to Brisbane are one thousand seven hundred dollars, cheapest out of Sydney."
# -> {"path": "/workspace/agent/voice-replies/reply-….ogg", "duration_secs": 9.4, "voice": "en-US-Chirp3-HD-Aoede", "provider": "google", "fallback_used": false, "chars": 118, "truncated": false}
```

Then attach it: `send_file` with that `path` (`to` is required: use the destination of the chat you are replying in).

## How it works

- **Google Chirp 3 HD** is each agent's voice (**Tiff** = Aoede, **Jimmy** = Charon, **Jack** = Fenrir, all `en-US`), chosen by assistant name in `voices.json`. The request goes to Google's Text-to-Speech REST API through the OneCLI gateway, which adds the API key: no key is in this skill, the image or your environment. Google returns Ogg Opus directly.
- **Automatic fallback to Piper** (a local offline voice on this server's CPU: `en_US-hfc_female-medium` for Tiff, `en_US-ryan-medium` for the others). Any Google problem triggers it: no network, a timeout (8 s), an HTTP error, an invalid key, an exhausted quota, or the **monthly character limit** (900,000 of Google's 1,000,000 free characters, counted across all agents in `/workspace/projects/.nanoclaw-data/voice/google-usage.json`). The reason is printed to stderr, the exit code is still 0, and the JSON says `"provider": "piper", "fallback_used": true`. Piper starts in about 4 s and runs at roughly 4× real time.
- `voices.json` entries: a plain string is a Piper voice id; an object `{"provider": "google", "voice": "<name>", "fallback": "<piper id>"}` is a Google voice with its Piper fallback.
- Override per call with `--voice google:<name>` (e.g. `google:en-GB-Chirp3-HD-Zephyr`) or `--voice piper:<id>` (a bare id means Piper).
- The output is **Opus in an Ogg file**: the format Discord uses for voice messages, plays on every phone. Piper output is encoded with PyAV's bundled codecs, so no `ffmpeg` is needed (the agent images have none).
- The text is cleaned for speech first: markdown, emoji, code blocks and links are removed (links are never read aloud; `$1,789` becomes "1,789 dollars"). Replies are capped at about 1,200 characters (~85 s); longer text is cut at a sentence end and the tool warns you — put the rest in a normal text message.
- Reply text sent to Google is not kept by this skill, but it does leave the machine. Don't speak anything George wouldn't want a cloud service to process.

## Writing for the ear

Short sentences. Say the answer first. Round numbers ("about seventeen hundred dollars") unless exactness matters, and give exact figures in the text message. Avoid lists, abbreviations and anything that only makes sense visually.

## Options

| Flag | Use |
|------|-----|
| `--voice <id>` | `google:<name>`, `piper:<id>`, or a bare Piper id |
| `--out <file.ogg>` | Choose the output path (default `/workspace/agent/voice-replies/`) |
| `-` as the text | Read the text from stdin |

Exit codes: `0` ok (also when it fell back to Piper) · `2` nothing speakable · `3` Piper not installed and Google unavailable · `4` synthesis/conversion failed.

## Setup / troubleshooting (host)

One-time, run by George on the host: `container/skills/speak/setup.sh`. It installs pinned `piper-tts` and downloads the Piper voices listed in `voices.json` (including each Google voice's fallback) to `~/projects/.nanoclaw-tools/piper/` (about 60 MB per voice), which agents see at `/workspace/projects/.nanoclaw-tools/piper/`. No repo or image change, so no rebuild. To change a voice, edit `voices.json` and run `setup.sh` again. Voices are listed at https://huggingface.co/rhasspy/piper-voices (id format `en_GB-alan-medium`).
