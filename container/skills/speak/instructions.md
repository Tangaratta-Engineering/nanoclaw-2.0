# Replying by voice

When George sends you a **voice note** (an audio attachment) — or asks you to "say", "speak" or "reply by voice" — answer **in voice** as well as text. If he wrote in text, reply in text only, unless he asks for voice. If he says "voice off" or "text only", stop using voice until he says "voice on" (remember it in your memory notes).

1. **Write a short spoken version**: about 15–40 seconds (roughly 40–100 words), plain conversational sentences, no markdown, tables, links, emoji or code, and numbers said the way you would say them. Spoken replies are for the answer or the gist, not the full detail.
2. **Make the audio** (about 5–10 seconds):
   ```bash
   /app/skills/speak/scripts/speak "<the spoken text>"
   ```
   It prints JSON with a `path`.
3. **Send it** with `send_file`, giving that `path` and leaving `to` out so it goes to the same chat.
4. **Send anything that doesn't belong in speech as a normal text message**: links, lists, prices, booking details, the transcript if it was uncertain. Never read links or long numbers aloud.

Keep your own voice: Tiff warm and quick, Timmy dry and exact. If `speak` says it isn't installed, reply in text and tell George to run `container/skills/speak/setup.sh` on the host. Run `/speak` (the skill) for options.

**Never rely on an earlier failure.** Tools get fixed between conversations. If you remember `speak` failing before, run it again now; only say it doesn't work if it fails in this turn, and then quote the actual error text.
