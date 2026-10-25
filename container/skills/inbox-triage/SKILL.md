---
name: inbox-triage
description: Daily email triage for George. Gathers the inbox into a trimmed dataset (inbox-fetch), and creates, shows and — only after his approval — sends reply drafts (inbox-draft). Use for the scheduled inbox runs and when George asks about emails, invoices or replies.
allowed-tools: Bash(/app/skills/inbox-triage/scripts/inbox-fetch:*), Bash(/app/skills/inbox-triage/scripts/inbox-draft:*), Bash(/app/skills/inbox-triage/scripts/inbox-calendar:*), Bash(/app/skills/inbox-triage/scripts/inbox-mail:*)
---

# Inbox triage

Three roles share this skill: **Tiff** runs `inbox-fetch` on schedule (daily, 8am) and talks to George; the **Clerk** (Opus worker agent) reads the dataset and decides what needs action; **drafts** are only ever sent after George presses Send. The pipeline is in the always-on `instructions.md`; the Clerk's decision rules are in `triage-rubric.md`.

## `inbox-fetch` (the scheduled-task script)

```bash
/app/skills/inbox-triage/scripts/inbox-fetch            # since the last run
/app/skills/inbox-triage/scripts/inbox-fetch --days 7 --dry-run   # look back without moving the marker
```

Prints one JSON line `{"wakeAgent": bool, "data": {"dataset": "<path>", "counts": {...}}}`. The dataset (`emails.json`) holds only mail that could need action; everything dropped is listed with a reason in `skipped.json` next to it. Files live under `/workspace/projects/.nanoclaw-data/inbox-triage/<date_time>/` (outside git). Filters: Gmail promotion/social/forum categories, bulk and automated senders and George's `gmail-hourly/rules.json` ignore lists — but anything with invoice/payment words, an attachment, or action words in the subject (due soon, renewal, action required…) is always kept. PDF attachments are read to text when `setup.sh` has been run.

## `inbox-mail` (any agent: find and read an email properly)

```bash
M=/app/skills/inbox-triage/scripts/inbox-mail
$M search "505157"                     # whole mailbox (inbox, archive, sent); id | date | from | subject | attachments
$M search "from:nrma stay" --limit 40  # Gmail search syntax; add --spam to include spam and trash
$M read <message id> --pdf             # full text of the email, plus the text of any PDF attachment
```

Why it exists: some systems (booking engines, receipts) send a plain-text part that is only a placeholder such as "No Content", with the real details in the HTML part and/or a PDF. `read` shows the HTML text when the plain part is a placeholder, and `--pdf` reads attachments. "The email has no body" is a conclusion to reach only after `read --pdf` shows nothing.

## `inbox-draft`

```bash
D=/app/skills/inbox-triage/scripts/inbox-draft
$D create --thread <thread id> --body-file reply.txt     # saves a Gmail draft; nothing is sent
$D card <draft id>                                       # prints To / Subject / full text to show George
$D edit <draft id> --body-file new.txt                   # revise; the card must be shown again
$D send <draft id>                                       # only after George pressed Send on that card
```

Enforced in code: replies only, to people already on the thread, plain text; `send` fails unless the draft's current text is exactly what `card` last printed; at most 10 sends a day.

## `inbox-calendar`

```bash
C=/app/skills/inbox-triage/scripts/inbox-calendar
$C agenda [--offset 1] [--json]     # today's (or tomorrow's) calendar: APPOINTMENTS first, routine events on one line
$C week [--start 2026-11-02] [--days 7] [--json]   # the whole week: appointments per day, clashes, possible duplicates, all-day events, regular routine on one line
$C learn --title "Henry medication" --as routine        # or --as appointment; remembered for good
$C add --title "Physio" --start 2026-10-23T08:30 --end 2026-10-23T09:30 --location "..." --source-link <gmail link> --key <thread id>
```

`agenda` reads George's primary and Family calendars (change them in `calendar-rules.json` next to the datasets). It decides what is a real appointment and what is a standing routine event: your explicit rules win; otherwise anything with appointment words (Dr, dentist, physio, meeting…), a location or other people is an appointment, and repeating events without those (and titles seen five or more times in the last 30 days) are routine. `add` never creates a duplicate (same key, or a same-day event with a similar title) and refuses dates in the past; it can only add, never delete.

## `weekly-pack` (the Sunday-night briefing's scheduled-task script)

`scripts/weekly-pack` prints `{"wakeAgent": true, "data": {"calendar_week": …, "ledger_open_items": {"Open": …, "Awaiting approval": …}}}`: next week's calendar (Monday to Sunday) and the open items in the Notion Action ledger, trimmed to type, item, due date, amount and payee. Each part fails on its own, so a Notion or Calendar error is reported in the data instead of cancelling the briefing.

## Setup (host, once)

`NANOCLAW_AGENT_IMAGE=<agent image> container/skills/inbox-triage/setup.sh` installs pinned `pypdf` into `~/projects/.nanoclaw-tools/pdf`. Needs Gmail read and compose access through OneCLI (already connected).
