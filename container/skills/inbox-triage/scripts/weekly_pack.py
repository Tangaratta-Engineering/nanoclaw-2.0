#!/usr/bin/env python3
"""Gather the data for the Sunday-night week briefing: next week's calendar and the open action items.
Prints one JSON line {wakeAgent, data} so it can be a scheduled-task script. Each part fails on its own:
a Notion or Calendar error is reported in the data instead of stopping the briefing."""
import json
import os
import re
import subprocess
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "notion", "scripts"))

DATA = os.environ.get("INBOX_DATA", "/workspace/projects/.nanoclaw-data/inbox-triage")


def calendar_part():
    import inbox_calendar as c
    return c.cmd_week(SimpleNamespace(start=None, days=7, json=False))


KEYS = ("Confidence", "First seen", "Email link", "Last surfaced", "Status", "Why", "Thread id", "Due", "Type", "Item", "Amount", "Payee", "How to pay", "Draft id")
FIELD = re.compile(r"; (?=(?:%s)=)" % "|".join(KEYS))


def compact(text):
    """Keep only item, type, due, amount and payee from each ledger line; the full reasoning stays in Notion."""
    out = []
    for line in text.splitlines():
        row_id, _, rest = line.partition(" | ")
        f = dict(p.split("=", 1) for p in FIELD.split(rest) if "=" in p)
        if not f:
            out.append(line)  # not a ledger row (for example "No matching rows."): keep as is
            continue
        out.append(" | ".join(x for x in (f.get("Type", ""), f.get("Item", ""), f"due {f['Due']}" if f.get("Due") else "no due date", f.get("Amount", ""), f.get("Payee", "")) if x))
    return "\n".join(out) if out else "none"


def ledger_part():
    import notion_db
    with open(os.path.join(DATA, "config.json")) as f:
        db = json.load(f)["ledger_database"]
    out = {}
    for status in ("Open", "Awaiting approval"):
        out[status] = compact(notion_db.db_query(SimpleNamespace(db=db, where=[f"Status={status}"], sort="Due:asc", limit=60), subprocess.run))
    return out


def build(parts=None):
    parts = parts or {"calendar_week": calendar_part, "ledger_open_items": ledger_part}
    data = {}
    for name, fn in parts.items():
        try:
            data[name] = fn()
        except Exception as e:  # noqa: BLE001 - report, never stop the briefing
            data[name] = f"(could not load: {type(e).__name__}: {str(e)[:200]})"
    return {"wakeAgent": True, "data": data}


def main():
    print(json.dumps(build()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
