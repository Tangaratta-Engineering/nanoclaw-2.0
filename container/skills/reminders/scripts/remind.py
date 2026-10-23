#!/usr/bin/env python3
"""Add a reminder to George's iPhone Reminders app. See SKILL.md.

How: send one small JSON email to a mailbox on the phone; an iOS Shortcuts automation ("When I get an email")
creates the reminder. Calls the Gmail API with curl (the OneCLI gateway injects the OAuth token).
The recipient is fixed in config.json; this tool cannot send anywhere else.
"""
import argparse
import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from email.message import EmailMessage
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("REMIND_TZ", "Australia/Sydney"))
DATA = os.environ.get("REMIND_DATA", "/workspace/projects/.nanoclaw-data/reminders")
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_PER_DAY = 40
SUBJECT_TAG = "[NC-REMINDER]"


class RemindError(Exception):
    pass


def gmail(method, path, body=None, runner=subprocess.run):
    cmd = ["curl", "-sS", "--max-time", "60", "-X", method, GMAIL + path, "-H", "Content-Type: application/json", "-w", "\n%{http_code}"]
    if body is not None:
        cmd += ["--data-binary", "@-"]
    p = runner(cmd, input=json.dumps(body) if body is not None else None, capture_output=True, text=True)
    if p.returncode != 0:
        raise RemindError(f"network error: {p.stderr.strip() or p.returncode}")
    text, _, code = p.stdout.rpartition("\n")
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        raise RemindError(f"HTTP {code}: unreadable response")
    if not code.startswith("2"):
        msg = data.get("error", {}).get("message", text[:200])
        hint = " (the Gmail connection may lack send access: ask George to re-authorise Gmail with sending enabled)" if code in ("401", "403") else ""
        raise RemindError(f"HTTP {code}: {msg}{hint}")
    return data


def parse_due(text, ref=None):
    """ISO date/time, 'in 2h' / 'in 30m', 'tomorrow 9am', 'today 5pm'. Past times are refused."""
    ref = ref or dt.datetime.now(TZ)
    s = text.strip().lower()
    m = re.fullmatch(r"in\s+(\d+(?:\.\d+)?)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?)", s)
    if m:
        n, u = float(m.group(1)), m.group(2)[0]
        due = ref + dt.timedelta(minutes=n * {"m": 1, "h": 60, "d": 1440}[u])
    else:
        m = re.fullmatch(r"(today|tomorrow)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
        if m:
            h, mi, ap = int(m.group(2)), int(m.group(3) or 0), m.group(4)
            if ap == "pm" and h < 12:
                h += 12
            if ap == "am" and h == 12:
                h = 0
            if not (0 <= h < 24 and 0 <= mi < 60):
                raise RemindError(f"bad time '{text}'")
            due = ref.replace(hour=h, minute=mi, second=0, microsecond=0) + dt.timedelta(days=1 if m.group(1) == "tomorrow" else 0)
        else:
            try:
                due = dt.datetime.fromisoformat(text.strip().replace(" ", "T"))
            except ValueError:
                raise RemindError(f"cannot read the time '{text}': use 2026-10-24T09:00, 'in 2h', 'tomorrow 9am' or 'today 5pm'")
            if due.tzinfo is None:
                due = due.replace(tzinfo=TZ)
            if len(text.strip()) == 10:  # date only: 9am that day
                due = due.replace(hour=9)
    if due < ref - dt.timedelta(minutes=1):
        raise RemindError(f"{due:%a %d %b %H:%M} is in the past")
    return due.replace(second=0, microsecond=0)


def config():
    try:
        with open(os.path.join(DATA, "config.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def state_path():
    return os.path.join(DATA, "sent.json")


def check_rate():
    today = time.strftime("%Y-%m-%d")
    try:
        with open(state_path()) as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    if st.get(today, 0) >= MAX_PER_DAY:
        raise RemindError(f"daily limit of {MAX_PER_DAY} reminders reached")
    return today, st


def build_message(to, title, due, notes, sender=None, test=False):
    payload = {"title": title, "due": due.isoformat(timespec="minutes")}
    if notes:
        payload["notes"] = notes
    m = EmailMessage()
    m["To"] = to
    if sender:
        m["From"] = sender
    m["Subject"] = f"{SUBJECT_TAG}{' TEST' if test else ''} {title}"[:200]
    m.set_content(json.dumps(payload, ensure_ascii=False))
    return m, payload


def send(m, runner=subprocess.run):
    raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
    return gmail("POST", "/messages/send", {"raw": raw}, runner)


def cmd_add(a, runner=subprocess.run):
    cfg = config()
    to = cfg.get("to")
    if not to:
        raise RemindError("phone reminders are not set up yet (no recipient in config.json): use a Discord reminder instead and tell George to finish the Reminders setup")
    title = a.title.strip()
    if not title:
        raise RemindError("a reminder needs a title")
    due = parse_due(a.due)
    today, st = check_rate()
    m, payload = build_message(to, title, due, a.notes)
    send(m, runner)
    st[today] = st.get(today, 0) + 1
    os.makedirs(DATA, exist_ok=True)
    with open(state_path(), "w") as f:
        json.dump(st, f)
    return f"Reminder sent to the phone: {title}, due {due:%a %d %b %H:%M}. It appears in Reminders as soon as the iPhone receives the email."


def cmd_selftest(a, runner=subprocess.run):
    """Send a test reminder to George's own Gmail address (not the phone) to prove sending works."""
    me = gmail("GET", "/profile", None, runner)["emailAddress"]
    m, _ = build_message(me, "Test reminder from NanoClaw", dt.datetime.now(TZ) + dt.timedelta(hours=1), "Safe to delete.", test=True)
    send(m, runner)
    return "Test email sent to your own Gmail address (check the inbox). Sending works."


def main(argv=None, runner=subprocess.run):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--title", required=True)
    s.add_argument("--due", required=True, help="2026-10-24T09:00, 'in 2h', 'tomorrow 9am', 'today 5pm' (Sydney time); ask George if he did not say when")
    s.add_argument("--notes")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    try:
        print({"add": cmd_add, "selftest": cmd_selftest}[a.cmd](a, runner))
        return 0
    except RemindError as e:
        print(f"remind: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
