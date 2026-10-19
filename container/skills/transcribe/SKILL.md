---
name: transcribe
description: Turn voice messages and audio/video files into text (speech-to-text) with a reliability rating, in any language Whisper supports. Use whenever a message has an audio or voice attachment, or someone asks what a recording says or to translate it.
allowed-tools: Bash(/app/skills/transcribe/scripts/transcribe:*)
---

# Transcribe voice and audio

```bash
/app/skills/transcribe/scripts/transcribe /workspace/inbox/<id>/voice-message.ogg
```

Prints one header line, any warnings, then the transcript:

```
[engine=groq whisper-large-v3 · language=English · audio=17.8s · took=0.4s · reliability=good]
Do you have access to my email? ...
```

## Engines (automatic)

1. **Groq Whisper** (default): `whisper-large-v3`, about 0.3–1 s for a typical voice note. The API key lives in the OneCLI vault and is injected by the gateway — never ask for it. Audio is sent to Groq; for anything George marks private use `--engine local`.
2. **Cross-check**: every cloud result is compared with `whisper-large-v3-turbo` (run without the name hints). If the two disagree, the result is rated `uncertain` and the alternative is printed. One model's own confidence cannot catch a confident-but-wrong transcript; disagreement can.
3. **Local fallback**: if Groq is unreachable, rate-limited or errors, the local faster-whisper `small` model runs offline (about 1.6× the audio length on this server) and a `note:` says so.

## Reliability

`good` / `uncertain` / `poor`, with the reasons printed as `reliability warnings:` — models disagree, very little text for the audio length (speech may have been missed), a repeated sentence (hallucination), low model confidence. Act on it: see the always-on instructions — do not take consequential actions from an `uncertain` or `poor` transcript without George confirming the key words. If the audio itself is poor (mumbled, quiet, noisy), say so and ask for a re-send rather than guessing.

## Options

| Flag | Use |
|------|-----|
| `--engine auto\|cloud\|local` | Default `auto`. `local` keeps audio on this machine; `cloud` fails instead of falling back |
| `--language xx` | Force the spoken language (ISO code) when auto-detect is wrong or the clip is very short |
| `--translate` | Speech→English translation (English only) |
| `--timestamps` | Prefix each segment with `[mm:ss]` |
| `--json` | Machine-readable: engine, language, duration, text, segments, quality, issues, agreement, alternative |
| `--model tiny\|base\|small\|medium` | Local model only (default `small`; `medium` is more accurate but about 4–7× the audio length) |

Names the family uses (Tiff, Timmy, George, Emily, Henry, Sophie, Turramurra…) are passed to the primary model as a hint — edit `vocabulary.txt` to change them.

## Workflow

1. Find the path in the message (`saved to /workspace/inbox/...`). Discord voice messages are `.ogg` (Opus); anything ffmpeg can decode works, including video.
2. Run `transcribe`. Cloud takes about a second; the local fallback can take minutes for long audio, so for recordings longer than ~3 minutes on the local engine raise your Bash timeout (up to 10 minutes).
3. Reply to the **content**. Mention it was a voice message; quote the transcript only if it is short, the user asked for it, or it is uncertain.
4. **Translating to a language other than English:** transcribe in the original language, then translate the text yourself, naming both languages.
5. If the result is empty or garbled, say so and offer a re-send. Never invent words.

## Handoffs

Files do not travel with a handoff to the other agent. Transcribe first and put the transcript (and its reliability) in the handoff's Context.

## Setup / troubleshooting (host)

- **Groq key** (one-time): add it to the OneCLI vault as a generic secret — host `api.groq.com`, header `Authorization`, format `Bearer {value}`. Test: `onecli run --agent <agent-id> -- curl -s https://api.groq.com/openai/v1/models` should return `200` with a model list.
- **Local fallback** (one-time): `container/skills/transcribe/setup.sh [model ...]` (default `small`; add `medium` for offline accuracy). It installs pinned packages and downloads models to `~/projects/.nanoclaw-tools/whisper/`, which agents see at `/workspace/projects/.nanoclaw-tools/whisper/`. No repo or image change, so no rebuild.

Exit codes: `0` ok · `2` file not found · `3` no engine available · `4` `--engine cloud` failed.
