"""Shared Notion plumbing: ids, HTTP via curl (OneCLI gateway injects the token), errors."""
import json
import re
import subprocess

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
