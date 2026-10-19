---
name: transcribe
description: Turn voice messages and audio/video files into text (speech-to-text), locally and offline, in any language Whisper supports. Use whenever a message has an audio or voice attachment, or someone asks what a recording says or to translate it.
allowed-tools: Bash(/app/skills/transcribe/scripts/transcribe:*)
---

# Transcribe voice and audio

Local speech-to-text (faster-whisper, CPU, int8). Free, private — audio never leaves the machine. Default model `base`; use `--model small` when accuracy matters (e.g. accents, names, noisy audio).

## Quick start

```bash
/app/skills/transcribe/scripts/transcribe /workspace/inbox/<id>/voice-message.ogg
```

Prints a one-line summary (`[language=en (97%) · audio=11.0s · model=base · took=5.4s]`) and then the transcript.

## Options

| Flag | Use |
|------|-----|
| `--language xx` | Force the spoken language (ISO code) when auto-detect is wrong or the clip is very short |
| `--translate` | Whisper's built-in speech→English translation (English only; fast, rougher) |
| `--timestamps` | Prefix each segment with `[mm:ss]` — useful for long recordings or quoting |
| `--json` | Machine-readable: language, probability, duration, text, segments |
| `--model tiny\|base\|small\|medium` | Speed vs accuracy (default `base`). Only models downloaded by `setup.sh` work offline |

## Workflow

1. Find the file path in the message (`saved to /workspace/inbox/...`). Discord voice messages are `.ogg` (Opus); anything ffmpeg can decode works, including video.
2. Run `transcribe` on it. Measured on this server (4 cores, plus model load of a few seconds): `base` ≈ 0.5× the audio length (11 s clip → ~5 s); `small` ≈ 1.6× the audio length (11 s → ~18 s). Your Bash call times out after about 2 minutes by default, so for audio longer than ~3 minutes raise the Bash timeout (up to 10 minutes) or run it in the background and poll the output file; for very long recordings use `--model tiny`.
3. Reply to the **content**. Mention it was a voice message and the detected language; quote the transcript only if it is short or the user asked for it.
4. **Translating to a language other than English:** transcribe in the original language, then translate the text yourself — better than `--translate`. Name both languages.
5. If the result is empty or garbled, say so and offer to retry with `--language`, a larger model, or a re-sent clip. Never invent words.

## Handoffs

Files do not travel with a handoff to the other agent. Transcribe first and put the transcript in the handoff's Context.

## Setup / troubleshooting (host)

One-time, run by George on the host: `container/skills/transcribe/setup.sh [model ...]` (default: `base small`; add `medium` for accuracy, `tiny` for speed). It installs pinned packages and downloads the models to `~/projects/.nanoclaw-tools/whisper/` (about 0.9 GB total for `base` + `small`), which the agent containers see at `/workspace/projects/.nanoclaw-tools/whisper/`. Nothing in the repo or image changes, so no rebuild is needed. If `transcribe` reports "not installed" or "could not load model", that setup has not been run or the model is missing.

Exit codes: `0` ok · `2` file not found · `3` not installed / model missing.
