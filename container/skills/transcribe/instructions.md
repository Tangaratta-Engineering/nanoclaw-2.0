# Voice messages and audio

When a message carries an audio or voice attachment (it shows up like `[audio: voice-message.ogg — saved to /workspace/inbox/<id>/voice-message.ogg]`, or the file is an mp3/m4a/wav/ogg/webm/mp4), do not say you cannot hear it: transcribe it first with the local speech-to-text tool, then answer the content as if George had typed it.

```bash
/app/skills/transcribe/scripts/transcribe /workspace/inbox/<id>/<file>
```

State that you transcribed a voice message and the detected language, and say so if the audio was unclear or silent instead of guessing words. To translate speech into another language, transcribe it and translate the text yourself. Run `/transcribe` (the skill) for options, long audio and troubleshooting. If the tool says it is not installed, tell George to run `container/skills/transcribe/setup.sh` on the host.

Attachments are not forwarded when you hand a request to the other agent: transcribe first and put the transcript in the handoff.
