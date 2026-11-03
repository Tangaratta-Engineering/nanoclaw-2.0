#!/usr/bin/env python3
"""Woolworths shopping lists for George. See SKILL.md.

Sends a request to the host's Woolworths bridge (a JSON file in the shared queue) and prints the answer.
The bridge works inside George's signed-in browser; this tool never sees a password or session.
"""
import argparse
import json
import os
import secrets
import sys
import time

QUEUE = os.environ.get("WOOLIES_QUEUE", "/workspace/projects/.nanoclaw-data/woolies/queue")
DEFAULT_LIST = os.environ.get("WOOLIES_LIST", "NanoClaw")
TIMEOUT = float(os.environ.get("WOOLIES_TIMEOUT", "70"))


class WooliesError(Exception):
    pass


def ask(req, queue=QUEUE, timeout=TIMEOUT, sleep=time.sleep):
    rid = f"{int(time.time())}-{secrets.token_hex(4)}"
    inbox = os.path.join(queue, "in", rid + ".json")
    outbox = os.path.join(queue, "out", rid + ".json")
    if not os.path.isdir(os.path.join(queue, "in")):
        raise WooliesError("the Woolworths bridge isn't set up on the server (no queue folder)")
    tmp = inbox + ".tmp"
    with open(tmp, "w") as f:
        json.dump(req, f)
    os.chmod(tmp, 0o666)
    os.rename(tmp, inbox)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(outbox):
            with open(outbox) as f:
                res = json.load(f)
            os.remove(outbox)
            if not res.get("ok"):
                raise WooliesError(res.get("error", "unknown error"))
            return res["data"]
        sleep(0.5)
    try:
        os.remove(inbox)
    except OSError:
        pass
    raise WooliesError("no answer from the Woolworths bridge (is it running on the server? tell George)")


def money(v):
    return f"${v:.2f}" if isinstance(v, (int, float)) else "n/a"


def fmt_item(p):
    tags = []
    if p.get("boughtBefore"):
        tags.append("bought before")
    if p.get("special"):
        tags.append("on special")
    if not p.get("available", True):
        tags.append("UNAVAILABLE")
    return f"{p['stockcode']} | {p['name']} | {p.get('size') or ''} | {money(p.get('price'))}" + (f" | {p['cup']}" if p.get("cup") else "") + (f" | {', '.join(tags)}" if tags else "")


def parse_item(s):
    code, _, qty = s.partition("=")
    try:
        return {"stockcode": int(code), "qty": int(qty) if qty else 1}
    except ValueError:
        raise WooliesError(f"'{s}' isn't STOCKCODE or STOCKCODE=QTY")


def run(argv, ask=ask):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="is the server's Woolworths login working?")
    s = sub.add_parser("usual", help="search what George has bought before (best way to find his usual brand and size)")
    s.add_argument("query"); s.add_argument("-n", type=int, default=6)
    s = sub.add_parser("search", help="search all Woolworths products")
    s.add_argument("query"); s.add_argument("-n", type=int, default=6)
    sub.add_parser("lists", help="George's Woolworths lists")
    s = sub.add_parser("show", help="what is on a list")
    s.add_argument("--list", default=DEFAULT_LIST)
    s = sub.add_parser("add", help="add products (STOCKCODE or STOCKCODE=QTY) to a list; creates the list if missing")
    s.add_argument("--list", default=DEFAULT_LIST); s.add_argument("items", nargs="+")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "status":
            d = ask({"op": "status"})
            return "Signed in to Woolworths." if d["signedIn"] else "NOT signed in: George needs to sign in to the server's browser again."
        if a.cmd in ("usual", "search"):
            op = "history" if a.cmd == "usual" else "search"
            d = ask({"op": op, "query": a.query, "limit": a.n})
            if not d["items"]:
                return "No matches." if op == "search" else "Nothing like that in his purchase history. Try `search`."
            head = "From what George has bought before:" if op == "history" else "Woolworths search results:"
            return head + "\n" + "\n".join(fmt_item(p) for p in d["items"])
        if a.cmd == "lists":
            d = ask({"op": "lists"})
            return "\n".join(f"{l['name']} ({l['count']} items)" for l in d["lists"])
        if a.cmd == "show":
            try:
                d = ask({"op": "show", "list": a.list})
            except WooliesError as e:
                if a.list == DEFAULT_LIST and "no list called" in str(e):
                    return f"The '{a.list}' list doesn't exist yet; it is created the first time something is added."
                raise
            return f"{d['list']}: {d['total']} items\n" + "\n".join(fmt_item(p) for p in d["items"])
        if a.cmd == "add":
            d = ask({"op": "add", "list": a.list, "create": a.list == DEFAULT_LIST, "items": [parse_item(i) for i in a.items]})
            out = f"Added {len(d['added'])} to the Woolworths list '{d['list']}': " + ", ".join(map(str, d["added"]))
            if d["failed"]:
                out += "\nFAILED: " + ", ".join(f"{x['stockcode']} (HTTP {x['status']})" for x in d["failed"])
            return out
    except WooliesError as e:
        print(f"woolies: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    print(run(sys.argv[1:]))
