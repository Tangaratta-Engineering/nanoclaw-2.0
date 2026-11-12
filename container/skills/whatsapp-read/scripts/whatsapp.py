#!/usr/bin/env python3
"""Read George's allow-listed WhatsApp group chats (read-only). See SKILL.md."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# 172.17.0.1 is its own host address so the OneCLI secret for this service is not mixed up with the others.
BASE = os.environ.get("WHATSAPP_READ_URL", "http://172.17.0.1:8772")
STATE = os.environ.get("WHATSAPP_READ_STATE", "/tmp/whatsapp-last-new.json")
TIMEOUT = 30


class ReadError(Exception):
    pass


def call(method, path, params=None, body=None, opener=urllib.request.urlopen):
    """The OneCLI gateway adds the API key on the way through; this script never holds it."""
    url = BASE + path + ("?" + urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")}) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
    try:
        with opener(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ReadError("the WhatsApp reader refused the request (no API key was added). Tell George the WhatsApp secret is missing or not assigned in OneCLI")
        raise ReadError(f"the WhatsApp reader answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ReadError(f"cannot reach the WhatsApp reader: {getattr(e, 'reason', e)}")


def fmt(m):
    return f'[{m["at"][:16].replace("T", " ")} UTC] {m["chat"]} | {m["sender"]}: {m["text"]}'


def main(argv=None, opener=urllib.request.urlopen):
    ap = argparse.ArgumentParser(description="Read allow-listed WhatsApp chats (read-only)")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new", help="messages nobody has dealt with yet; then run `mark`")
    sub.add_parser("mark", help="mark the messages the last `new` showed as dealt with (inside this tool only; WhatsApp is not touched)")
    r = sub.add_parser("recent")
    r.add_argument("--hours", type=int, default=24)
    r.add_argument("--chat")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=20)
    sub.add_parser("chats")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "new":
            res = call("GET", "/messages/new", opener=opener)
            msgs = res["data"]["messages"]
            with open(STATE, "w") as f:
                json.dump([{"chat": m["chatJid"], "id": m["id"]} for m in msgs], f)
            print(json.dumps(res, indent=2) if a.json else ("\n".join(fmt(m) for m in msgs) + "\n\n" + res["data"]["note"] if msgs else "No new messages."))
        elif a.cmd == "mark":
            try:
                keys = json.load(open(STATE))
            except (OSError, ValueError):
                print("nothing to mark: run `new` first")
                return 0
            res = call("POST", "/messages/reported", body={"messages": keys}, opener=opener)
            os.remove(STATE)
            print(f'marked {res["marked"]} message(s) as dealt with')
        elif a.cmd == "recent":
            res = call("GET", "/messages/recent", {"hours": a.hours, "chat": a.chat}, opener=opener)
            print(json.dumps(res, indent=2) if a.json else ("\n".join(fmt(m) for m in res["messages"]) or "No messages in that period."))
        elif a.cmd == "search":
            res = call("GET", "/messages/search", {"q": a.query, "limit": a.limit}, opener=opener)
            print(json.dumps(res, indent=2) if a.json else ("\n".join(fmt(m) for m in res["results"]) or f'No messages match "{a.query}".'))
        else:
            res = call("GET", "/chats", opener=opener)
            print("\n".join(f'{c["name"] or c["jid"]}' for c in res["chats"]) or "No chats are being read yet.")
    except ReadError as e:
        print(f"whatsapp: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
