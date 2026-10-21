---
name: inbox-triage
description: Daily email triage for George. Gathers the inbox into a trimmed dataset (inbox-fetch), and creates, shows and — only after his approval — sends reply drafts (inbox-draft). Use for the scheduled inbox runs and when George asks about emails, invoices or replies.
allowed-tools: Bash(/app/skills/inbox-triage/scripts/inbox-fetch:*), Bash(/app/skills/inbox-triage/scripts/inbox-draft:*)
---

# Inbox triage

Three roles share this skill: **Tiff** runs `inbox-fetch` on schedule and talks to George; the **Clerk** (Opus worker agent) reads the dataset and decides what needs action; **drafts** are only ever sent after George presses Send. The pipeline is in the always-on `instructions.md`; the Clerk's decision rules are in `triage-rubric.md`.

## `inbox-fetch` (the scheduled-task script)

```bash
/app/skills/inbox-triage/scripts/inbox-fetch            # since the last run
/app/skills/inbox-triage/scripts/inbox-fetch --days 7 --dry-run   # look back without moving the marker
```

Prints one JSON line `{"wakeAgent": bool, "data": {"dataset": "<path>", "counts": {...}}}`. The dataset (`emails.json`) holds only mail that could need action; everything dropped is listed with a reason in `skipped.json` next to it. Files live under `/workspace/projects/.nanoclaw-data/inbox-triage/<date_time>/` (outside git). Filters: Gmail promotion/social/forum categories, bulk and automated senders and George's `gmail-hourly/rules.json` ignore lists — but anything with invoice/payment words, an attachment, or action words in the subject (due soon, renewal, action required…) is always kept. PDF attachments are read to text when `setup.sh` has been run.

## `inbox-draft`

```bash
D=/app/skills/inbox-triage/scripts/inbox-draft
$D create --thread <thread id> --body-file reply.txt     # saves a Gmail draft; nothing is sent
$D card <draft id>                                       # prints To / Subject / full text to show George
$D edit <draft id> --body-file new.txt                   # revise; the card must be shown again
$D send <draft id>                                       # only after George pressed Send on that card
```

Enforced in code: replies only, to people already on the thread, plain text; `send` fails unless the draft's current text is exactly what `card` last printed; at most 10 sends a day.

## Setup (host, once)

`NANOCLAW_AGENT_IMAGE=<agent image> container/skills/inbox-triage/setup.sh` installs pinned `pypdf` into `~/projects/.nanoclaw-tools/pdf`. Needs Gmail read and compose access through OneCLI (already connected).
