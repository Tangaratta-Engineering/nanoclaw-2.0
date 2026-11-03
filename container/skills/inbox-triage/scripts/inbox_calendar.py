#!/usr/bin/env python3
"""Add events from email to George's Google Calendar, without duplicates. See SKILL.md.

Calls the Calendar API with curl; the OneCLI gateway injects the OAuth token.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
from zoneinfo import ZoneInfo

API = "https://www.googleapis.com/calendar/v3/calendars"
TZ = "Australia/Sydney"
DATA = os.environ.get("INBOX_DATA", "/workspace/projects/.nanoclaw-data/inbox-triage")
RULES = os.path.join(DATA, "calendar-rules.json")
DEFAULT_CALENDARS = ["primary", "Family"]
APPOINTMENT_WORDS = re.compile(r"\b(dr|doctor|dentist|dental|physio\w*|chiro\w*|appointment|appt|meeting|interview|consult\w*|specialist|psychiatrist|psychologist|surgery|review|call with|flight|parent.?teacher|exam|vet|hearing|booking)\b", re.I)


class CalError(Exception):
    pass


def call(method, url, body=None, runner=subprocess.run):
    cmd = ["curl", "-sS", "--max-time", "60", "-X", method, url, "-H", "Content-Type: application/json", "-w", "\n%{http_code}"]
    if body is not None:
        cmd += ["--data-binary", "@-"]
    p = runner(cmd, input=json.dumps(body) if body is not None else None, capture_output=True, text=True)
    if p.returncode != 0:
        raise CalError(f"network error: {p.stderr.strip() or p.returncode}")
    text, _, code = p.stdout.rpartition("\n")
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        raise CalError(f"HTTP {code}: unreadable response")
    if not code.startswith("2"):
        raise CalError(f"HTTP {code}: {data.get('error', {}).get('message', text[:200])}")
    return data


def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def parse_start(s):
    s = s.strip().replace(" ", "T")
    try:
        if len(s) == 10:
            return dt.date.fromisoformat(s), None
        return None, dt.datetime.fromisoformat(s)
    except ValueError:
        raise CalError(f"bad date/time '{s}' (use 2026-10-23 or 2026-10-23T08:30)")


def build_event(a):
    day, when = parse_start(a.start)
    desc = (a.notes or "").strip()
    if a.source_link:
        desc += ("\n\n" if desc else "") + f"From email: {a.source_link}\nAdded by NanoClaw"
    ev = {"summary": a.title, "description": desc,
          "extendedProperties": {"private": {"nanoclawKey": a.key or norm(a.title)[:60] + "|" + a.start[:10]}}}
    if a.location:
        ev["location"] = a.location
    if day:
        ev["start"] = {"date": day.isoformat()}
        ev["end"] = {"date": (dt.date.fromisoformat(a.end[:10]) if a.end else day).__add__(dt.timedelta(days=1)).isoformat()}
    else:
        end = dt.datetime.fromisoformat(a.end.replace(" ", "T")) if a.end else when + dt.timedelta(hours=1)
        ev["start"] = {"dateTime": when.isoformat(), "timeZone": TZ}
        ev["end"] = {"dateTime": end.isoformat(), "timeZone": TZ}
    return ev, (day or when.date())


def existing(a, event_day, run):
    """Events on that day (any calendar the tool can see on `a.calendar`) that already cover this item."""
    cal = urllib.parse.quote(a.calendar, safe="")
    t0 = dt.datetime.combine(event_day, dt.time.min) - dt.timedelta(hours=12)
    t1 = dt.datetime.combine(event_day, dt.time.max) + dt.timedelta(hours=12)
    q = urllib.parse.urlencode({"timeMin": t0.isoformat() + "Z", "timeMax": t1.isoformat() + "Z", "singleEvents": "true", "maxResults": "50"})
    items = call("GET", f"{API}/{cal}/events?{q}", None, run).get("items", [])
    want = norm(a.title)
    key = (a.key or "")
    for e in items:
        got = norm(e.get("summary", ""))
        same_key = key and e.get("extendedProperties", {}).get("private", {}).get("nanoclawKey") == key
        if same_key or (want and got and (want in got or got in want)):
            return e
    return None


def cmd_add(a, run=subprocess.run):
    ev, day = build_event(a)
    if day < dt.date.today() and not a.allow_past:
        raise CalError(f"{day} is in the past; not adding")
    dup = existing(a, day, run)
    if dup:
        return f"Already on the calendar: {dup.get('summary')} | {dup.get('htmlLink', '')}"
    r = call("POST", f"{API}/{urllib.parse.quote(a.calendar, safe='')}/events", ev, run)
    return f"Added: {r.get('summary')} | {a.start} | {r.get('htmlLink', '')}"


# ---- find / edit / delete / restore: changes to EXISTING events need George's explicit yes ------------
# Two steps: `edit`/`delete` only previews and prints a one-time token; the change is made by repeating the
# command with `--confirm TOKEN`, and only after George has said yes to that exact preview. Every applied
# change logs the event as it was, so `restore` can undo a delete and the old values can be re-applied.

PENDING = os.path.join(DATA, "calendar-pending.json")
CHANGELOG = os.path.join(DATA, "calendar-changes.jsonl")
TOKEN_TTL = 30 * 60


def _read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _ev_url(cal, event_id):
    return f"{API}/{urllib.parse.quote(cal, safe='')}/events/{urllib.parse.quote(event_id, safe='')}"


def describe(ev):
    st = ev.get("start", {})
    when = st.get("dateTime") or st.get("date") or "?"
    en = ev.get("end", {})
    until = en.get("dateTime") or en.get("date") or ""
    out = f"{ev.get('summary', '(no title)')} | {when}" + (f" -> {until}" if until and until != when else "")
    if ev.get("location"):
        out += f" | {ev['location']}"
    return out


def cmd_find(a, run=subprocess.run):
    today = dt.date.today()
    t0 = day_bounds(today - dt.timedelta(days=a.past_days))[0]
    t1 = day_bounds(today + dt.timedelta(days=a.days))[0]
    q = (a.query or "").lower()
    rows = []
    for cal, label in calendar_ids(load_rules()["calendars"], run):
        for e in list_events(cal, t0, t1, run):
            if q and q not in e.get("summary", "").lower() and q not in e.get("description", "").lower():
                continue
            rows.append(f"{e['id']} | {label} | {describe(e)}")
    return "\n".join(rows) or "No matching events."


def _patch_from_args(a, ev):
    patch = {}
    if a.title:
        patch["summary"] = a.title
    if a.location is not None:
        patch["location"] = a.location
    if a.notes is not None:
        patch["description"] = a.notes
    if a.start or a.end:
        old_start = ev.get("start", {})
        old_end = ev.get("end", {})
        day, when = parse_start(a.start) if a.start else (None, None)
        if a.start and day:
            patch["start"] = {"date": day.isoformat()}
            end_day = dt.date.fromisoformat(a.end[:10]) if a.end else day
            patch["end"] = {"date": (end_day + dt.timedelta(days=1)).isoformat()}
        elif a.start:
            end = dt.datetime.fromisoformat(a.end.replace(" ", "T")) if a.end else when + dt.timedelta(hours=1)
            patch["start"] = {"dateTime": when.isoformat(), "timeZone": TZ}
            patch["end"] = {"dateTime": end.isoformat(), "timeZone": TZ}
        else:  # only the end changes
            if "date" in old_start:
                patch["end"] = {"date": (dt.date.fromisoformat(a.end[:10]) + dt.timedelta(days=1)).isoformat()}
            else:
                patch["end"] = {"dateTime": dt.datetime.fromisoformat(a.end.replace(" ", "T")).isoformat(), "timeZone": TZ}
    if not patch:
        raise CalError("nothing to change: give at least one of --title --start --end --location --notes")
    return patch


def _check_single(ev):
    if ev.get("recurrence") or ev.get("recurringEventId"):
        raise CalError("this is a repeating event; I don't change those. Ask George to change it in the Calendar app")
    if ev.get("status") == "cancelled":
        raise CalError("that event is already deleted (use restore to bring it back)")


def _issue_token(op, cal, event_id, patch):
    pend = {k: v for k, v in _read_json(PENDING, {}).items() if v.get("expires", 0) > dt.datetime.now().timestamp()}
    import secrets
    tok = secrets.token_hex(3)
    pend[tok] = {"op": op, "cal": cal, "id": event_id, "patch": patch, "expires": dt.datetime.now().timestamp() + TOKEN_TTL}
    os.makedirs(os.path.dirname(PENDING), exist_ok=True)
    with open(PENDING, "w") as f:
        json.dump(pend, f)
    return tok


def _take_token(tok, op, cal, event_id):
    pend = _read_json(PENDING, {})
    t = pend.pop(tok, None)
    if not t or t["expires"] < dt.datetime.now().timestamp() or (t["op"], t["cal"], t["id"]) != (op, cal, event_id):
        raise CalError("that confirmation code is unknown, expired, or for a different change. Run the command again without --confirm and show George the new preview")
    with open(PENDING, "w") as f:
        json.dump(pend, f)
    return t


def _log_change(op, cal, before, patch=None):
    os.makedirs(os.path.dirname(CHANGELOG), exist_ok=True)
    with open(CHANGELOG, "a") as f:
        f.write(json.dumps({"at": dt.datetime.now().isoformat(timespec="seconds"), "op": op, "calendar": cal, "id": before.get("id"), "before": before, "patch": patch}) + "\n")


def cmd_change(a, run=subprocess.run):
    op = a.cmd  # edit | delete
    ev = call("GET", _ev_url(a.calendar, a.event_id), None, run)
    _check_single(ev)
    patch = _patch_from_args(a, ev) if op == "edit" else None
    if not a.confirm:
        tok = _issue_token(op, a.calendar, a.event_id, patch)
        lines = [f"PREVIEW ONLY, nothing changed yet.", f"Event: {describe(ev)}"]
        if op == "edit":
            lines.append("Change to: " + json.dumps({k: v for k, v in patch.items()}))
        else:
            lines.append("This event would be DELETED (it can be restored afterwards).")
        lines.append(f"Show George exactly this and wait for a clear yes. Then run the same command again with: --confirm {tok}")
        return "\n".join(lines)
    t = _take_token(a.confirm, op, a.calendar, a.event_id)
    _log_change(op, a.calendar, ev, t["patch"])
    if op == "edit":
        r = call("PATCH", _ev_url(a.calendar, a.event_id), t["patch"], run)
        return f"Changed: {describe(r)} | {r.get('htmlLink', '')}"
    call("DELETE", _ev_url(a.calendar, a.event_id), None, run)
    return f"Deleted: {describe(ev)}. To undo: inbox-calendar restore {a.event_id}"


def cmd_restore(a, run=subprocess.run):
    r = call("PATCH", _ev_url(a.calendar, a.event_id), {"status": "confirmed"}, run)
    return f"Restored: {describe(r)}"


def main(argv=None, run=subprocess.run):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--title", required=True)
    s.add_argument("--start", required=True, help="2026-10-23 (all day) or 2026-10-23T08:30 (Sydney time)")
    s.add_argument("--end", help="end date/time; default start+1h (all-day: same day)")
    s.add_argument("--location")
    s.add_argument("--notes")
    s.add_argument("--source-link", help="Gmail link to the email this came from")
    s.add_argument("--key", help="stable dedupe key, e.g. the Gmail thread id")
    s.add_argument("--calendar", default="primary")
    s.add_argument("--allow-past", action="store_true")
    s = sub.add_parser("agenda", help="appointments vs routine for a day (default today)")
    s.add_argument("--offset", type=int, default=0, help="days from today (1 = tomorrow)")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("week", help="the coming week day by day (default: the week starting Monday)")
    s.add_argument("--start", help="first day, YYYY-MM-DD"); s.add_argument("--days", type=int, default=7); s.add_argument("--json", action="store_true")
    s = sub.add_parser("learn", help="remember that events with this title are routine or a real appointment")
    s.add_argument("--title", required=True)
    s.add_argument("--as", dest="kind", choices=["routine", "appointment"], required=True)
    s = sub.add_parser("find", help="list events (with ids) matching a text, to edit or delete")
    s.add_argument("--query", default=""); s.add_argument("--days", type=int, default=60); s.add_argument("--past-days", type=int, default=7)
    for name, hlp in (("edit", "change one event (preview first; needs George's yes, then --confirm)"), ("delete", "delete one event (preview first; needs George's yes, then --confirm)")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("event_id"); s.add_argument("--calendar", default="primary")
        s.add_argument("--confirm", metavar="CODE", help="the code printed by the preview, ONLY after George said yes to it")
        if name == "edit":
            s.add_argument("--title"); s.add_argument("--start"); s.add_argument("--end"); s.add_argument("--location"); s.add_argument("--notes")
    s = sub.add_parser("restore", help="bring back an event deleted with this tool")
    s.add_argument("event_id"); s.add_argument("--calendar", default="primary")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "find":
            print(cmd_find(a, run))
        elif a.cmd in ("edit", "delete"):
            print(cmd_change(a, run))
        elif a.cmd == "restore":
            print(cmd_restore(a, run))
        elif a.cmd == "agenda":
            print(cmd_agenda(a, run))
        elif a.cmd == "week":
            print(cmd_week(a, run))
        elif a.cmd == "learn":
            print(learn(a.title, a.kind))
        else:
            print(cmd_add(a, run))
        return 0
    except CalError as e:
        print(f"inbox-calendar: {e}", file=sys.stderr)
        return 1



# ---- agenda: today's calendar, split into real appointments vs standing routine -------------

def load_rules(path=None):
    try:
        with open(path or RULES) as f:
            r = json.load(f)
    except (OSError, ValueError):
        r = {}
    return {"routine": r.get("routine", []), "appointment": r.get("appointment", []), "calendars": r.get("calendars", DEFAULT_CALENDARS)}


def save_rules(r, path=None):
    path = path or RULES
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(r, f, indent=1)


def learn(title, kind, path=None):
    """Remember George's correction: events whose title contains `title` are `kind`."""
    r = load_rules(path)
    key = norm(title)
    other = "appointment" if kind == "routine" else "routine"
    r[other] = [x for x in r[other] if x != key]
    if key not in r[kind]:
        r[kind].append(key)
    save_rules(r, path)
    return f"Learned: '{key}' is {kind}."


def classify(ev, rules, counts):
    """Return ('appointment'|'routine'|'allday', reason). Explicit rules beat heuristics."""
    title = norm(ev.get("summary", ""))
    for kind in ("appointment", "routine"):
        if any(k and k in title for k in rules[kind]):
            return kind, "your rule"
    if "date" in ev.get("start", {}):
        return "allday", "all-day"
    others = [a for a in ev.get("attendees", []) if not a.get("self")]
    if APPOINTMENT_WORDS.search(ev.get("summary", "")) or ev.get("location") or others:
        return "appointment", "appointment words, a place or other people"
    if ev.get("recurringEventId") or counts.get(title, 0) >= 5:
        return "routine", "repeats"
    return "appointment", "one-off"


def day_bounds(day):
    tz = ZoneInfo(TZ)
    a = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    return a.isoformat(), (a + dt.timedelta(days=1)).isoformat()


def list_events(cal, t0, t1, run):
    q = urllib.parse.urlencode({"timeMin": t0, "timeMax": t1, "singleEvents": "true", "orderBy": "startTime", "maxResults": "250"})
    return call("GET", f"{API}/{urllib.parse.quote(cal, safe='')}/events?{q}", None, run).get("items", [])


def calendar_ids(wanted, run):
    items = call("GET", "https://www.googleapis.com/calendar/v3/users/me/calendarList", None, run).get("items", [])
    out = []
    for w in wanted:
        for i in items:
            if (w == "primary" and i.get("primary")) or i.get("summary", "").lower() == w.lower():
                out.append((i["id"], "primary" if i.get("primary") else i.get("summary", w)))
    return out


def hhmm(ev):
    s = ev["start"].get("dateTime")
    e = ev["end"].get("dateTime")
    f = lambda x: dt.datetime.fromisoformat(x).astimezone(ZoneInfo(TZ)).strftime("%H:%M")
    return f"{f(s)}-{f(e)}" if s and e else ""


def agenda(day, rules, run=subprocess.run):
    cals = calendar_ids(rules["calendars"], run)
    t0, t1 = day_bounds(day)
    h0, h1 = day_bounds(day - dt.timedelta(days=30))[0], t0
    out = {"date": day.isoformat(), "appointment": [], "routine": [], "allday": []}
    for cid, name in cals:
        counts = {}
        for e in list_events(cid, h0, h1, run):
            counts[norm(e.get("summary", ""))] = counts.get(norm(e.get("summary", "")), 0) + 1
        for e in list_events(cid, t0, t1, run):
            if e.get("status") == "cancelled":
                continue
            kind, why = classify(e, rules, counts)
            out[kind].append({"time": hhmm(e), "title": e.get("summary", "(no title)"), "where": e.get("location", ""), "calendar": name, "why": why})
    for k in ("appointment", "routine", "allday"):
        out[k].sort(key=lambda x: x["time"])
    return out


def render(a):
    lines = [f"CALENDAR {a['date']}"]
    if a["appointment"]:
        lines.append("APPOINTMENTS")
        lines += [f"  {x['time'] or 'all day'}  {x['title']}" + (f" @ {x['where']}" if x["where"] else "") + (f"  [{x['calendar']}]" if x["calendar"] != "primary" and x["calendar"] else "") for x in a["appointment"]]
    else:
        lines.append("APPOINTMENTS\n  none")
    if a["routine"]:
        lines.append("ROUTINE: " + "; ".join(f"{x['title']} {x['time'].split('-')[0]}".strip() for x in a["routine"]))
    if a["allday"]:
        lines.append("ALL DAY: " + "; ".join(x["title"] for x in a["allday"]))
    return "\n".join(lines)


def cmd_agenda(a, run=subprocess.run):
    day = dt.datetime.now(ZoneInfo(TZ)).date() + dt.timedelta(days=a.offset)
    ag = agenda(day, load_rules(), run)
    return json.dumps(ag, indent=1) if a.json else render(ag)

# ---- week view: the coming seven days at once ------------------------------------------------

def default_week_start(today):
    """Run on Sunday night -> the week starting tomorrow (Monday); on Monday -> today; otherwise the next Monday."""
    if today.weekday() == 0:
        return today
    return today + dt.timedelta(days=(7 - today.weekday()))


def _local_date(ev):
    s = ev["start"]
    if "date" in s:
        return dt.date.fromisoformat(s["date"])
    return dt.datetime.fromisoformat(s["dateTime"]).astimezone(ZoneInfo(TZ)).date()


def _span(ev):
    """(start datetime, end datetime) for timed events, else None."""
    s, e = ev["start"].get("dateTime"), ev["end"].get("dateTime")
    return (dt.datetime.fromisoformat(s), dt.datetime.fromisoformat(e)) if s and e else None


def week(start, days, rules, run=subprocess.run):
    """Events for `days` days from `start`, grouped by day. History is fetched once per calendar."""
    cals = calendar_ids(rules["calendars"], run)
    end_day = start + dt.timedelta(days=days)
    t0, t1 = day_bounds(start)[0], day_bounds(end_day - dt.timedelta(days=1))[1]
    h0 = day_bounds(start - dt.timedelta(days=30))[0]
    by_day = {start + dt.timedelta(days=i): {"appointment": [], "routine": []} for i in range(days)}
    multi = []
    for cid, name in cals:
        counts = {}
        for e in list_events(cid, h0, t0, run):
            k = norm(e.get("summary", ""))
            counts[k] = counts.get(k, 0) + 1
        for e in list_events(cid, t0, t1, run):
            if e.get("status") == "cancelled":
                continue
            kind, why = classify(e, rules, counts)
            title = e.get("summary", "(no title)")
            if kind == "allday":
                first = _local_date(e)
                last = dt.date.fromisoformat(e["end"]["date"]) - dt.timedelta(days=1) if "date" in e.get("end", {}) else first
                multi.append({"title": title, "from": max(first, start).isoformat(), "to": min(last, end_day - dt.timedelta(days=1)).isoformat(), "full_from": first.isoformat(), "full_to": last.isoformat(), "calendar": name})
                continue
            d = _local_date(e)
            if d in by_day:
                by_day[d][kind].append({"time": hhmm(e), "title": title, "where": e.get("location", ""), "calendar": name, "span": _span(e)})
    out = {"start": start.isoformat(), "days": [], "all_day": multi, "daily_routine": []}
    routine_days = {}
    for d, parts in by_day.items():
        for r in parts["routine"]:
            routine_days.setdefault(norm(r["title"]), set()).add(d)
    daily = {t for t, ds in routine_days.items() if len(ds) >= max(4, days - 3)}
    for d in sorted(by_day):
        appts = sorted(by_day[d]["appointment"], key=lambda x: x["time"])
        overlaps, dupes = [], []
        for i, a in enumerate(appts):
            for b in appts[i + 1:]:
                if a["span"] and b["span"] and a["span"][0] < b["span"][1] and b["span"][0] < a["span"][1]:
                    if a["span"] == b["span"]:
                        dupes.append(f"{a['title']} / {b['title']}")  # same time slot: usually one event entered twice
                    else:
                        overlaps.append(f"{a['title']} overlaps {b['title']}")
        routine = [r for r in sorted(by_day[d]["routine"], key=lambda x: x["time"]) if norm(r["title"]) not in daily]
        out["days"].append({"date": d.isoformat(), "appointments": [{k: v for k, v in x.items() if k != "span"} for x in appts],
                            "routine": [{k: v for k, v in x.items() if k != "span"} for x in routine], "overlaps": overlaps, "possible_duplicates": dupes})
    seen = {}
    for d in sorted(by_day):
        for r in by_day[d]["routine"]:
            if norm(r["title"]) in daily and norm(r["title"]) not in seen:
                seen[norm(r["title"])] = f"{r['title']} {r['time'].split('-')[0]}".strip()
    out["daily_routine"] = list(seen.values())
    return out


def _all_day_label(x):
    first, last = dt.date.fromisoformat(x["full_from"]), dt.date.fromisoformat(x["full_to"])
    return f"{x['title']} (until {last:%d %b})" if last != first else f"{x['title']} ({first:%a %d %b})"


def render_week(w):
    first = dt.date.fromisoformat(w["start"])
    last = dt.date.fromisoformat(w["days"][-1]["date"])
    lines = [f"WEEK {first:%a %d %b} to {last:%a %d %b %Y}"]
    busiest = max(w["days"], key=lambda d: len(d["appointments"]))
    if busiest["appointments"]:
        lines.append(f"Busiest day: {dt.date.fromisoformat(busiest['date']):%A} ({len(busiest['appointments'])} appointments)")
    clashes = [f"{dt.date.fromisoformat(d['date']):%a %d %b}: {o}" for d in w["days"] for o in d["overlaps"]]
    if clashes:
        lines.append("CLASHES: " + "; ".join(clashes))
    dupes = [f"{dt.date.fromisoformat(d['date']):%a %d %b}: {x}" for d in w["days"] for x in d["possible_duplicates"]]
    if dupes:
        lines.append("POSSIBLE DUPLICATE ENTRIES (same time slot): " + "; ".join(dupes))
    if w["all_day"]:
        lines.append("ALL-DAY / MULTI-DAY: " + "; ".join(_all_day_label(x) for x in w["all_day"]))
    if w["daily_routine"]:
        lines.append("REGULAR (most days): " + "; ".join(w["daily_routine"]))
    for d in w["days"]:
        day = dt.date.fromisoformat(d["date"])
        lines.append(f"\n{day:%A %d %b}")
        if not d["appointments"]:
            lines.append("  clear (no appointments)")
        for x in d["appointments"]:
            lines.append(f"  {x['time'] or 'all day'}  {x['title']}" + (f" @ {x['where']}" if x["where"] else "") + (f"  [{x['calendar']}]" if x["calendar"] != "primary" else ""))
        if d["routine"]:
            lines.append("  routine: " + "; ".join(f"{x['title']} {x['time'].split('-')[0]}".strip() for x in d["routine"]))
    return "\n".join(lines)


def cmd_week(a, run=subprocess.run):
    today = dt.datetime.now(ZoneInfo(TZ)).date()
    start = dt.date.fromisoformat(a.start) if a.start else default_week_start(today)
    w = week(start, a.days, load_rules(), run)
    return json.dumps(w, indent=1) if a.json else render_week(w)


if __name__ == "__main__":
    sys.exit(main())
