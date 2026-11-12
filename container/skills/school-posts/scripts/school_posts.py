#!/usr/bin/env python3
"""Search and read the history of school (Audiri) posts and their documents. See SKILL.md."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("SCHOOL_POSTS_URL", "http://172.21.0.1:8765")
TIMEOUT = 30


class PostsError(Exception):
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
            raise PostsError("the school-posts service refused the request (no API key was added). "
                             "Tell George the Audiri secret is missing or not assigned in OneCLI")
        if e.code == 404:
            raise PostsError("no such post or event")
        raise PostsError(f"the school-posts service answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise PostsError(f"cannot reach the school-posts service: {getattr(e, 'reason', e)}")


def line(p):
    docs = ", ".join(f'{d["name"]} ({d["status"]})' for d in p.get("documents", [])) or "no documents"
    return f'{p["postId"]} | {(p.get("postedAt") or "")[:10]} | {p["kind"]} | {p["title"]}\n    documents: {docs}'


def fmt_search(res):
    if not res["results"]:
        return f'No posts match "{res["query"]}".'
    out = [f'{res["count"]} post(s) match "{res["query"]}" (newest information may be in a document, see show):']
    for p in res["results"]:
        out.append(line(p))
        if p.get("snippet"):
            out.append("    ..." + p["snippet"].replace("\n", " ") + "...")
    return "\n".join(out)


def fmt_post(p):
    out = [f'{p["title"]}', f'Posted {(p.get("postedAt") or "")[:10]} | {p["kind"]} | groups: {", ".join(p["groups"]) or "all"} | id {p["postId"]}',
           "", p["content"] or "(no text)"]
    for d in p.get("documents", []):
        out += ["", f'--- {d["kind"]}: {d["name"]} [{d["status"]}] {d["url"]}']
        if d["status"] == "ok" and d.get("text"):
            out.append(d["text"])
        elif d["kind"] == "image":
            out.append("(image: not read; open the link and look at it)")
        elif d["status"] == "no_text":
            out.append("(no text found: a scan or image; open the link and look at it)")
        elif d["status"] == "pending":
            out.append("(still being read: try again in a minute, or open the link)")
        elif d["status"] in ("failed", "skipped_host"):
            out.append("(not read by the service: open the link yourself)")
    if p.get("reportedSummary"):
        out += ["", f'--- What was sent to George ({(p.get("reportedAt") or "")[:16]}):', p["reportedSummary"]]
    return "\n".join(out)


def when(e):
    """'Fri 13 Nov 17:30' for a timed event, 'Fri 20 Nov (all day)' for an all-day one. Times are already in the school's timezone."""
    from datetime import datetime
    try:
        d = datetime.fromisoformat(e["start"])
    except (KeyError, TypeError, ValueError):
        return e.get("start") or "unknown time"
    return d.strftime("%a %d %b") + (" (all day)" if e.get("allDay") else d.strftime(" %H:%M"))


def event_line(e):
    bits = [when(e), e["title"].strip()]
    if e.get("location"):
        bits.append("at " + e["location"])
    if e.get("status") and e["status"] != "PUBLISHED":
        bits.append(f'[{e["status"]}]')
    out = " | ".join(bits) + f'  (id {e["eventId"]})'
    if e.get("groups"):
        out += "\n    groups: " + ", ".join(e["groups"])
    if e.get("content"):
        out += "\n    " + e["content"].strip().replace("\n", " / ")[:300]
    return out


def fmt_events(res, empty):
    items = res.get("events") or res.get("results") or []
    if not items:
        return empty
    return "\n".join(event_line(e) for e in items)


def fmt_event(e):
    out = [event_line(e)]
    if e.get("removedAt"):
        out.append("Removed from the school calendar " + e["removedAt"][:10])
    for c in e.get("changes") or []:
        out.append(f'  {(c.get("detectedAt") or "")[:10]} {c.get("change")}: {c.get("summary") or ""}')
    return "\n".join(out)


def fmt_changes(res):
    d = res.get("data", {})
    if d.get("error"):
        return "Could not read the school calendar: " + str(d["error"])
    if not d.get("changes"):
        return "No calendar changes."
    out = [f'{d["count"]} calendar change(s):']
    for c in d["changes"]:
        out.append(f'{c["change"].upper()}: {event_line(c["event"])}' + (f'\n    what changed: {c["summary"]}' if c.get("summary") else ""))
    return "\n".join(out)


def main(argv=None, opener=urllib.request.urlopen):
    ap = argparse.ArgumentParser(description="Search and read school post history")
    ap.add_argument("--json", action="store_true", help="print the raw JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--since", help="YYYY-MM-DD")
    s.add_argument("--until", help="YYYY-MM-DD")
    s.add_argument("--kind", choices=["newsletter", "excursion", "reminder", "other"])
    s.add_argument("--group")
    s.add_argument("--limit", type=int, default=10)
    sh = sub.add_parser("show")
    sh.add_argument("post_id")
    la = sub.add_parser("latest")
    la.add_argument("kind", nargs="?", choices=["newsletter", "excursion", "reminder", "other"])
    la.add_argument("-n", type=int, default=1)
    un = sub.add_parser("unreported", help="posts stored but never reported to George")
    un.add_argument("--min-age", type=int, default=20)
    rp = sub.add_parser("report", help="record the summary you sent George")
    rp.add_argument("post_id")
    rp.add_argument("summary")
    ev = sub.add_parser("events", help="the school calendar (read-only)")
    evs = ev.add_subparsers(dest="ecmd", required=True)
    up = evs.add_parser("upcoming")
    up.add_argument("--days", type=int, default=14)
    up.add_argument("--group")
    es = evs.add_parser("search")
    es.add_argument("query")
    es.add_argument("--limit", type=int, default=10)
    esh = evs.add_parser("show")
    esh.add_argument("event_id")
    evs.add_parser("changes", help="calendar changes not yet reported (each is returned once; the scheduled task only)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "search":
            res = call("GET", "/posts/search", {"q": a.query, "since": a.since, "until": a.until, "kind": a.kind, "group": a.group, "limit": a.limit}, opener=opener)
            print(json.dumps(res, indent=2) if a.json else fmt_search(res))
        elif a.cmd == "show":
            res = call("GET", "/posts/" + urllib.parse.quote(a.post_id, safe=""), opener=opener)
            print(json.dumps(res, indent=2) if a.json else fmt_post(res))
        elif a.cmd == "latest":
            res = call("GET", "/posts/latest", {"kind": a.kind, "n": a.n}, opener=opener)
            print(json.dumps(res, indent=2) if a.json else "\n\n=====\n\n".join(fmt_post(p) for p in res["posts"]) or "No posts stored.")
        elif a.cmd == "unreported":
            res = call("GET", "/posts/unreported", {"min_age_minutes": a.min_age}, opener=opener)
            print(json.dumps(res, indent=2) if a.json else (f'{res["count"]} unreported post(s):\n' + "\n".join(line(p) for p in res["posts"]) if res["count"] else "Nothing unreported."))
        elif a.cmd == "events":
            if a.ecmd == "upcoming":
                res = call("GET", "/events/upcoming", {"days": a.days, "group": a.group}, opener=opener)
                out = fmt_events(res, f"No school events in the next {a.days} days.")
            elif a.ecmd == "search":
                res = call("GET", "/events/search", {"q": a.query, "limit": a.limit}, opener=opener)
                out = fmt_events(res, f'No calendar events match "{a.query}".')
            elif a.ecmd == "show":
                res = call("GET", "/events/" + urllib.parse.quote(a.event_id, safe=""), opener=opener)
                out = fmt_event(res)
            else:
                res = call("GET", "/new-events", opener=opener)
                out = fmt_changes(res)
            print(json.dumps(res, indent=2) if a.json else out)
        else:
            call("POST", "/posts/" + urllib.parse.quote(a.post_id, safe="") + "/report", body={"summary": a.summary}, opener=opener)
            print("recorded")
    except PostsError as e:
        print(f"school-posts: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
