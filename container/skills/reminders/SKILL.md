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

The reminder email is sent from George's Gmail address **to the same address** (`config.json`: `{"to": "george.cains@gmail.com"}`), so the iPhone Mail app must have that Gmail account added (Settings → Apps → Mail → Mail Accounts). Gmail reaches Mail by fetch, so a reminder can take up to ~15 minutes to appear; that is fine for reminders set in advance, not for "in 5 minutes". The inbox triage ignores these emails.

1. Shortcuts app → **Automation** tab → **+** → **Email**.
2. **Sender**: choose George's own address (george.cains@gmail.com). **Subject Contains**: `[NC-REMINDER]`. **Account**: the Gmail account. Select **Run Immediately** (not "Run After Confirmation") → **Next** → **New Blank Automation**.
3. Add these actions, in this order (search for each by name):
   1. **Get Text from Input** — Input: *Shortcut Input* (the email).
   2. **Get Dictionary from Input** — Input: *Text* (the result of step 1).
   3. **Get Dictionary Value** — Key `title`. (Tap the result and rename it "Title".)
   4. **Get Dictionary Value** — Key `due`, Dictionary: *Dictionary* from step 2. Rename "Due".
   5. **Get Dates from Input** — Input: *Due* → rename "DueDate".
   6. **Get Dictionary Value** — Key `notes`, Dictionary: *Dictionary* from step 2. Rename "Notes" (it can be empty).
   7. **Add New Reminder** — Title: *Title*; tap the arrow to show more: List: Reminders; Notes: *Notes*; **Date/Alert: DueDate**.
4. **Done**. Then ask NanoClaw for a test reminder.

If the email body does not come through in step 1, the fallback is to read the **Subject** and **Body** with *Get Details of Email* instead.

Tests: `python3 container/skills/reminders/scripts/test_remind.py`.
