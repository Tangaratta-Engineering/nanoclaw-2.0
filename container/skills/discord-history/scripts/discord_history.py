#!/usr/bin/env python3
"""Read and search the message history of the shared Discord channel (#general). See SKILL.md."""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

API = os.environ.get("DISCORD_HISTORY_API", "https://discord.com/api/v10")
CHANNELS = {"general": "1508404737056182339"}   # the only channel this skill reads (the gateway secret is scoped to it too)
TZ = ZoneInfo(os.environ.get("TZ") or "Australia/Sydney")
PAGE = 100
MAX_PAGES_DEFAULT = 20
MAX_CHARS_DEFAULT = 15_000
TEXT_TYPES = {0, 19}   # normal message, reply


class HistoryError(Exception):
    pass


def request(path, opener=urllib.request.urlopen, sleep=time.sleep):
    """GET from Discord. The OneCLI gateway adds the bot token; this script never holds it."""
    for attempt in range(4):
        req = urllib.request.Request(API + path, headers={"User-Agent": "nanoclaw-discord-history (internal)"})
        try:
            with opener(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                try:
                    wait = float(json.loads(e.read() or b"{}").get("retry_after", 1))
                except Exception:
                    wait = 1.0
                sleep(min(wait, 10))
                continue
            if e.code in (401, 403):
                raise HistoryError("Discord refused the request (no bot token was added, or the bot cannot read this channel). "
                                   "Tell George the Discord secret is missing or not assigned in OneCLI")
            raise HistoryError(f"Discord answered HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise HistoryError(f"cannot reach Discord: {getattr(e, 'reason', e)}")
    raise HistoryError("Discord rate limit: try again in a minute")


def parse_since(text, now=None):
    """'3d', '12h', '30m', '2026-11-05' or '2026-11-05T09:00' -> aware UTC datetime."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    m = re.fullmatch(r"(\d+)([dhm])", text.strip())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return now - datetime.timedelta(**{{"d": "days", "h": "hours", "m": "minutes"}[unit]: n})
    try:
        d = datetime.datetime.fromisoformat(text.strip())
    except ValueError:
        raise HistoryError(f"cannot read the time {text!r}: use 3d, 12h, 30m or 2026-11-05")
    return (d if d.tzinfo else d.replace(tzinfo=TZ)).astimezone(datetime.timezone.utc)


def ts(msg):
    return datetime.datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))


def fetch(channel_id, since=None, until=None, max_pages=MAX_PAGES_DEFAULT, opener=urllib.request.urlopen, sleep=time.sleep):
    """Messages newest-first from `until` back to `since`, as far as max_pages allows. Returns (messages, hit_page_limit)."""
    out, before, pages = [], None, 0
    while pages < max_pages:
        path = f"/channels/{channel_id}/messages?limit={PAGE}" + (f"&before={before}" if before else "")
        batch = request(path, opener, sleep)
        pages += 1
        if not batch:
            return out, False
        for m in batch:
            t = ts(m)
            if since and t < since:
                return out, False
            if until and t > until:
                continue
            out.append(m)
        before = batch[-1]["id"]
        if len(batch) < PAGE:
            return out, False
    return out, True


def render(msg):
    when = ts(msg).astimezone(TZ).strftime("%a %d %b %H:%M")
    who = (msg.get("member") or {}).get("nick") or msg["author"].get("global_name") or msg["author"]["username"]
    text = (msg.get("content") or "").strip()
    for e in msg.get("embeds") or []:
        bit = " - ".join(x for x in (e.get("title"), e.get("description")) if x)
        if bit:
            text += ("\n" if text else "") + f"[card] {bit}"
    for a in msg.get("attachments") or []:
        text += ("\n" if text else "") + f"[attachment: {a.get('filename')}]"
    ref = msg.get("referenced_message")
    if ref:
        text = f"(replying to {ref['author']['username']}: \"{(ref.get('content') or '')[:60]}\")\n" + text
    return f"{when} {who}: {text or '(no text)'}"


def keep(msg, who=None):
    if msg.get("type") not in TEXT_TYPES:
        return False
    return not who or who.lower() in {msg["author"]["username"].lower(), (msg["author"].get("global_name") or "").lower()}


def emit(messages, limit_chars, notes=()):
    lines = [render(m) for m in reversed(messages)]   # oldest first, reads like the chat
    text = "\n".join(lines)
    if len(text) > limit_chars:
        text = "...(older messages cut: narrow --since or add --from/--limit)...\n" + text[-limit_chars:]
    return "\n".join([*notes, text]) if messages else "\n".join([*notes, "No messages found."])


def main(argv=None, opener=urllib.request.urlopen, sleep=time.sleep):
    ap = argparse.ArgumentParser(description="Read and search #general history")
    ap.add_argument("--channel", default="general", choices=sorted(CHANNELS))
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("history", help="what was said recently")
    h.add_argument("--since", default="1d")
    h.add_argument("--until")
    h.add_argument("--from", dest="who", help="only this person or agent, e.g. Jimmy")
    h.add_argument("--limit", type=int, default=100, help="most recent N messages")
    h.add_argument("--max-chars", type=int, default=MAX_CHARS_DEFAULT)
    s = sub.add_parser("search", help="find messages containing all the words")
    s.add_argument("query")
    s.add_argument("--since", default="30d")
    s.add_argument("--from", dest="who")
    s.add_argument("--context", type=int, default=0, help="messages to show around each hit")
    s.add_argument("--max-pages", type=int, default=MAX_PAGES_DEFAULT)
    s.add_argument("--max-chars", type=int, default=MAX_CHARS_DEFAULT)
    a = ap.parse_args(argv)
    try:
        cid = CHANNELS[a.channel]
        since = parse_since(a.since)
        if a.cmd == "history":
            msgs, more = fetch(cid, since, parse_since(a.until) if a.until else None, MAX_PAGES_DEFAULT, opener, sleep)
            msgs = [m for m in msgs if keep(m, a.who)][: a.limit]
            note = [f"({len(msgs)} message(s) since {a.since}, times in {TZ.key}{'; more exist further back' if more else ''})"]
            print(emit(msgs, a.max_chars, note))
        else:
            words = [w.lower() for w in re.findall(r"\S+", a.query)]
            msgs, more = fetch(cid, since, None, a.max_pages, opener, sleep)
            text_msgs = [m for m in msgs if keep(m)]
            hit_ids = set()
            picked = []
            for i, m in enumerate(text_msgs):          # newest-first
                hay = render(m).lower()
                if all(w in hay for w in words) and keep(m, a.who):
                    for j in range(max(0, i - a.context), min(len(text_msgs), i + a.context + 1)):
                        if text_msgs[j]["id"] not in hit_ids:
                            hit_ids.add(text_msgs[j]["id"])
                            picked.append(text_msgs[j])
            picked.sort(key=lambda m: m["id"], reverse=True)
            note = [f'({len([m for m in picked if all(w in render(m).lower() for w in words)])} message(s) match "{a.query}" in the last {a.since}'
                    f"{'; searched only part of that range, narrow --since' if more else ''})"]
            print(emit(picked, a.max_chars, note))
    except HistoryError as e:
        print(f"discord-history: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
