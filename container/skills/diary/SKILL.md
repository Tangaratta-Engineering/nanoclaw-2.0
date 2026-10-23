---
name: diary
description: Keep a pain and medication diary with timestamps, and check medication limits (rolling 24 h totals, minimum intervals, next allowed time). Use whenever someone logs pain, symptoms or a dose, or asks what they can take and when.
allowed-tools: Bash(/app/skills/diary/scripts/diary:*)
---

# Pain and medication diary

All time and dose arithmetic is done by this tool, not by you. Quote its output; never compute totals or "next allowed" times yourself.

```bash
D=/app/skills/diary/scripts/diary
$D now                                          # the real current date and time (Sydney)
$D log --at "2 hours ago" --severity 6 --location "base of skull" --character dull --helped "heat" --red-flags none
$D dose --drug meloxicam --at "just then"       # records the dose, then prints BREACH/WARNING lines first, rolling 24 h totals, next allowed times
$D dose --drug paracetamol --units 2 --at 11am
$D check --drug meloxicam                       # can I take one now? nothing is recorded
$D status                                       # 24 h totals and the next allowed time for every drug
$D amend <id> --at "yesterday 10pm" --reason "he corrected the time"      # or --void; the original stays in the file
$D render --days 7                              # the diary as markdown, newest day last (or --date 2026-10-23)
$D export --start 2026-10-16 --end 2026-10-23   # clinician summary figures
```

If a message has an arrival time, pass it as `--ref <ISO time>` before the sub-command so "just then" and "an hour ago" mean relative to when it was sent: `$D --ref 2026-10-23T14:02:00+11:00 dose --drug meloxicam --at "just then"`.

## Times

`--at` accepts: `just then`, `now`, `30 minutes ago`, `about 2 hours ago`, `half an hour ago`, `11am`, `~2:30pm`, `14:05`, `yesterday 10pm`, `last night 11pm`, or an ISO time. A clock time later than now is taken as yesterday and the tool says so. Anything vaguer ("earlier", "this morning sometime") is refused: ask for a clock time or how long ago. Never guess a time for a dose.

## Medication rules

Limits live in `meds.json` in the data directory (see `meds.example.json`). The tool enforces per-dose maximums, minimum intervals between doses, rolling 24 h caps (combination products count toward their ingredient), same-day conflicts between NSAIDs, unit caps and stopped drugs. A dose is always recorded as reported — the diary records what was said — and breaches are reported in the first lines. Unknown drug or missing strength: ask, do not assume. Do not loosen a limit in `meds.json` yourself; change it only when the person reports a new prescription from their clinician, and say you changed it.

A dose logged twice by mistake shows up as an interval breach: ask whether it was one dose, and if so `amend ... --void` the duplicate.

## Data

`/workspace/agent/diary/entries.jsonl` is append-only (one JSON record per line); amendments are new records. It is personal health data: keep it out of git and out of messages to anyone but the person it belongs to. Back it up with the rest of `groups/`.

Tests: `python3 container/skills/diary/scripts/test_diary.py`.
