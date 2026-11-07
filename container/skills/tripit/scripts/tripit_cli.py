#!/usr/bin/env python3
"""Read and write the agents' TripIt account through the local tripit-bridge. See SKILL.md."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("TRIPIT_BRIDGE_URL", "http://192.168.3.13:8770/tripit")
KINDS = ["trips", "hotels", "flights", "transport", "activities", "cars"]
MAX_CHARS = 12_000
TIMEOUT = 90


class BridgeError(Exception):
    pass


def call(method, path, body=None, opener=urllib.request.urlopen):
    """The OneCLI gateway adds the bridge key; this script never holds it."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
    try:
        with opener(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read() or b"{}").get("detail", "")
        except Exception:
            detail = ""
        if e.code == 403 and (not detail or detail == "Invalid API key"):
            raise BridgeError("the TripIt bridge refused the request (no key was added). Tell George the TripIt secret is missing or not assigned in OneCLI")
        raise BridgeError(detail or f"the TripIt bridge answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise BridgeError(f"cannot reach the TripIt bridge: {getattr(e, 'reason', e)}")


def first(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def trips_summary(result):
    """One line per trip from whatever shape the list comes back in."""
    items = result.get("Trip") if isinstance(result, dict) else result
    if isinstance(items, dict):
        items = [items]
    if not items:
        return "No trips."
    lines = []
    for t in items:
        lines.append(f'{first(t, "uuid", "id")} | {first(t, "display_name", "displayName", "name")} | '
                     f'{first(t, "start_date", "startDate")} to {first(t, "end_date", "endDate")} | {first(t, "primary_location", "primaryLocation") or ""}')
    return f"{len(lines)} trip(s) (id | name | dates | location):\n" + "\n".join(lines)


OBJECTS = [("AirObject", "flight"), ("LodgingObject", "hotel"), ("TransportObject", "transport"), ("ActivityObject", "activity"), ("CarObject", "car")]


def listify(x):
    return x if isinstance(x, list) else ([x] if isinstance(x, dict) else [])


def when(o):
    seg = listify(o.get("Segment"))
    start = o.get("StartDateTime") or (seg[0].get("StartDateTime") if seg else None) or {}
    end = o.get("EndDateTime") or (seg[-1].get("EndDateTime") if seg else None) or {}
    f = lambda d: " ".join(x for x in (d.get("date"), (d.get("time") or "")[:5]) if x)
    return f"{f(start)} to {f(end)}".strip()


def where(o):
    a = o.get("Address") or {}
    seg = listify(o.get("Segment"))
    if seg:
        return f'{seg[0].get("start_city_name") or ""} to {seg[-1].get("end_city_name") or ""}'.strip()
    return first(o, "start_location_name") or ", ".join(x for x in (a.get("address"), a.get("city")) if x)


def trip_summary(result):
    """A trip and its bookings, one line each (the raw record is long)."""
    t = result.get("Trip") or {}
    lines = [f'{first(t, "display_name")} | {first(t, "start_date")} to {first(t, "end_date")} | {first(t, "primary_location") or ""} | id {first(t, "uuid")}']
    n = 0
    for key, label in OBJECTS:
        for o in listify(result.get(key)):
            n += 1
            lines.append(f'  {label} | {first(o, "uuid")} | {first(o, "display_name", "supplier_name") or "(no name)"} | {when(o)} | {where(o)}'
                         + (f' | conf {o["supplier_conf_num"]}' if o.get("supplier_conf_num") else ""))
    if not n:
        lines.append("  (no bookings yet)")
    return "\n".join(lines)


def dump(obj):
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "\n...(cut: ask for one object at a time)"


def parse_json(text):
    raw = sys.stdin.read() if text == "-" else text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BridgeError(f"the data is not valid JSON ({e})")
    if not isinstance(data, dict):
        raise BridgeError("the data must be a JSON object")
    return data


def main(argv=None, opener=urllib.request.urlopen):
    ap = argparse.ArgumentParser(description="TripIt (the agents' account)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trips", help="list trips")
    t.add_argument("--past", action="store_true")
    t.add_argument("--json", action="store_true")
    g = sub.add_parser("get", help="show one trip or booking")
    g.add_argument("kind", choices=KINDS)
    g.add_argument("id")
    g.add_argument("--json", action="store_true", help="the full raw record")
    for name in ("create", "update"):
        c = sub.add_parser(name, help=f"{name} a trip or booking from JSON ('-' reads stdin)")
        c.add_argument("kind", choices=KINDS)
        c.add_argument("data")
    d = sub.add_parser("delete", help="ask to delete: prints what would go and a code for George's yes")
    d.add_argument("kind", choices=KINDS)
    d.add_argument("id")
    ad = sub.add_parser("adopt", help="ask to change one of George's existing trips: prints the trip and a code for his yes")
    ad.add_argument("trip_id")
    ac = sub.add_parser("adopt-confirm", help="allow changes to that existing trip, after George said yes, using the code")
    ac.add_argument("code")
    dc = sub.add_parser("delete-confirm", help="delete, after George said yes, using the code")
    dc.add_argument("code")
    ch = sub.add_parser("changes", help="what the agents changed recently")
    ch.add_argument("--limit", type=int, default=30)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "trips":
            r = call("POST", "/call", {"kind": "trips", "verb": "list", "data": {"past": a.past}}, opener)["result"]
            print(dump(r) if a.json else trips_summary(r))
        elif a.cmd == "get":
            r = call("POST", "/call", {"kind": a.kind, "verb": "get", "id": a.id}, opener)["result"]
            print(trip_summary(r) if a.kind == "trips" and not a.json else dump(r))
        elif a.cmd in ("create", "update"):
            r = call("POST", "/call", {"kind": a.kind, "verb": a.cmd, "data": parse_json(a.data)}, opener)["result"]
            print(f"{a.cmd}d {a.kind[:-1] if a.kind.endswith('s') else a.kind}:")
            print(dump(r))
        elif a.cmd == "delete":
            r = call("POST", "/delete/request", {"kind": a.kind, "id": a.id}, opener)
            print("NOT DELETED YET. This is what would be deleted:")
            print(dump(r["preview"]))
            print(f'\nShow George exactly this and ask for his yes. If he says yes, run: tripit delete-confirm {r["code"]}  (code valid {r["expiresInMinutes"]:.0f} minutes)')
        elif a.cmd == "adopt":
            r = call("POST", "/adopt/request", {"tripId": a.trip_id}, opener)
            print("NOT ALLOWED YET. This is one of George's existing trips:")
            print(trip_summary(r["preview"]))
            print(f'\nTell George which trip and exactly what you want to change, and ask for his yes. If he says yes, run: tripit adopt-confirm {r["code"]}  (code valid {r["expiresInMinutes"]:.0f} minutes)')
        elif a.cmd == "adopt-confirm":
            r = call("POST", "/adopt/confirm", {"code": a.code}, opener)
            print(f'you may now change trip {r["id"]}')
        elif a.cmd == "delete-confirm":
            r = call("POST", "/delete/confirm", {"code": a.code}, opener)
            print(f'deleted {r["kind"]} {r["id"]}')
        else:
            r = call("GET", f"/changes?limit={a.limit}", opener=opener)["changes"]
            print("\n".join(f'{c["at"][:16]} {c["verb"]} {c["kind"]} {c.get("label") or c.get("id")}' for c in r) or "No changes recorded.")
    except BridgeError as e:
        print(f"tripit: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
