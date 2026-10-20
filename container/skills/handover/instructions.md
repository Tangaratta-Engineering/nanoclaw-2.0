# Getting context from your sibling agent (handover)

This applies to Tiff and Timmy: the "other agent" is the one that is not you. **Never tell George to repeat himself when the other agent probably already has the context.** If George says things like "Tiff is struggling with this", "Tiff was working on…", "continue what Timmy was doing", "I asked Tiff earlier", "as I said before", or refers to something you cannot see, then:

1. Check your own memory notes first. If that is not enough:
2. Tell George in ONE line (in the chat he used) that you are getting the context from the other agent.
3. Send a **CONTEXT REQUEST** with `<message to="<other agent>">…</message>` (use exactly this shape):
   ```
   CONTEXT REQUEST from <you> → <other>
   Asked by: George, via: <channel | dm>
   Request (verbatim): "<George's exact words>"
   I need: <what you need — what he originally asked, what was tried, results and exact errors, ids/links/files, his preferences>
   Return: reply to me once with a HANDOVER. Do not message George.
   ```
   (`via` is `channel` when his message arrived with `from="general"`, `dm` when it arrived with `from="george"`.) Then stop — do not guess.

**If you receive a CONTEXT REQUEST:** run `/app/skills/handover/scripts/recent-context` (add `--grep <keywords>` for the topic, `--hours 72` if it is older), read your memory notes, and reply ONCE to the requester — never to George — with:
```
HANDOVER from <you> → <other>
Echo: George via <channel | dm> asked: "<verbatim>"
What George originally wanted: …
Done so far: …
What went wrong or is blocked (exact error text): …
State: ids, file paths, links, drafts, anything created or sent
His preferences and constraints: …
Open questions: …
Suggested next step: …
```
Facts only, under about 300 words. Say "I don't have this" for gaps — never guess. **Take dates and times only from the tool's `--- Mon 19 Oct ---` day headers and `[hh:mm]` stamps (Sydney time) — never infer the day, and always include the date.**

**When the HANDOVER arrives:** carry on with the work yourself and deliver the result where George asked — `via: channel` → post to `general-main` starting with "Re: <his request in ≤10 words>"; `via: dm` → send it to him via `george`. If something you truly need is still missing, ask George ONE specific question — never "can you repeat everything".

**Limits:** a CONTEXT REQUEST is never answered with another CONTEXT REQUEST. One request, one reply. Do not mirror either message to the channel, and do not thank or acknowledge.
