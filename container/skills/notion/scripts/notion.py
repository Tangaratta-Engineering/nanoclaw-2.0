#!/usr/bin/env python3
"""View, create and update Notion pages as Markdown. See SKILL.md.

Calls api.notion.com with curl; the OneCLI gateway injects the integration
token, so no credential is ever visible here.
"""
import argparse
import json
import re
import subprocess
import sys

API = "https://api.notion.com"
VERSION = "2026-03-11"
ID_RE = re.compile(r"([0-9a-fA-F]{32})(?![0-9a-fA-F])")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


class NotionError(Exception):
    pass


def page_id(ref):
    """Accept a Notion URL, a bare 32-hex id or a dashed UUID."""
    ref = ref.strip()
    m = UUID_RE.search(ref)
    if m:
        return m.group(0).lower()
    ref = ref.split("?")[0].split("#")[0]
    # URLs end "...Title-<32hex>"
    ids = ID_RE.findall(ref.split("/")[-1].replace("-", "")) or ID_RE.findall(ref.replace("-", ""))
    if not ids:
        raise NotionError(f"cannot find a Notion page id in: {ref}")
    h = ids[-1].lower()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def request(method, path, body=None, runner=subprocess.run):
    cmd = ["curl", "-sS", "--max-time", "60", "-X", method, API + path,
           "-H", f"Notion-Version: {VERSION}", "-H", "Content-Type: application/json",
           "-w", "\n%{http_code}"]
    if body is not None:
        cmd += ["--data-binary", "@-"]
    p = runner(cmd, input=json.dumps(body) if body is not None else None,
               capture_output=True, text=True)
    if p.returncode != 0:
        raise NotionError(f"network error: {p.stderr.strip() or p.returncode}")
    text, _, code = p.stdout.rpartition("\n")
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        raise NotionError(f"HTTP {code}: unreadable response")
    if not code.startswith("2"):
        msg = data.get("message", text[:300])
        hint = ""
        if code in ("401", "403"):
            hint = " (token missing or lacks the capability — ask George to check the Notion integration)"
        elif code == "404":
            hint = " (page not found, or not shared with the integration — George must connect it via the page's ••• → Connections menu)"
        raise NotionError(f"HTTP {code} {data.get('code', '')}: {msg}{hint}")
    return data


def title_of(obj):
    props = obj.get("properties") or {}
    for v in props.values():
        if isinstance(v, dict) and v.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in v.get("title", [])) or "(untitled)"
    t = obj.get("title")
    if isinstance(t, list):
        return "".join(x.get("plain_text", "") for x in t) or "(untitled)"
    return "(untitled)"


def body_text(args):
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    if sys.stdin.isatty():
        raise NotionError("give --file PATH or pipe Markdown on stdin")
    return sys.stdin.read()


def fmt_markdown(r):
    out = r.get("markdown", "")
    notes = []
    if r.get("truncated"):
        notes.append("page too large: output truncated")
    if r.get("unknown_block_ids"):
        notes.append(f"{len(r['unknown_block_ids'])} block(s) could not be loaded (shown as <unknown>)")
    for w in r.get("warnings", []) or []:
        notes.append(f"{w.get('code')}: {w.get('message')}")
    if notes:
        out += "\n\n[notion] " + "; ".join(notes)
    return out


def cmd_search(a, run):
    body = {"query": a.query, "page_size": min(a.limit, 100),
            "filter": {"property": "object", "value": "page"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
    res = request("POST", "/v1/search", body, run).get("results", [])
    if not res:
        return "No pages found. (Pages only appear if shared with the integration.)"
    return "\n".join(f"{title_of(p)} | {p['id']} | {p.get('url', '')} | edited {p.get('last_edited_time', '')[:10]}"
                     for p in res)


def cmd_get(a, run):
    return fmt_markdown(request("GET", f"/v1/pages/{page_id(a.page)}/markdown", None, run))


def cmd_create(a, run):
    md = body_text(a)
    body = {"parent": {"page_id": page_id(a.parent)}, "markdown": md,
            "properties": {"title": {"title": [{"text": {"content": a.title}}]}}}
    try:
        r = request("POST", "/v1/pages", body, run)
    except NotionError as e:
        if "HTTP 400" not in str(e):
            raise
        body.pop("properties")  # fall back: title as a leading heading
        body["markdown"] = f"# {a.title}\n\n{md}"
        r = request("POST", "/v1/pages", body, run)
    return f"Created: {title_of(r)} | {r['id']} | {r.get('url', '')}"


def patch(page, command, run):
    return fmt_markdown(request("PATCH", f"/v1/pages/{page_id(page)}/markdown", command, run))


def cmd_append(a, run):
    cmd = {"type": "insert_content", "insert_content": {"content": body_text(a), "position": {"type": "end"}}}
    patch(a.page, cmd, run)
    return "Appended to the end of the page."


def cmd_edit(a, run):
    cmd = {"type": "update_content", "update_content": {"content_updates": [
        {"old_str": a.old, "new_str": a.new, "replace_all_matches": a.all}]}}
    r = request("PATCH", f"/v1/pages/{page_id(a.page)}/markdown", cmd, run)
    warns = r.get("warnings") or []
    return "Edited." + "".join(f"\n[notion] {w.get('code')}: {w.get('message')}" for w in warns)


def cmd_replace(a, run):
    if not a.yes_overwrite:
        raise NotionError("replace overwrites the whole page; confirm with George, then add --yes-overwrite")
    cmd = {"type": "replace_content", "replace_content": {"new_str": body_text(a)}}
    patch(a.page, cmd, run)
    return "Page content replaced. (Child pages/databases are never deleted by this tool.)"


def build_parser():
    p = argparse.ArgumentParser(prog="notion", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("query", nargs="?", default=""); s.add_argument("--limit", type=int, default=10)
    s = sub.add_parser("get"); s.add_argument("page")
    s = sub.add_parser("create"); s.add_argument("--parent", required=True); s.add_argument("--title", required=True); s.add_argument("--file")
    s = sub.add_parser("append"); s.add_argument("page"); s.add_argument("--file")
    s = sub.add_parser("edit"); s.add_argument("page"); s.add_argument("--old", required=True); s.add_argument("--new", required=True); s.add_argument("--all", action="store_true")
    s = sub.add_parser("replace"); s.add_argument("page"); s.add_argument("--file"); s.add_argument("--yes-overwrite", action="store_true")
    return p


COMMANDS = {"search": cmd_search, "get": cmd_get, "create": cmd_create,
            "append": cmd_append, "edit": cmd_edit, "replace": cmd_replace}


def main(argv=None, run=subprocess.run):
    a = build_parser().parse_args(argv)
    try:
        print(COMMANDS[a.cmd](a, run))
    except NotionError as e:
        print(f"notion: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
