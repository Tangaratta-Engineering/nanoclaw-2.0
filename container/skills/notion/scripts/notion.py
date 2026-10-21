#!/usr/bin/env python3
"""View, create and update Notion pages as Markdown. See SKILL.md.

Calls api.notion.com with curl; the OneCLI gateway injects the integration
token, so no credential is ever visible here.
"""
import argparse
import subprocess
import sys

from notion_core import NotionError, page_id, request, title_of  # noqa: F401
import notion_db


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


def cmd_move(a, run):
    request("POST", f"/v1/pages/{page_id(a.page)}/move", {"parent": {"type": "page_id", "page_id": page_id(a.to)}}, run)
    return "Moved. (The API can only move a page under another page, not to the workspace top level.)"


def build_parser():
    p = argparse.ArgumentParser(prog="notion", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("query", nargs="?", default=""); s.add_argument("--limit", type=int, default=10)
    s = sub.add_parser("get"); s.add_argument("page")
    s = sub.add_parser("create"); s.add_argument("--parent", required=True); s.add_argument("--title", required=True); s.add_argument("--file")
    s = sub.add_parser("append"); s.add_argument("page"); s.add_argument("--file")
    s = sub.add_parser("edit"); s.add_argument("page"); s.add_argument("--old", required=True); s.add_argument("--new", required=True); s.add_argument("--all", action="store_true")
    s = sub.add_parser("replace"); s.add_argument("page"); s.add_argument("--file"); s.add_argument("--yes-overwrite", action="store_true")
    s = sub.add_parser("move"); s.add_argument("page"); s.add_argument("--to", required=True, help="new parent page")
    s = sub.add_parser("db-create", help="create a database (table) under a page")
    s.add_argument("--parent", required=True); s.add_argument("--title", required=True)
    s.add_argument("--columns", required=True, help='e.g. "Item:title,Person:select(George|Emily),Packed:checkbox,Due:date,Qty:number,Notes:text"')
    s = sub.add_parser("db-schema"); s.add_argument("db")
    s = sub.add_parser("db-add-row"); s.add_argument("db"); s.add_argument("--set", action="append", default=[], metavar="Column=value"); s.add_argument("--body-file")
    s = sub.add_parser("db-add-rows"); s.add_argument("db"); s.add_argument("--file", required=True, help="JSON array of {column: value} objects")
    s = sub.add_parser("db-update-row"); s.add_argument("row"); s.add_argument("--set", action="append", default=[], metavar="Column=value")
    s = sub.add_parser("db-query"); s.add_argument("db"); s.add_argument("--where", action="append", metavar="Column=value|Column~text|Column<date")
    s.add_argument("--sort", help="Column:asc|desc"); s.add_argument("--limit", type=int, default=50)
    s = sub.add_parser("db-alter"); s.add_argument("db"); s.add_argument("--add", action="append"); s.add_argument("--rename", action="append", metavar="Old=New")
    s.add_argument("--remove", action="append"); s.add_argument("--yes-remove", action="store_true")
    return p


COMMANDS = {"search": cmd_search, "get": cmd_get, "create": cmd_create,
            "append": cmd_append, "edit": cmd_edit, "replace": cmd_replace, "move": cmd_move,
            "db-create": notion_db.db_create, "db-schema": notion_db.db_schema, "db-add-row": notion_db.db_add_row,
            "db-add-rows": notion_db.db_add_rows, "db-update-row": notion_db.db_update_row,
            "db-query": notion_db.db_query, "db-alter": notion_db.db_alter}


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
