#!/usr/bin/env python3
"""Publish web pages for George.

Private (default): the page is copied into the shared pages folder that the home server shows at https://pages.home/<name>/
(reachable only from the home network).
Public: `public NAME` previews, then `public NAME --confirm CODE` (after George says yes) uploads it to Netlify.
Netlify's token is injected by the OneCLI gateway; this script never sees it.
"""
import argparse, hashlib, io, json, os, re, secrets, subprocess, sys, time, zipfile

PAGES = os.environ.get("PUBLISH_DIR", "/workspace/projects/.nanoclaw-data/pages")
PRIVATE_BASE = os.environ.get("PUBLISH_PRIVATE_BASE", "https://pages.home")
NETLIFY = "https://api.netlify.com/api/v1"
MAX_BYTES = 5 * 1024 * 1024
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
CODE_TTL = 30 * 60
OK_EXT = {".html", ".htm", ".css", ".js", ".json", ".txt", ".md", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff2"}


class PublishError(Exception):
    pass


def slug(name):
    n = name.strip().lower().replace("_", "-").replace(" ", "-")
    if not NAME_RE.match(n):
        raise PublishError("page names are 2-41 characters: letters, digits and dashes (for example 'tasmania-trip')")
    return n


def meta_path(root):
    return os.path.join(root, ".publish.json")


def load_meta(root):
    try:
        with open(meta_path(root)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"pages": {}, "codes": {}}


def save_meta(root, meta):
    os.makedirs(root, exist_ok=True)
    tmp = meta_path(root) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(meta, f, indent=1)
    os.replace(tmp, meta_path(root))


def collect(src):
    """(relative path -> bytes) for a file or folder; a lone file becomes index.html."""
    files = {}
    if os.path.isfile(src):
        with open(src, "rb") as f:
            files["index.html"] = f.read()
    elif os.path.isdir(src):
        for base, _dirs, names in os.walk(src):
            for n in names:
                p = os.path.join(base, n)
                rel = os.path.relpath(p, src).replace(os.sep, "/")
                if n.startswith(".") or os.path.splitext(n)[1].lower() not in OK_EXT:
                    raise PublishError(f"not allowed in a published page: {rel} (allowed: {', '.join(sorted(OK_EXT))})")
                if os.path.islink(p):
                    raise PublishError(f"links are not allowed: {rel}")
                with open(p, "rb") as f:
                    files[rel] = f.read()
    else:
        raise PublishError(f"not found: {src}")
    if "index.html" not in files:
        raise PublishError("the page needs an index.html")
    if sum(len(v) for v in files.values()) > MAX_BYTES:
        raise PublishError("the page is bigger than 5 MB")
    return files


def put(root, name, src, who):
    name = slug(name)
    files = collect(src)
    meta = load_meta(root)
    entry = meta["pages"].get(name)
    if entry and entry.get("by") != who and who != "george":
        raise PublishError(f"'{name}' was published by {entry['by']}; pick another name")
    dest = os.path.join(root, name)
    tmp = dest + ".new"
    for base in (tmp,):
        os.makedirs(base, exist_ok=True)
    for rel, data in files.items():
        p = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    if os.path.isdir(dest):
        old = dest + ".old"
        os.replace(dest, old)
        os.replace(tmp, dest)
        subprocess.run(["rm", "-rf", old])
    else:
        os.replace(tmp, dest)
    meta["pages"].setdefault(name, {"by": who})
    meta["pages"][name].update(updated=int(time.time()), files=len(files), bytes=sum(len(v) for v in files.values()))
    save_meta(root, meta)
    return {"name": name, "url": f"{PRIVATE_BASE}/{name}/", "public": bool(meta["pages"][name].get("public_url")),
            "note": "private: only reachable from the home network"}


def remove(root, name, who):
    name = slug(name)
    meta = load_meta(root)
    entry = meta["pages"].get(name)
    if not entry:
        raise PublishError(f"no published page called '{name}'")
    if entry.get("public_url"):
        raise PublishError("it is also public: run `unpublish` first")
    subprocess.run(["rm", "-rf", os.path.join(root, name)])
    del meta["pages"][name]
    save_meta(root, meta)
    return {"removed": name}


def listing(root):
    meta = load_meta(root)
    return [{"name": n, "by": e.get("by"), "private_url": f"{PRIVATE_BASE}/{n}/", "public_url": e.get("public_url")}
            for n, e in sorted(meta["pages"].items())]


# ------------------------------------------------------------------ public
SENSITIVE = [("email address", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
             ("phone number", re.compile(r"(?<!\d)(?:\+?61|0)[\s-]?\d(?:[\s-]?\d){8}(?!\d)")),
             ("long number (account/card?)", re.compile(r"(?<![\w.])\d{9,}(?![\w.])")),
             ("secret-looking key", re.compile(r"(?i)(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S{6,}"))]


def scan(files):
    found = {}
    for rel, data in files.items():
        if os.path.splitext(rel)[1].lower() in (".html", ".htm", ".js", ".json", ".txt", ".md", ".css", ".svg"):
            text = data.decode("utf-8", "replace")
            for label, rx in SENSITIVE:
                for m in rx.findall(text):
                    found.setdefault(label, set()).add(m if len(m) < 40 else m[:37] + "...")
    return {k: sorted(v)[:5] for k, v in found.items()}


def make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, data in sorted(files.items()):
            z.writestr(rel, data)
    return buf.getvalue()


def http(method, url, body=None, ctype="application/json"):
    cmd = ["curl", "-sS", "-m", "90", "-X", method, "-w", "\n%{http_code}", url]
    if body is not None:
        cmd += ["-H", f"Content-Type: {ctype}", "--data-binary", "@-"]
    r = subprocess.run(cmd, input=body, capture_output=True)
    if r.returncode != 0:
        raise PublishError(f"network error ({r.stderr.decode()[:120].strip() or r.returncode})")
    out, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
    if not code.startswith("2"):
        raise PublishError(f"Netlify HTTP {code}: {out[:160]}")
    return json.loads(out) if out.strip() else {}


def public_request(root, name, now=None):
    name = slug(name)
    meta = load_meta(root)
    if name not in meta["pages"]:
        raise PublishError(f"publish it privately first: no page called '{name}'")
    files = collect(os.path.join(root, name))
    code = secrets.token_hex(3)
    now = now or time.time()
    meta["codes"] = {c: v for c, v in meta.get("codes", {}).items() if v["exp"] > now}
    digest = hashlib.sha256(make_zip(files)).hexdigest()
    meta["codes"][code] = {"name": name, "exp": now + CODE_TTL, "digest": digest}
    save_meta(root, meta)
    return {"name": name, "code": code, "files": sorted(files), "bytes": sum(len(v) for v in files.values()),
            "possibly_sensitive": scan(files),
            "next": "Show George the page contents and anything listed under possibly_sensitive, say it will be visible to anyone "
                    "with the link, and ask. Only if he says yes: publish public NAME --confirm CODE (valid 30 min, only for this exact content)."}


def public_confirm(root, name, code, now=None, api=http):
    name = slug(name)
    meta = load_meta(root)
    c = meta.get("codes", {}).get(code)
    now = now or time.time()
    if not c or c["name"] != name or c["exp"] < now:
        raise PublishError("that confirmation code is wrong or expired: run `public NAME` again and ask George again")
    files = collect(os.path.join(root, name))
    blob = make_zip(files)
    if hashlib.sha256(blob).hexdigest() != c["digest"]:
        raise PublishError("the page changed after George was asked: run `public NAME` again")
    entry = meta["pages"][name]
    site = entry.get("netlify_id")
    if not site:
        s = api("POST", f"{NETLIFY}/sites", json.dumps({"name": f"gc-{name}-{secrets.token_hex(2)}"}).encode())
        site = entry["netlify_id"] = s["id"]
        entry["public_url"] = s.get("ssl_url") or s.get("url")
    api("POST", f"{NETLIFY}/sites/{site}/deploys", blob, "application/zip")
    del meta["codes"][code]
    entry["public_at"] = int(now)
    save_meta(root, meta)
    log = os.path.join(root, ".publish-log.jsonl")
    with open(log, "a") as f:
        f.write(json.dumps({"at": int(now), "name": name, "url": entry["public_url"], "sha": c["digest"][:12]}) + "\n")
    return {"name": name, "public_url": entry["public_url"], "note": "visible to anyone with the link"}


def unpublish(root, name, api=http):
    name = slug(name)
    meta = load_meta(root)
    entry = meta["pages"].get(name, {})
    if not entry.get("netlify_id"):
        raise PublishError(f"'{name}' is not public")
    api("DELETE", f"{NETLIFY}/sites/{entry['netlify_id']}")
    for k in ("netlify_id", "public_url", "public_at"):
        entry.pop(k, None)
    save_meta(root, meta)
    return {"name": name, "public": False}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as", dest="who", default=os.environ.get("ASSISTANT_NAME", "agent").lower())
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("put", help="publish privately: put NAME FILE_OR_FOLDER"); p.add_argument("name"); p.add_argument("src")
    sub.add_parser("list")
    p = sub.add_parser("remove"); p.add_argument("name")
    p = sub.add_parser("public", help="preview, then with --confirm CODE go public"); p.add_argument("name"); p.add_argument("--confirm")
    p = sub.add_parser("unpublish"); p.add_argument("name")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "put":
            out = put(PAGES, a.name, a.src, a.who)
        elif a.cmd == "list":
            out = listing(PAGES)
        elif a.cmd == "remove":
            out = remove(PAGES, a.name, a.who)
        elif a.cmd == "public":
            out = public_confirm(PAGES, a.name, a.confirm) if a.confirm else public_request(PAGES, a.name)
        else:
            out = unpublish(PAGES, a.name)
    except PublishError as e:
        print(f"publish: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
