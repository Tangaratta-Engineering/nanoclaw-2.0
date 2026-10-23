"""Pain/medication diary core: time parsing, append-only storage, medication limit rules.

The arithmetic that matters for safety (rolling 24 h totals, minimum intervals, next allowed time) lives
here, in code, so the agent never has to work it out. Limits come from a private `meds.json`; this module
contains no personal data. Not medical advice: it enforces whatever limits the clinician set.
"""
import datetime as dt
import json
import os
import re
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("DIARY_TZ", "Australia/Sydney"))
DATA = os.environ.get("DIARY_DATA", "/workspace/agent/diary")


def now(ref=None):
    return dt.datetime.fromisoformat(ref).astimezone(TZ) if ref else dt.datetime.now(TZ)


def fmt(t):
    return t.astimezone(TZ).strftime("%a %d %b %H:%M")


# ---- time ---------------------------------------------------------------------------------------

_UNITS = {"m": 1, "min": 1, "mins": 1, "minute": 1, "minutes": 1, "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60}


def _clock(text):
    """'2pm', '2:30 pm', '14:05', '0715' -> (hour, minute) or None."""
    m = re.fullmatch(r"~?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text.strip())
    if m and (m.group(2) or m.group(3) or len(m.group(1)) >= 2):
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if 0 <= h < 24 and 0 <= mi < 60:
            return h, mi
    m = re.fullmatch(r"(\d{2})(\d{2})", text.strip())
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return int(m.group(1)), int(m.group(2))
    return None


def parse_when(text, ref):
    """Return (datetime, assumption or None). Raises ValueError for anything it cannot resolve exactly."""
    s = (text or "").strip().lower().replace(".", "")
    if s in ("", "now", "just now", "just then", "right now", "a moment ago", "just before", "just earlier"):
        return ref, None
    m = re.fullmatch(r"(?:about |around |~)?(\d+(?:\.\d+)?|an?|half an?|a couple of|a couple)\s*(m|mins?|minutes?|h|hrs?|hours?)\s*ago", s)
    if m:
        q = m.group(1)
        n = {"a": 1, "an": 1, "half a": 0.5, "half an": 0.5, "a couple of": 2, "a couple": 2}.get(q)
        n = n if n is not None else float(q)
        return ref - dt.timedelta(minutes=n * _UNITS[m.group(2)]), None
    m = re.fullmatch(r"(?:(today|yesterday|last night|this morning)\s+(?:at\s+)?)?(.+)", s)
    if m:
        day_word, rest = m.group(1), m.group(2)
        c = _clock(rest.replace("at ", ""))
        if c:
            base = ref.replace(hour=c[0], minute=c[1], second=0, microsecond=0)
            if day_word == "yesterday":
                return base - dt.timedelta(days=1), None
            if day_word == "last night":
                return (base if base <= ref else base - dt.timedelta(days=1)), "took 'last night' to be the most recent past occurrence of that time"
            if base > ref + dt.timedelta(minutes=5):
                return base - dt.timedelta(days=1), "time was later than now, so assumed yesterday"
            return base, None
    try:
        t = dt.datetime.fromisoformat(text.strip())
        return (t if t.tzinfo else t.replace(tzinfo=TZ)), None
    except ValueError:
        raise ValueError(f"cannot resolve the time '{text}': ask George for a clock time or how long ago")


# ---- storage (append-only) ----------------------------------------------------------------------

def _path():
    return os.path.join(DATA, "entries.jsonl")


def append(rec):
    os.makedirs(DATA, exist_ok=True)
    rec.setdefault("id", "e-%d" % int(dt.datetime.now().timestamp() * 1000))
    rec.setdefault("logged", dt.datetime.now(TZ).isoformat(timespec="seconds"))
    with open(_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load():
    """Effective records: amendments applied, voided records dropped; nothing is ever deleted from the file."""
    try:
        with open(_path(), encoding="utf-8") as f:
            raw = [json.loads(line) for line in f if line.strip()]
    except OSError:
        return []
    by_id = {}
    for r in raw:
        if r.get("kind") == "amend":
            t = by_id.get(r["amends"])
            if t is not None:
                t.update(r.get("fields", {}))
                t.setdefault("history", []).append({"amended": r["logged"], "fields": r.get("fields", {})})
        else:
            by_id[r["id"]] = dict(r)
    return [r for r in by_id.values() if not r.get("voided")]


def doses(recs):
    out = []
    for r in recs:
        if r.get("kind") == "dose":
            r = dict(r)
            r["t"] = dt.datetime.fromisoformat(r["at"])
            out.append(r)
    return sorted(out, key=lambda r: r["t"])


# ---- medication rules ---------------------------------------------------------------------------

def load_meds(path=None):
    p = path or os.path.join(DATA, "meds.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)["drugs"]
    except (OSError, KeyError, ValueError):
        raise ValueError(f"medication limits not found or invalid at {p}")


def _contrib(d, meds):
    """Which limit groups a dose counts toward and how much: {group: mg}. A drug counts toward itself."""
    cfg = meds.get(d["drug"], {})
    out = {d["drug"]: d["mg"]}
    for group, per_unit in (cfg.get("counts_as") or {}).items():
        out[group] = out.get(group, 0) + per_unit * d.get("units", 1)
    return out


def _total(group, window_end, ds, meds, hours=24):
    start = window_end - dt.timedelta(hours=hours)
    return sum(_contrib(d, meds).get(group, 0) for d in ds if start < d["t"] <= window_end)


def evaluate(ds, meds):
    """Check every dose against every rule given all doses. Returns [(dose id, drug, message, severity)]."""
    findings = []
    ds = sorted(ds, key=lambda r: r["t"])  # stable: among equal times, list order decides who came "first"
    for idx, d in enumerate(ds):
        cfg = meds.get(d["drug"], {})
        if cfg.get("stopped"):
            findings.append((d["id"], d["drug"], f"{d['drug']} is marked stopped" + (f" ({cfg['stopped_note']})" if cfg.get("stopped_note") else ""), "note"))
        if cfg.get("per_dose_max_mg") is not None and d["mg"] > cfg["per_dose_max_mg"] + 1e-9:
            findings.append((d["id"], d["drug"], f"{d['mg']:g} mg is over the {cfg['per_dose_max_mg']:g} mg per-dose maximum", "breach"))
        for group, mg in _contrib(d, meds).items():
            gcfg = meds.get(group, {})
            gap = gcfg.get("min_interval_h")
            if gap:
                prev = [p for j, p in enumerate(ds) if j < idx and group in _contrib(p, meds)]
                if prev and d["t"] - prev[-1]["t"] < dt.timedelta(hours=gap) - dt.timedelta(seconds=30):
                    findings.append((d["id"], d["drug"], f"{group}: only {(d['t'] - prev[-1]['t']).total_seconds() / 3600:.1f} h after the previous dose at {fmt(prev[-1]['t'])} (minimum {gap:g} h)", "breach"))
            cap = gcfg.get("max_24h_mg")
            if cap is not None:
                tot = _total(group, d["t"], ds, meds)
                if tot > cap + 1e-9:
                    findings.append((d["id"], d["drug"], f"{group}: {tot:g} mg in the 24 h to {fmt(d['t'])} is over the {cap:g} mg limit", "breach"))
                elif gcfg.get("soft_24h_mg") and tot > gcfg["soft_24h_mg"] + 1e-9:
                    findings.append((d["id"], d["drug"], f"{group}: {tot:g} mg in 24 h is above the {gcfg['soft_24h_mg']:g} mg comfort level", "warning"))
        cls = cfg.get("class")
        if cls == "nsaid" or cfg.get("forbidden_with"):
            for o in ds:
                if o is d or o["drug"] == d["drug"] or o["t"].astimezone(TZ).date() != d["t"].astimezone(TZ).date():
                    continue
                ocfg = meds.get(o["drug"], {})
                if o["drug"] in (cfg.get("forbidden_with") or []) or d["drug"] in (ocfg.get("forbidden_with") or []) or (cls == "nsaid" and ocfg.get("class") == "nsaid"):
                    findings.append((d["id"], d["drug"], f"{d['drug']} and {o['drug']} taken on the same day ({d['t'].astimezone(TZ):%a %d %b})", "breach"))
    cap_units = {}
    for d in ds:
        cfg = meds.get(d["drug"], {})
        if cfg.get("max_24h_units") is not None:
            n = sum(x.get("units", 1) for x in ds if d["t"] - dt.timedelta(hours=24) < x["t"] <= d["t"] and x["drug"] == d["drug"])
            if n > cfg["max_24h_units"]:
                findings.append((d["id"], d["drug"], f"{n} {d['drug']} units in the 24 h to {fmt(d['t'])} (maximum {cfg['max_24h_units']})", "breach"))
    seen, out = set(), []
    for f in findings:
        if (f[0], f[2]) not in seen:
            seen.add((f[0], f[2]))
            out.append(f)
    return out


def make_dose(drug, meds, mg=None, units=None, at=None, ref=None):
    cfg = meds.get(drug)
    if cfg is None:
        raise ValueError(f"unknown medication '{drug}' (known: {', '.join(sorted(meds))}); ask George for the strength, do not guess")
    if mg is None and units is None:
        units = 1
    if mg is None:
        if cfg.get("unit_mg") is None:
            raise ValueError(f"{drug} has no tablet strength on file: ask George for the dose in mg")
        mg = cfg["unit_mg"] * units
    elif units is None:
        units = (mg / cfg["unit_mg"]) if cfg.get("unit_mg") else 1
    return {"kind": "dose", "drug": drug, "mg": mg, "units": units, "at": (at or ref).isoformat(timespec="minutes")}


def next_allowed(drug, meds, ds, ref, mg=None):
    """Earliest time (5-minute steps, up to 72 h ahead) a normal dose of `drug` would pass every rule."""
    cfg = meds.get(drug, {})
    if cfg.get("stopped"):
        return None
    base = make_dose(drug, meds, mg=mg, at=ref, ref=ref)
    step = dt.timedelta(minutes=5)
    t = ref.replace(second=0, microsecond=0)
    for _ in range(72 * 12):
        cand = dict(base, id="candidate", at=t.isoformat(), t=t)
        if not [f for f in evaluate(ds + [cand], meds) if f[3] == "breach" and f[0] == "candidate"]:
            return t
        t += step
    return None


def status(ds, meds, ref):
    lines = [f"Now: {fmt(ref)} ({ref:%Z})"]
    groups = [g for g, c in meds.items() if c.get("max_24h_mg") is not None]
    for g in groups:
        tot = _total(g, ref, ds, meds)
        lines.append(f"24 h to now: {g} {tot:g} / {meds[g]['max_24h_mg']:g} mg")
    for drug, cfg in meds.items():
        if cfg.get("stopped") or cfg.get("hide_next"):
            continue
        t = next_allowed(drug, meds, ds, ref)
        lines.append(f"Next {drug}: " + ("now" if t is not None and t <= ref + dt.timedelta(minutes=5) else fmt(t) if t else "not within 72 h"))
    return lines
