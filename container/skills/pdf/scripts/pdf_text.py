#!/usr/bin/env python3
"""Extract text from a PDF: a local file, a URL, or a Gmail attachment. See SKILL.md."""
import argparse
import io
import json
import os
import re
import subprocess
import sys

PDF_SITE = "/workspace/projects/.nanoclaw-tools/pdf/site"
MAX_BYTES = 25_000_000
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"


class PdfError(Exception):
    pass


def curl(args, runner=subprocess.run):
    p = runner(["curl", "-sS", "-L", "--max-time", "90", "--max-filesize", str(MAX_BYTES)] + args, capture_output=True)
    if p.returncode != 0:
        raise PdfError(f"download failed: {p.stderr.decode(errors='replace').strip()[:200] or p.returncode}")
    return p.stdout


def fetch_url(url, runner=subprocess.run):
    if not re.match(r"https?://", url):
        raise PdfError("only http(s) URLs are supported")
    data = curl([url], runner)
    if not data.startswith(b"%PDF"):
        raise PdfError("that URL did not return a PDF (it may be a web page: use WebFetch for pages)")
    return data


def b64(data):
    import base64
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def fetch_gmail(message_id, name, runner=subprocess.run):
    msg = json.loads(curl([f"{GMAIL}/messages/{message_id}?format=full"], runner))
    if "error" in msg:
        raise PdfError(f"Gmail: {msg['error'].get('message', 'error')}")
    found = []

    def walk(part):
        if part.get("filename") and part.get("body", {}).get("attachmentId"):
            found.append((part["filename"], part["body"]["attachmentId"]))
        for p in part.get("parts", []) or []:
            walk(p)

    walk(msg.get("payload", {}))
    pdfs = [f for f in found if f[0].lower().endswith(".pdf")]
    if name:
        pdfs = [f for f in pdfs if name.lower() in f[0].lower()]
    if not pdfs:
        raise PdfError("no PDF attachment on that message" + (f" matching '{name}'" if name else "") + f" (attachments: {[f[0] for f in found]})")
    att = json.loads(curl([f"{GMAIL}/messages/{message_id}/attachments/{pdfs[0][1]}"], runner))
    return b64(att["data"])


def parse_pages(spec, total):
    if not spec:
        return list(range(total))
    out = []
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        lo = int(a) - 1
        hi = int(b or a) - 1
        out += [i for i in range(max(lo, 0), min(hi, total - 1) + 1)]
    return out


def extract(data, pages=None, layout=False, max_chars=20000):
    if os.path.isdir(PDF_SITE) and PDF_SITE not in sys.path:
        sys.path.insert(0, PDF_SITE)
    try:
        from pypdf import PdfReader
    except ImportError:
        raise PdfError("pypdf is not installed: ask George to run container/skills/pdf/setup.sh on the host")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                raise PdfError("the PDF is password protected")
    except PdfError:
        raise
    except Exception as e:  # noqa: BLE001
        raise PdfError(f"not a readable PDF: {type(e).__name__}")
    total = len(reader.pages)
    idx = parse_pages(pages, total)
    chunks, empty = [], 0
    for i in idx:
        try:
            t = reader.pages[i].extract_text(extraction_mode="layout") if layout else reader.pages[i].extract_text()
        except Exception:  # noqa: BLE001
            t = ""
        t = re.sub(r"[ \t]+\n", "\n", t or "").strip()
        if not t:
            empty += 1
        chunks.append(f"--- page {i + 1} of {total} ---\n{t}")
    text = "\n\n".join(chunks)
    notes = []
    if idx and empty == len(idx):
        notes.append("NO TEXT LAYER: this looks like a scanned or image-only PDF. Text extraction cannot read it; open it with the Read tool (it can view PDF pages as images) or ask George for a text version.")
    elif empty:
        notes.append(f"{empty} of {len(idx)} pages had no text (images or scans).")
    if len(text) > max_chars:
        text = text[:max_chars]
        notes.append(f"output cut at {max_chars} characters; use --pages to read the rest.")
    return text, notes


def main(argv=None, runner=subprocess.run):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", nargs="?", help="a file path or an http(s) URL")
    ap.add_argument("--gmail", metavar="MESSAGE_ID", help="read a PDF attachment of this Gmail message instead")
    ap.add_argument("--name", help="with --gmail: part of the attachment's file name")
    ap.add_argument("--pages", help="e.g. 1-3,5 (default: all)")
    ap.add_argument("--layout", action="store_true", help="keep the column layout (better for tables and invoices)")
    ap.add_argument("--max-chars", type=int, default=20000)
    a = ap.parse_args(argv)
    try:
        if a.gmail:
            data = fetch_gmail(a.gmail, a.name, runner)
        elif a.source and re.match(r"https?://", a.source):
            data = fetch_url(a.source, runner)
        elif a.source:
            with open(a.source, "rb") as f:
                data = f.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise PdfError("file is larger than 25 MB")
        else:
            ap.error("give a file path, a URL, or --gmail MESSAGE_ID")
        text, notes = extract(data, a.pages, a.layout, a.max_chars)
    except (PdfError, OSError) as e:
        print(f"pdf-text: {e}", file=sys.stderr)
        return 1
    print(text)
    for n in notes:
        print(f"\n[pdf-text] {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
