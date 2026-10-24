"""Gmail plumbing for the inbox-triage skill: HTTP via curl (OneCLI gateway injects the OAuth token),
message parsing and text extraction. Email content is untrusted data."""
import base64
import html
import json
import re
import subprocess
from html.parser import HTMLParser

API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailError(Exception):
    pass


def call(method, path, body=None, runner=subprocess.run):
    cmd = ["curl", "-sS", "--max-time", "60", "-X", method, API + path, "-H", "Content-Type: application/json", "-w", "\n%{http_code}"]
    if body is not None:
        cmd += ["--data-binary", "@-"]
    p = runner(cmd, input=json.dumps(body) if body is not None else None, capture_output=True, text=True)
    if p.returncode != 0:
        raise GmailError(f"network error: {p.stderr.strip() or p.returncode}")
    text, _, code = p.stdout.rpartition("\n")
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        raise GmailError(f"HTTP {code}: unreadable response")
    if not code.startswith("2"):
        raise GmailError(f"HTTP {code}: {data.get('error', {}).get('message', text[:200])}")
    return data


def b64(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class _Text(HTMLParser):
    SKIP = {"script", "style", "head"}
    BREAK = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "table"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BREAK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(s):
    p = _Text()
    p.feed(s)
    return clean("".join(p.out))


def clean(text):
    text = html.unescape(text).replace("\r", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def header(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def walk(part):
    yield part
    for p in part.get("parts", []) or []:
        yield from walk(p)


# Some systems (booking engines, receipts) send a placeholder as the plain-text part and the real
# content only as HTML. Treat these as "no usable plain text".
_PLACEHOLDER = re.compile(r"^(no content|this (email|message) (requires|contains) html.*|view (this|in) (email )?(in )?(your )?browser.*|your email (client|app) (does not|doesn't) support html.*|please enable html.*)$", re.I | re.S)


def _usable(plain, htm):
    """Prefer the plain-text part, unless it is a placeholder or far shorter than the HTML text."""
    if not plain:
        return False
    if _PLACEHOLDER.match(plain.strip().rstrip(".")):
        return False
    return not (htm and len(plain) < 60 and len(htm) > 4 * len(plain))


def body_text(msg, limit=1500):
    plain, htm = "", ""
    for p in walk(msg.get("payload", {})):
        data = (p.get("body") or {}).get("data")
        if not data or p.get("filename"):
            continue
        try:
            txt = b64(data).decode("utf-8", "replace")
        except Exception:
            continue
        if p.get("mimeType") == "text/plain" and not plain:
            plain = clean(txt)
        elif p.get("mimeType") == "text/html" and not htm:
            htm = html_to_text(txt)
    text = plain if _usable(plain, htm) else (htm or plain)
    text = re.sub(r"\n>.*", "", text)  # quoted reply lines
    return text[:limit]


def attachments(msg):
    out = []
    for p in walk(msg.get("payload", {})):
        fn = p.get("filename")
        aid = (p.get("body") or {}).get("attachmentId")
        if fn and aid:
            out.append({"filename": fn, "mime": p.get("mimeType", ""), "size": p["body"].get("size", 0), "attachment_id": aid})
    return out
