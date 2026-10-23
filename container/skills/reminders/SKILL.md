---
name: reminders
description: Put a reminder into George's iPhone Reminders app, with a due time. Use whenever he says "remind me", "add a reminder", "don't let me forget", or a task has a deadline he should be alerted about.
allowed-tools: Bash(/app/skills/reminders/scripts/remind:*)
---

# Phone reminders (iPhone Reminders app)

```bash
R=/app/skills/reminders/scripts/remind
$R add --title "Pick up Sophie's piano book" --due "tomorrow 9am"
$R add --title "Pay the Music4Kids invoice" --due 2026-11-02T09:00 --notes "Invoice 2026222, ANZ transfer"
$R selftest        # sends a test email to George's own Gmail address to prove sending works
```

`--due` is required: `2026-10-24T09:00`, a date alone (= 9am), `in 2h`, `in 30m`, `tomorrow 9am` or `today 5pm`, all Sydney time. Times in the past are refused. If he did not say when, ask; do not guess a time. One reminder per call; the daily limit is 40.

## How it works

The tool emails one small JSON message (`{"title", "due", "notes"}`, subject starting `[NC-REMINDER]`) to a mailbox on George's iPhone. An iOS Shortcuts automation ("When I get an email") turns it into a reminder in the Reminders app, which then alerts him natively at the due time. The recipient is fixed in `config.json` (`{"to": "<address on the phone>"}` in the data directory, outside git); the tool cannot send anywhere else. Success means the email was sent; the phone creates the reminder when it receives it (seconds with iCloud Mail push, up to ~15 minutes with Gmail fetch).

If the tool says phone reminders are not set up, fall back to a Discord reminder (`schedule_task`) and tell George to finish the setup below.

## Setup on the iPhone (once, about 10 minutes)

1. Use a mailbox that **pushes** to the phone: an iCloud Mail address (Settings → your name → iCloud → Mail on; an `@icloud.com` address). Put that address in `config.json` as `to`. (Gmail also works, but iOS only fetches it every ~15 minutes.)
2. Shortcuts app → **Automation** → **+** → **Email**. Sender: George's Gmail address. Subject contains: `[NC-REMINDER]`. Account: the mailbox above. Choose **Run Immediately** (turn off "Ask Before Running") and **Next**.
3. Build the shortcut, in this order:
   1. **Get Text from Input** (input: Shortcut Input) — the email body.
   2. **Get Dictionary from Input** (input: Text).
   3. **Get Dictionary Value**: key `title` → rename the result "Title".
   4. **Get Dictionary Value**: key `due` → rename "Due".
   5. **Get Dates from Input** (input: Due) → rename "DueDate".
   6. **Get Dictionary Value**: key `notes` → rename "Notes" (may be empty).
   7. **Add New Reminder**: Title = Title; tap the arrow to show more: List = Reminders, Notes = Notes, **Alert/Due = DueDate**.
4. Save, then test from NanoClaw: ask Tiff to "add a test reminder in 5 minutes". A reminder appears in the app, and the phone alerts at the due time.

Tests: `python3 container/skills/reminders/scripts/test_remind.py`.
