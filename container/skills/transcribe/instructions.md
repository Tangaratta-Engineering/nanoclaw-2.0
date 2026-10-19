# Voice messages and audio

When a message carries an audio or voice attachment (it shows up like `[audio: voice-message.ogg — saved to /workspace/inbox/<id>/voice-message.ogg]`, or the file is an mp3/m4a/wav/ogg/webm/mp4), do not say you cannot hear it: transcribe it first, then answer the content as if George had typed it.

```bash
/app/skills/transcribe/scripts/transcribe /workspace/inbox/<id>/<file>
```

The first line reports the engine and a **reliability** rating: `good`, `uncertain` or `poor`.
- `good`: answer normally and say you transcribed a voice message.
- `uncertain` / `poor`: say so plainly. Give your best reading, quote the doubtful part (and the tool's alternative if it printed one), and ask George to confirm the key words **before acting** on anything that involves money, dates, deleting or sending something. Never present a shaky transcript as fact, and never fill gaps with guesses.
- The `language=` field is the detected spoken language, not how accurate the transcript is. Never describe it as "confidence".

To translate speech into another language, transcribe it and translate the text yourself. Run `/transcribe` (the skill) for options and troubleshooting. If the tool says no engine is available, tell George to run `container/skills/transcribe/setup.sh` on the host.

Attachments are not forwarded when you hand a request to the other agent: transcribe first and put the transcript in the handoff.
