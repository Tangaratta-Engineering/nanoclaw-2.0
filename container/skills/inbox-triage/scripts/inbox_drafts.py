#!/usr/bin/env python3
"""Reply drafts with an approval gate: create -> card (shown to George) -> send exactly what was shown.

Safety rules enforced here, not just in prose:
- replies only, on an existing thread, to people already on that thread, plain text, no attachments;
- a draft can be sent only if its current text is exactly what `card` last displayed;
- at most MAX_SENDS_PER_DAY sends per day.
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import time
from email.message import EmailMessage
from email.utils import getaddresses

sys.path.insert(0, os.path.dirname(__file__))
import inbox_gmail as g  # noqa: E402

DATA = os.environ.get("INBOX_DATA", "/workspace/projects/.nanoclaw-data/inbox-triage")
MAX_SENDS_PER_DAY = 10


def state_path():
    return os.path.join(DATA, "drafts.json")


def load():
    try:
        with open(state_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"drafts": {}, "sends": {}}


def save(st):
    os.makedirs(DATA, exist_ok=True)
    with open(state_path(), "w") as f:
        json.dump(st, f, indent=1)


def digest(to, subject, body):
    return hashlib.sha256(json.dumps([sorted(to), subject, body.strip()]).encode()).hexdigest()


def addrs(value):
    return [a.lower() for _, a in getaddresses([value]) if a]


def thread_info(call, thread_id):
    me = call("GET", "/profile")["emailAddress"].lower()
    t = call("GET", f"/threads/{thread_id}?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Cc&metadataHeaders=Reply-To&metadataHeaders=Subject&metadataHeaders=Message-ID&metadataHeaders=References")
    people, last_in = set(), None
    for m in t.get("messages", []):
        for h in ("From", "To", "Cc"):
            people.update(addrs(g.header(m, h)))
        if me not in addrs(g.header(m, "From")):
            last_in = m
    people.discard(me)
    if not last_in:
        raise g.GmailError("no incoming message in that thread to reply to")
    return me, people, last_in


def build_raw(to, subject, body, msg_id, refs):
    m = EmailMessage()
    m["To"] = ", ".join(to)
    m["Subject"] = subject
    if msg_id:
        m["In-Reply-To"] = msg_id
        m["References"] = (refs + " " + msg_id).strip()
    m.set_content(body)
    return base64.urlsafe_b64encode(m.as_bytes()).decode()


def current(call, draft_id):
    d = call("GET", f"/drafts/{draft_id}?format=full")
    m = d["message"]
    to = addrs(g.header(m, "To"))
    return to, g.header(m, "Subject"), g.body_text(m, 20000), m


def cmd_create(a, call):
    body = open(a.body_file, encoding="utf-8").read().strip()
    if not body:
        raise g.GmailError("empty draft body")
    me, people, last_in = thread_info(call, a.thread)
    reply_to = addrs(g.header(last_in, "Reply-To")) or addrs(g.header(last_in, "From"))
    to = [x for x in (a.to or reply_to) if x != me]
    stranger = [x for x in (x.lower() for x in to) if x not in people]
    if not to or stranger:
        raise g.GmailError(f"recipients must already be on the thread; not on it: {', '.join(stranger) or '(none given)'}")
    subj = g.header(last_in, "Subject")
    subj = subj if subj.lower().startswith("re:") else f"Re: {subj}"
    raw = build_raw(to, subj, body, g.header(last_in, "Message-ID"), g.header(last_in, "References"))
    d = call("POST", "/drafts", {"message": {"raw": raw, "threadId": a.thread}})
    st = load()
    st["drafts"][d["id"]] = {"thread": a.thread, "created": int(time.time()), "shown": None, "sent": False}
    save(st)
    return f"draft {d['id']} created for {', '.join(to)} (not shown, not sent)"


def cmd_card(a, call):
    st = load()
    rec = st["drafts"].get(a.draft)
    if not rec:
        raise g.GmailError("unknown draft: create it with this tool first")
    to, subj, body, _ = current(call, a.draft)
    rec["shown"] = digest(to, subj, body)
    save(st)
    return f"To: {', '.join(to)}\nSubject: {subj}\n\n{body}"


def cmd_edit(a, call):
    st = load()
    rec = st["drafts"].get(a.draft)
    if not rec or rec["sent"]:
        raise g.GmailError("unknown or already-sent draft")
    body = open(a.body_file, encoding="utf-8").read().strip()
    to, subj, _, m = current(call, a.draft)
    raw = build_raw(to, subj, body, g.header(m, "In-Reply-To"), g.header(m, "References"))
    call("PUT", f"/drafts/{a.draft}", {"message": {"raw": raw, "threadId": rec["thread"]}})
    rec["shown"] = None  # must be shown again before it can be sent
    save(st)
    return "draft updated; show the card again before sending"


def cmd_send(a, call):
    st = load()
    rec = st["drafts"].get(a.draft)
    if not rec or rec["sent"]:
        raise g.GmailError("unknown or already-sent draft")
    if not rec["shown"]:
        raise g.GmailError("this draft has not been shown to George: run `card` and get his [Send] first")
    to, subj, body, _ = current(call, a.draft)
    if digest(to, subj, body) != rec["shown"]:
        raise g.GmailError("the draft changed since George saw it: show the card again")
    today = time.strftime("%Y-%m-%d")
    if st["sends"].get(today, 0) >= MAX_SENDS_PER_DAY:
        raise g.GmailError(f"daily send limit ({MAX_SENDS_PER_DAY}) reached")
    r = call("POST", "/drafts/send", {"id": a.draft})
    rec["sent"] = True
    st["sends"][today] = st["sends"].get(today, 0) + 1
    save(st)
    return f"sent (message {r.get('id', '?')}) to {', '.join(to)}"


def main(argv=None, call=g.call):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("create"); s.add_argument("--thread", required=True); s.add_argument("--body-file", required=True); s.add_argument("--to", action="append")
    for n in ("card", "send"):
        s = sub.add_parser(n); s.add_argument("draft")
    s = sub.add_parser("edit"); s.add_argument("draft"); s.add_argument("--body-file", required=True)
    a = ap.parse_args(argv)
    try:
        print({"create": cmd_create, "card": cmd_card, "edit": cmd_edit, "send": cmd_send}[a.cmd](a, call))
        return 0
    except g.GmailError as e:
        print(f"inbox-draft: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
