#!/usr/bin/env python3
"""Compact "what was I working on?" pack from this agent's own recent conversations.

Reads the agent's Claude transcripts (every session of this agent group shares one
directory), and prints the most recent messages from George, this agent's replies and
the notable tool calls/errors, newest sessions first. Used to answer a CONTEXT REQUEST
from the other agent.

Usage: recent-context [--hours 24] [--max-chars 9000] [--grep WORD ...] [--dir PATH]
"""
import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import sys

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

DEFAULT_DIR = "/home/node/.claude/projects/-workspace-agent"
DEFAULT_TZ = "Australia/Sydney"  # George's timezone; the container may run in UTC

MSG_RE = re.compile(r"<message\b([^>]*)>(.*?)</message>", re.S)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
TO_RE = re.compile(r'<message\s+to="([^"]+)"\s*>(.*?)</message>', re.S)
ERR_HINT = re.compile(r"error|traceback|exception|failed|not found|denied|exit code|unauthor", re.I)


def clip(text, n):
    text = re.sub(r"\s+", " ", html.unescape(text or "")).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def local_tz(name=None):
    """Timezone used for printing: --tz, TZ env, else Sydney. Falls back to the system zone."""
    for n in (name, os.environ.get("TZ"), DEFAULT_TZ):
        if n and ZoneInfo:
            try:
                return ZoneInfo(n)
            except Exception:
                continue
    return None


def parse_ts(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def block_text(content):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


def events_from_transcript(path):
    """Yield (timestamp, kind, text) in order: user / agent / tool / error."""
    pending = {}
    with open(path, errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ts = parse_ts(r.get("timestamp", ""))
            m = r.get("message") or {}
            content = m.get("content")
            if r.get("type") == "user":
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            res = b.get("content")
                            txt = res if isinstance(res, str) else block_text(res or [])
                            name = pending.pop(b.get("tool_use_id"), "tool")
                            if txt:
                                kind = "error" if ERR_HINT.search(txt[:600]) else "tool"
                                yield ts, kind, f"{name} -> {clip(txt, 320 if kind == 'error' else 110)}"
                body = block_text(content)
                for attrs, text in MSG_RE.findall(body):
                    a = dict(ATTR_RE.findall(attrs))
                    src = a.get("from") or "?"
                    who = a.get("sender") or src  # messages from another agent carry no sender name
                    yield ts, "user", f"{who} (via {src}): {clip(text, 700)}"
            elif r.get("type") == "assistant" and isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text", "").strip():
                        t = b["text"]
                        sent = TO_RE.findall(t)
                        if sent:
                            for to, body in sent:
                                yield ts, "agent", f"said to {to}: {clip(body, 800)}"
                        else:
                            yield ts, "agent", f"said: {clip(t, 800)}"
                    elif b.get("type") == "tool_use":
                        inp = b.get("input") or {}
                        arg = inp.get("command") or inp.get("path") or inp.get("prompt") or inp.get("description") or json.dumps(inp)
                        pending[b.get("id")] = f"{b.get('name')} {clip(str(arg), 110)}"


def main():
    ap = argparse.ArgumentParser(description="Recent-conversation context pack for a handover.")
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--max-chars", type=int, default=9000)
    ap.add_argument("--grep", nargs="*", default=[], help="only keep events mentioning any of these words")
    ap.add_argument("--tz", help="timezone for printed times (default: TZ env, else Australia/Sydney)")
    ap.add_argument("--dir", default=os.environ.get("RECENT_CONTEXT_DIR", DEFAULT_DIR))
    args = ap.parse_args()

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.hours)
    files = sorted(glob.glob(os.path.join(args.dir, "*.jsonl")), key=os.path.getmtime, reverse=True)
    if not files:
        print(f"(no conversation records found in {args.dir})")
        return 0
    words = [w.lower() for w in args.grep]
    chunks, used = [], 0
    for path in files:
        if dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc) < cutoff:
            continue
        evs = [(ts, k, t) for ts, k, t in events_from_transcript(path) if ts is None or ts >= cutoff]
        if words:
            evs = [e for e in evs if any(w in e[2].lower() for w in words)]
        if not evs:
            continue
        tz = local_tz(args.tz)

        def when(ts, fmt):
            return ts.astimezone(tz).strftime(fmt) if ts else "?"

        lines = [f"## conversation {os.path.basename(path)[:8]} (last activity {when(evs[-1][0], '%a %d %b %H:%M')})"]
        day = None
        for ts, kind, text in evs:
            d = when(ts, "%a %d %b")
            if d != day:
                lines.append(f"--- {d} ---")
                day = d
            stamp = when(ts, "%H:%M")
            tag = {"user": "", "agent": "ME ", "tool": "· tool ", "error": "! ERROR "}[kind]
            lines.append(f"[{stamp}] {tag}{text}")
        block = "\n".join(lines)
        # keep the newest part of a long conversation, within the overall budget
        room = args.max_chars - used
        if room < 400:
            break
        if len(block) > room:
            block = lines[0] + "\n…(earlier turns omitted)…\n" + block[-(room - len(lines[0]) - 40):]
        chunks.append(block)
        used += len(block)
    print("\n\n".join(chunks) if chunks else f"(nothing in the last {args.hours:g} hours)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
