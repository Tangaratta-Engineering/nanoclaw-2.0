---
name: speak
description: Reply with a spoken voice message (local text-to-speech, free and offline) instead of only text. Use when George sent a voice note, or asks for a voice reply, so you can talk back to him.
allowed-tools: Bash(/app/skills/speak/scripts/speak:*)
---

# Speak (text-to-speech)

```bash
/app/skills/speak/scripts/speak "Good morning George. Your flights to Brisbane are one thousand seven hundred dollars, cheapest out of Sydney."
# -> {"path": "/workspace/agent/voice-replies/reply-….ogg", "duration_secs": 9.4, "voice": "en_US-hfc_female-medium", "chars": 118, "truncated": false}
```

Then attach it: `send_file` with that `path` (leave `to` out to reply in the same chat).

## How it works

- **Piper**, a local neural voice running on this server's CPU: free, offline, nothing leaves the machine. Startup is about 4 s and speech is generated at roughly 4× real time, so a 25 s reply takes about 7 s.
- Each agent has its own voice, chosen by its assistant name in `voices.json`: **Tiff** = `en_US-hfc_female-medium`, **Timmy** = `en_US-ryan-medium`. `--voice <id>` overrides it. Piper has no Australian English voices (only `en_GB` and `en_US`).
- The output is **Opus in an Ogg file** at 48 kHz mono — the format Discord uses for voice messages, and it plays on every phone. It is encoded with PyAV's bundled codecs, so it does not need `ffmpeg` (the agent images don't ship it).
- The text is cleaned for speech first: markdown, emoji, code blocks and links are removed (links are never read aloud; `$1,789` becomes "1,789 dollars"). Replies are capped at about 1,200 characters (~85 s); longer text is cut at a sentence end and the tool warns you — put the rest in a normal text message.

## Writing for the ear

Short sentences. Say the answer first. Round numbers ("about seventeen hundred dollars") unless exactness matters, and give exact figures in the text message. Avoid lists, abbreviations and anything that only makes sense visually.

## Options

| Flag | Use |
|------|-----|
| `--voice <id>` | Use a different installed voice |
| `--out <file.ogg>` | Choose the output path (default `/workspace/agent/voice-replies/`) |
| `-` as the text | Read the text from stdin |

Exit codes: `0` ok · `2` nothing speakable · `3` not installed · `4` synthesis/conversion failed.

## Setup / troubleshooting (host)

One-time, run by George on the host: `container/skills/speak/setup.sh`. It installs pinned `piper-tts` and downloads the voices listed in `voices.json` to `~/projects/.nanoclaw-tools/piper/` (about 60 MB per voice), which agents see at `/workspace/projects/.nanoclaw-tools/piper/`. No repo or image change, so no rebuild. To change a voice, edit `voices.json` and run `setup.sh` again. Voices are listed at https://huggingface.co/rhasspy/piper-voices (id format `en_GB-alan-medium`).
