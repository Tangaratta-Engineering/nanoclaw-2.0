#!/usr/bin/env python3
"""Search and read George's email properly: real body text (HTML when the plain part is a placeholder),
attachments, and PDF attachment text. See SKILL.md."""
import argparse
import json
import os
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inbox_gmail as g  # noqa: E402

PDF_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pdf", "scripts")


def cmd_search(a, call=g.call):
    q = a.query
    if not any(t in q for t in ("in:", "label:", "is:")):
        q = q + " in:anywhere"  # inbox, archive, sent and labelled mail, not only the inbox
    out, token = [], None
    while len(out) < a.limit:
        path = f"/messages?maxResults={min(50, a.limit)}&q={urllib.parse.quote(q)}&includeSpamTrash={'true' if a.spam else 'false'}" + (f"&pageToken={token}" if token else "")
        r = call("GET", path)
        out += [m["id"] for m in r.get("messages", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    lines = []
    for i in out[: a.limit]:
        m = call("GET", f"/messages/{i}?format=full")
        names = [x["filename"] for x in g.walk(m.get("payload", {})) if x.get("filename")]
        lines.append(f"{i} | {g.header(m, 'date')[:22]} | {g.header(m, 'from')[:45]} | {g.header(m, 'subject')[:80]}" + (f" | attachments: {', '.join(names)}" if names else ""))
    return (f"{len(lines)} messages for: {q}\n" if lines else f"No messages for: {q}. Widen it: fewer words, a sender name, or a date range with after:/before:.\n") + "\n".join(lines)


def cmd_read(a, call=g.call, runner=subprocess.run):
    m = call("GET", f"/messages/{a.id}?format=full")
    lines = [f"From: {g.header(m, 'from')}", f"To: {g.header(m, 'to')}", f"Date: {g.header(m, 'date')}", f"Subject: {g.header(m, 'subject')}", ""]
    body = g.body_text(m, a.max_chars)
    lines.append(body if body.strip() else "(no body text in either the plain or the HTML part)")
    atts = g.attachments(m)
    if atts:
        lines.append("\nAttachments: " + ", ".join(f"{x['filename']} ({x['mime']}, {x['size']} bytes)" for x in atts))
    if a.pdf:
        sys.path.insert(0, PDF_SCRIPTS)
        try:
            import pdf_text
        except ImportError:
            pdf_text = None
        for x in atts:
            if x["filename"].lower().endswith(".pdf"):
                lines.append(f"\n--- text of {x['filename']} ---")
                if pdf_text is None:
                    lines.append("(the pdf skill is not available)")
                    continue
                try:
                    data = pdf_text.fetch_gmail(a.id, x["filename"], runner)
                    text, notes = pdf_text.extract(data, None, True, a.max_chars)
                    lines.append(text)
                    lines += [f"[{n}]" for n in notes]
                except Exception as e:  # noqa: BLE001
                    lines.append(f"(could not read this PDF: {e})")
    elif any(x["filename"].lower().endswith(".pdf") for x in atts):
        lines.append("\nThis email has a PDF attachment: run again with --pdf to read it.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query"); s.add_argument("--limit", type=int, default=20); s.add_argument("--spam", action="store_true", help="include spam and trash")
    s = sub.add_parser("read")
    s.add_argument("id"); s.add_argument("--pdf", action="store_true", help="also print the text of PDF attachments"); s.add_argument("--max-chars", type=int, default=6000)
    a = ap.parse_args(argv)
    try:
        print({"search": cmd_search, "read": cmd_read}[a.cmd](a))
        return 0
    except g.GmailError as e:
        print(f"inbox-mail: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
