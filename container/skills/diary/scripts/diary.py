#!/usr/bin/env python3
"""Pain and medication diary CLI. See SKILL.md. Times are Sydney time unless DIARY_TZ is set."""
import argparse
import datetime as dt
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diary_core as c  # noqa: E402


def when(a, ref):
    t, note = c.parse_when(getattr(a, "at", None) or "now", ref)
    return t, note


def cmd_now(a, ref):
    return f"{ref:%A %d %B %Y %H:%M} ({ref:%Z}, {ref.isoformat(timespec='seconds')})"


def cmd_log(a, ref):
    t, note = when(a, ref)
    rec = {"kind": "pain" if a.severity is not None else "note", "at": t.isoformat(timespec="minutes")}
    for k in ("severity", "location", "character", "onset", "duration", "text", "helped", "not_helped", "trigger", "red_flags", "plan"):
        v = getattr(a, k)
        if k == "severity" and v is not None and v == int(v):
            v = int(v)
        if v is not None:
            rec[k] = v
    if a.severity is not None and not 0 <= a.severity <= 10:
        raise ValueError("severity must be 0-10")
    c.append(rec)
    out = f"Logged {rec['kind']} at {c.fmt(t)}" + (f" severity {rec['severity']}/10" if a.severity is not None else "") + f" (id {rec['id']})"
    return out + (f"\nNote: {note}" if note else "")


def report(before, after, meds):
    """Findings the new entry introduced (on itself or on an existing dose it now crowds), breaches first."""
    known = {(f[0], f[2]) for f in c.evaluate(before, meds)}
    fresh = [f for f in c.evaluate(after, meds) if (f[0], f[2]) not in known]
    return [f"{sev.upper()}: {msg}" for sev in ("breach", "warning", "note") for _, _, msg, s in fresh if s == sev]


def cmd_dose(a, ref):
    meds = c.load_meds(a.meds)
    t, note = when(a, ref)
    rec = c.make_dose(a.drug.lower(), meds, mg=a.mg, units=a.units, at=t, ref=ref)
    if a.note:
        rec["text"] = a.note
    before = c.doses(c.load())
    c.append(rec)
    ds = c.doses(c.load())
    lines = report(before, ds, meds)
    head = f"Logged {rec['drug']} {rec['mg']:g} mg at {c.fmt(t)} (id {rec['id']})"
    out = lines + [head] + ([f"Note: {note}"] if note else []) + c.status(ds, meds, ref)
    return "\n".join(out)


def cmd_check(a, ref):
    """What would happen if a dose were taken now (or at --at)? Nothing is recorded."""
    meds = c.load_meds(a.meds)
    t, _ = when(a, ref)
    ds = c.doses(c.load())
    cand = dict(c.make_dose(a.drug.lower(), meds, mg=a.mg, units=a.units, at=t, ref=ref), id="candidate")
    cand["t"] = t
    fs = [f for f in c.evaluate(ds + [cand], meds) if f[0] == "candidate"]
    if any(f[3] == "breach" for f in fs):
        lines = [f"NOT ALLOWED: {m}" for _, _, m, s in fs if s == "breach"]
        nxt = c.next_allowed(a.drug.lower(), meds, ds, ref, mg=cand["mg"])
        lines.append("Earliest allowed: " + (c.fmt(nxt) if nxt else "not within 72 h"))
        return "\n".join(lines)
    return f"OK: {cand['drug']} {cand['mg']:g} mg at {c.fmt(t)} is within the limits on file." + "".join(f"\nNOTE: {m}" for _, _, m, s in fs)


def cmd_status(a, ref):
    meds = c.load_meds(a.meds)
    return "\n".join(c.status(c.doses(c.load()), meds, ref))


def cmd_amend(a, ref):
    recs = {r["id"]: r for r in c.load()}
    if a.id not in recs:
        raise ValueError(f"no entry {a.id}")
    fields = {}
    if a.at:
        fields["at"] = c.parse_when(a.at, ref)[0].isoformat(timespec="minutes")
    for k in ("severity", "mg", "units", "location", "text"):
        v = getattr(a, k)
        if v is not None:
            fields[k] = v
    if a.void:
        fields["voided"] = True
    if not fields:
        raise ValueError("nothing to change")
    c.append({"kind": "amend", "amends": a.id, "fields": fields, "reason": a.reason or ""})
    return f"Amended {a.id}: {fields} (original kept in the file)"


def day_key(r):
    return dt.datetime.fromisoformat(r["at"]).astimezone(c.TZ).date()


def cmd_render(a, ref):
    recs = sorted(c.load(), key=lambda r: r["at"])
    since = ref.date() - dt.timedelta(days=a.days - 1)
    if a.date:
        since, until = dt.date.fromisoformat(a.date), dt.date.fromisoformat(a.date)
    else:
        until = ref.date()
    recs = [r for r in recs if since <= day_key(r) <= until]
    if not recs:
        return "No entries in that range."
    out, cur = [], None
    for r in recs:
        d = day_key(r)
        if d != cur:
            out.append(f"\n## {d:%A %d %B %Y}")
            cur = d
        t = dt.datetime.fromisoformat(r["at"]).astimezone(c.TZ).strftime("%H:%M")
        if r["kind"] == "dose":
            out.append(f"- **{t} — medication:** {r['drug']} {r['mg']:g} mg" + (f" ({r['text']})" if r.get("text") else ""))
        else:
            bits = [f"- **{t} — {'pain' if r['kind'] == 'pain' else 'note'}:**"]
            if r.get("severity") is not None:
                bits.append(f"{r['severity']}/10")
            for k, label in (("location", "location"), ("character", "character"), ("onset", "onset"), ("duration", "duration"), ("text", ""), ("helped", "helped"), ("not_helped", "didn't help"), ("trigger", "trigger"), ("red_flags", "red flags"), ("plan", "plan")):
                if r.get(k):
                    bits.append(f"{label + ': ' if label else ''}{r[k]}")
            out.append(" ".join(bits))
    return "\n".join(out).strip()


def cmd_export(a, ref):
    meds = c.load_meds(a.meds)
    recs = [r for r in c.load() if dt.date.fromisoformat(a.start) <= day_key(r) <= dt.date.fromisoformat(a.end)]
    pains = [r for r in recs if r["kind"] == "pain" and r.get("severity") is not None]
    ds = c.doses(c.load())
    mine = {r["id"] for r in recs}
    lines = [f"Clinician summary {a.start} to {a.end}", f"Entries: {len(recs)}; pain entries: {len(pains)}"]
    days = {}
    for r in pains:
        days.setdefault(day_key(r), []).append(r["severity"])
    for d in sorted(days):
        lines.append(f"- {d:%a %d %b}: max {max(days[d])}/10 ({len(days[d])} entries)")
    totals = {}
    for d in ds:
        if d["id"] in mine:
            totals[d["drug"]] = totals.get(d["drug"], 0) + d["mg"]
    lines.append("Medication totals: " + ("; ".join(f"{k} {v:g} mg" for k, v in sorted(totals.items())) or "none logged"))
    breaches = [f for f in c.evaluate(ds, meds) if f[3] == "breach" and f[0] in mine]
    lines.append("Limit breaches: " + ("none" if not breaches else ""))
    lines += [f"- {m}" for _, _, m, _ in breaches]
    return "\n".join(lines)


def build():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", help="ISO time to treat as 'now' (e.g. the time George's message arrived)")
    ap.add_argument("--meds", help="path to meds.json (default: <data dir>/meds.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("now")
    s = sub.add_parser("log")
    s.add_argument("--at"); s.add_argument("--severity", type=float)
    for k in ("location", "character", "onset", "duration", "text", "helped", "not-helped", "trigger", "red-flags", "plan"):
        s.add_argument("--" + k)
    for n in ("dose", "check"):
        s = sub.add_parser(n)
        s.add_argument("--drug", required=True); s.add_argument("--mg", type=float); s.add_argument("--units", type=float); s.add_argument("--at")
        if n == "dose":
            s.add_argument("--note")
    sub.add_parser("status")
    s = sub.add_parser("amend")
    s.add_argument("id"); s.add_argument("--at"); s.add_argument("--severity", type=float); s.add_argument("--mg", type=float); s.add_argument("--units", type=float)
    s.add_argument("--location"); s.add_argument("--text"); s.add_argument("--void", action="store_true"); s.add_argument("--reason")
    s = sub.add_parser("render")
    s.add_argument("--days", type=int, default=7); s.add_argument("--date")
    s = sub.add_parser("export")
    s.add_argument("--start", required=True); s.add_argument("--end", required=True)
    return ap


COMMANDS = {"now": cmd_now, "log": cmd_log, "dose": cmd_dose, "check": cmd_check, "status": cmd_status, "amend": cmd_amend, "render": cmd_render, "export": cmd_export}


def main(argv=None):
    a = build().parse_args(argv)
    try:
        print(COMMANDS[a.cmd](a, c.now(a.ref)))
        return 0
    except (ValueError, KeyError) as e:
        print(f"diary: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
