#!/usr/bin/env python3
"""storymap — manage George's Life Story Map (map.json) from the command line.

The board at https://roadmapping.netlify.app reads map.json from the GitHub repo
firsthalfhero/roadmapping. Every change this tool writes is a commit to `main`;
Netlify redeploys automatically and the board updates within about a minute.

Remote mode (default): reads and writes map.json through the GitHub API.
    In the agent container the OneCLI gateway injects the GitHub credential (vault secret for
    api.github.com, scoped to the roadmapping repo); no token is stored in the container. Outside
    the gateway, set env GITHUB_TOKEN (fine-grained token, roadmapping repo, Contents: read & write).
Local mode: --file path/to/map.json edits a file on disk instead (no commit).

Standard library only. Python 3.8+.
Run `storymap.py --help` or `storymap.py <command> --help` for usage.
"""
import argparse, base64, datetime, json, os, secrets, subprocess, sys

REPO = os.environ.get("STORYMAP_REPO", "firsthalfhero/roadmapping")
BRANCH = os.environ.get("STORYMAP_BRANCH", "main")
PATH = "map.json"
API = "https://api.github.com"

TYPE_ALIASES = {"result": "yellow", "yellow": "yellow", "unknown": "pink", "pink": "pink", "red": "pink", "research": "pink"}
TYPE_LABEL = {"yellow": "RESULT", "pink": "UNKNOWN"}


class Fail(Exception):
    pass


# ---------- storage ----------

def _req(method, url, token, body=None, runner=subprocess.run):
    """HTTP via curl so the OneCLI gateway can inject the credential. Returns (status, json)."""
    cmd = ["curl", "-sS", "--max-time", "30", "-X", method, url,
           "-H", "Accept: application/vnd.github+json", "-H", "X-GitHub-Api-Version: 2022-11-28",
           "-H", "User-Agent: storymap-cli", "-H", "Content-Type: application/json",
           "-w", "\n%{http_code}"]
    if token:
        cmd += ["-H", "Authorization: Bearer " + token]
    if body is not None:
        cmd += ["--data-binary", "@-"]
    p = runner(cmd, input=json.dumps(body) if body is not None else None, capture_output=True, text=True)
    if p.returncode != 0:
        raise Fail("network error: " + (p.stderr.strip() or str(p.returncode)))
    text, _, code = p.stdout.rpartition("\n")
    try:
        return int(code), json.loads(text or "{}")
    except ValueError:
        raise Fail("unexpected response from GitHub: " + p.stdout[:200])


class Store:
    def __init__(self, file=None):
        self.file = file
        self.sha = None
        if not file:
            self.token = os.environ.get("GITHUB_TOKEN") or os.environ.get("STORYMAP_TOKEN")  # optional: gateway injects it

    def load(self):
        if self.file:
            with open(self.file, encoding="utf-8") as f:
                return json.load(f)
        code, body = _req("GET", f"{API}/repos/{REPO}/contents/{PATH}?ref={BRANCH}", self.token)
        if code != 200:
            raise Fail(f"Could not read {PATH} from {REPO} (HTTP {code}): {body.get('message', '')}"
                       + (" (401/403/404 usually means the GitHub credential is missing or not scoped to this repo)" if code in (401, 403, 404) else ""))
        self.sha = body["sha"]
        return json.loads(base64.b64decode(body["content"]).decode("utf-8"))

    def save(self, data, message):
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if self.file:
            with open(self.file, "w", encoding="utf-8") as f:
                f.write(text)
            return "saved to " + self.file
        code, body = _req("PUT", f"{API}/repos/{REPO}/contents/{PATH}", self.token, {
            "message": message,
            "content": base64.b64encode(text.encode("utf-8")).decode(),
            "sha": self.sha,
            "branch": BRANCH,
        })
        if code == 409:
            raise Conflict()
        if code not in (200, 201):
            raise Fail(f"Could not save {PATH} (HTTP {code}): {body.get('message', '')}")
        return "committed " + body["commit"]["sha"][:7]


class Conflict(Exception):
    pass


# ---------- model helpers ----------
#
# Hierarchy (left to right by theme, top to bottom by detail):
#   category (green)           -> "super epic" when it holds any epics
#     epic (green, optional)   -> {"kind": "epic", "outcomes": [...]}, sits on its own row
#       outcome (blue)         -> {"items": [...]}, may be completed (done + doneAt)
#         card (yellow / pink) -> {"type", "text", "done"}
# A category's "outcomes" list holds outcomes and epics side by side; epics hold outcomes only.

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def an(w):
    return ("an " if w[:1].lower() in "aeiou" else "a ") + w


def is_epic(n):
    return n.get("kind") == "epic"


def is_completed(o):
    return not is_epic(o) and o.get("done") is True


def has_epics(g):
    return any(is_epic(n) for n in g["outcomes"])


def iter_outcomes(g):
    """Yield (epic_or_None, outcome) for every blue outcome in a category."""
    for n in g["outcomes"]:
        if is_epic(n):
            for o in n["outcomes"]:
                yield n, o
        else:
            yield None, n


def migrate(data):
    """Convert old green sub-heading columns (kind "green" with blue item cards) into epics.
    Returns True if anything changed."""
    changed = False
    for g in data.get("groups", []):
        for n in g.get("outcomes", []):
            if n.get("kind") == "green":
                items = n.pop("items", [])
                outs = []
                for it in items:
                    if it.get("type") == "blue":
                        o = {"id": it["id"], "title": it.get("text", ""), "items": []}
                        if it.get("done"):
                            o["done"] = True
                            o["doneAt"] = now_iso()
                        outs.append(o)
                rest = [it for it in items if it.get("type") != "blue"]
                if rest:
                    outs.append({"id": n["id"] + "-cards", "title": n.get("title", "Cards"), "items": rest})
                n["kind"] = "epic"
                n.pop("done", None); n.pop("doneAt", None)
                n["outcomes"] = outs
                changed = True
    return changed


def new_id(prefix, data):
    used = {x["id"] for x in walk(data)}
    while True:
        i = prefix + secrets.token_hex(3)
        if i not in used:
            return i


def walk(data):
    """Yield every node (category, epic, outcome, card) with an 'id'."""
    for g in data["groups"]:
        yield g
        for n in g["outcomes"]:
            yield n
            for o in (n["outcomes"] if is_epic(n) else [n]):
                if o is not n:
                    yield o
                for c in o["items"]:
                    yield c


def locate(data, id_):
    """Return (level, node, parent_list, parent_node) for an id.
    level is one of: category, epic, outcome, card."""
    for g in data["groups"]:
        if g["id"] == id_:
            return "category", g, data["groups"], None
        for n in g["outcomes"]:
            if is_epic(n):
                if n["id"] == id_:
                    return "epic", n, g["outcomes"], g
                pool, owner = n["outcomes"], n
            else:
                pool, owner = [n], g
            for o in pool:
                if o["id"] == id_:
                    return "outcome", o, (n["outcomes"] if is_epic(n) else g["outcomes"]), owner
                for c in o["items"]:
                    if c["id"] == id_:
                        return "card", c, o["items"], o
    raise Fail(f"No category, epic, outcome or card with id '{id_}'. Run `show` to see ids.")


def where(data, id_):
    """Human path for an outcome or epic: 'Category > Epic'."""
    for g in data["groups"]:
        for n in g["outcomes"]:
            if n["id"] == id_:
                return g["title"]
            if is_epic(n) and any(o["id"] == id_ for o in n["outcomes"]):
                return f"{g['title']} > {n['title']}"
    return ""


def insert(lst, item, index):
    if index is None or index >= len(lst):
        lst.append(item)
    else:
        lst.insert(max(0, index), item)


def norm_type(t):
    try:
        return TYPE_ALIASES[t.lower()]
    except KeyError:
        raise Fail(f"Card type must be 'result' (yellow) or 'unknown' (pink), not '{t}'. "
                   "Blue outcomes are added with add-outcome, green epics with add-epic.")


def clean_text(t):
    t = (t or "").strip()
    if not t:
        raise Fail("Text can't be empty.")
    if len(t) > 280:
        raise Fail(f"Text is {len(t)} characters; keep cards under 280 (they're index cards).")
    return t


def validate(data):
    problems = []
    if not isinstance(data, dict) or not isinstance(data.get("groups"), list):
        return ["Top level must be an object with a 'groups' list."]
    seen = set()

    def chk_id(n, where_):
        i = n.get("id")
        if not isinstance(i, str) or not i:
            problems.append(f"{where_}: missing id")
        elif i in seen:
            problems.append(f"{where_}: duplicate id '{i}'")
        else:
            seen.add(i)

    def chk_outcome(o, w2):
        chk_id(o, w2)
        if not str(o.get("title", "")).strip():
            problems.append(f"{w2}: empty title")
        if "kind" in o and o["kind"] != "blue":
            problems.append(f"{w2}: an outcome can't have kind '{o['kind']}'")
        if "done" in o and not isinstance(o["done"], bool):
            problems.append(f"{w2}: done must be true/false")
        if not isinstance(o.get("items"), list):
            problems.append(f"{w2}: 'items' must be a list"); return
        for ci, c in enumerate(o["items"]):
            w3 = f"{w2} > card #{ci+1}"
            chk_id(c, w3)
            if c.get("type") not in ("yellow", "pink"):
                problems.append(f"{w3}: type must be 'yellow' or 'pink'")
            if not str(c.get("text", "")).strip():
                problems.append(f"{w3}: empty text")
            if not isinstance(c.get("done", False), bool):
                problems.append(f"{w3}: done must be true/false")

    for gi, g in enumerate(data["groups"]):
        w = f"category #{gi+1}"
        chk_id(g, w)
        if not str(g.get("title", "")).strip():
            problems.append(f"{w}: empty title")
        if not isinstance(g.get("outcomes"), list):
            problems.append(f"{w}: 'outcomes' must be a list"); continue
        for oi, n in enumerate(g["outcomes"]):
            if is_epic(n):
                we = f"{w} > epic #{oi+1}"
                chk_id(n, we)
                if not str(n.get("title", "")).strip():
                    problems.append(f"{we}: empty title")
                if "items" in n:
                    problems.append(f"{we}: epics hold outcomes, not cards")
                if n.get("done"):
                    problems.append(f"{we}: epics can't be completed; complete their outcomes")
                if not isinstance(n.get("outcomes"), list):
                    problems.append(f"{we}: 'outcomes' must be a list"); continue
                for ei, o in enumerate(n["outcomes"]):
                    if is_epic(o):
                        problems.append(f"{we} > #{ei+1}: epics can't contain epics"); continue
                    chk_outcome(o, f"{we} > outcome #{ei+1}")
            else:
                chk_outcome(n, f"{w} > outcome #{oi+1}")
    return problems


def _outcome_lines(o, show_done, label, indent, suffix=""):
    items = o["items"]
    open_n = sum(1 for c in items if not c.get("done"))
    out = [f"{indent}[{label} {o['id']}] {o['title']}  ({open_n} open / {len(items)} cards){suffix}"]
    for c in items:
        if c.get("done") and not show_done:
            continue
        box = "[x]" if c.get("done") else "[ ]"
        text = c["text"].replace("\n", " / ")
        out.append(f"{indent}  {box} {TYPE_LABEL[c['type']]:<7} {c['id']}  {text}")
    return out


def render_text(data, show_done=True):
    out = []
    upd = data.get("updated")
    if upd:
        out.append(f"Last saved: {upd}")
    completed = []
    for g in data["groups"]:
        label = "SUPER EPIC" if has_epics(g) else "CATEGORY"
        out.append(f"\n[{label} {g['id']}] {g['title']}")
        for n in g["outcomes"]:
            if is_epic(n):
                out.append(f"  [EPIC {n['id']}] {n['title']}")
                for o in n["outcomes"]:
                    if is_completed(o):
                        completed.append((f"{g['title']} > {n['title']}", o)); continue
                    out += _outcome_lines(o, show_done, "OUTCOME", "    ")
            elif is_completed(n):
                completed.append((g["title"], n))
            else:
                out += _outcome_lines(n, show_done, "OUTCOME", "  ")
    if completed and show_done:
        completed.sort(key=lambda po: po[1].get("doneAt", ""), reverse=True)
        out.append("\n[COMPLETED ROW] (completed outcomes, newest first; they still belong where they came from)")
        for path, o in completed:
            out += _outcome_lines(o, True, "COMPLETED", "  ", f"  from '{path}', completed {o.get('doneAt', '?')[:10]}")
    elif completed:
        out.append(f"\n({len(completed)} completed outcome(s) hidden; run `show` without --open-only to see them)")
    return "\n".join(out)


# ---------- commands ----------
# Each returns (commit_message or None) after mutating data in place, or prints and returns None.

def cmd_show(data, a):
    if a.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render_text(data, show_done=not a.open_only))


def cmd_find(data, a):
    q = a.text.lower()
    hits = 0
    for g in data["groups"]:
        if q in g["title"].lower():
            print(f"{'SUPER EPIC' if has_epics(g) else 'CATEGORY':<10} {g['id']}  {g['title']}"); hits += 1
        for n in g["outcomes"]:
            if is_epic(n) and q in n["title"].lower():
                print(f"{'EPIC':<10} {n['id']}  {g['title']} > {n['title']}"); hits += 1
        for e, o in iter_outcomes(g):
            path = g["title"] + (f" > {e['title']}" if e else "")
            if q in o["title"].lower():
                print(f"{'OUTCOME':<10} {o['id']}  {path} > {o['title']}" + ("  (completed)" if is_completed(o) else "")); hits += 1
            for c in o["items"]:
                if q in c["text"].lower():
                    print(f"{'CARD':<10} {c['id']}  {path} > {o['title']} > {c['text'].splitlines()[0]}"
                          + ("  (done)" if c.get("done") else "")); hits += 1
    if not hits:
        print("No matches.")


def cmd_validate(data, a):
    probs = validate(data)
    if probs:
        print("INVALID:\n- " + "\n- ".join(probs)); sys.exit(1)
    print("OK")


def cmd_add_category(data, a):
    g = {"id": new_id("g", data), "title": clean_text(a.title), "outcomes": []}
    insert(data["groups"], g, a.index)
    print(f"Added category {g['id']}: {g['title']}")
    return f"Add category: {g['title']}"


def cmd_add_epic(data, a):
    lvl, g, _, _ = locate(data, a.category_id)
    if lvl != "category":
        raise Fail(f"'{a.category_id}' is {an(lvl)}; epics go directly under a category (which then becomes a super epic).")
    e = {"id": new_id("e", data), "title": clean_text(a.title), "kind": "epic", "outcomes": []}
    insert(g["outcomes"], e, a.index)
    print(f"Added epic {e['id']} under '{g['title']}': {e['title']}"
          + ("" if sum(is_epic(n) for n in g["outcomes"]) > 1 else f" ('{g['title']}' is now a super epic)"))
    return f"Add epic: {e['title']}"


def cmd_add_outcome(data, a):
    lvl, parent, _, _ = locate(data, a.parent_id)
    if lvl not in ("category", "epic"):
        raise Fail(f"'{a.parent_id}' is {an(lvl)}; outcomes go under a category or an epic.")
    o = {"id": new_id("o", data), "title": clean_text(a.title), "items": []}
    insert(parent["outcomes"], o, a.index)
    print(f"Added outcome {o['id']} under {lvl} '{parent['title']}': {o['title']}")
    return f"Add outcome: {o['title']}"


def cmd_add_card(data, a):
    lvl, o, _, _ = locate(data, a.outcome_id)
    if lvl != "outcome":
        raise Fail(f"'{a.outcome_id}' is {an(lvl)}; cards go under a blue outcome.")
    c = {"id": new_id("c", data), "type": norm_type(a.type), "text": clean_text(a.text), "done": bool(a.done)}
    insert(o["items"], c, a.index)
    print(f"Added {TYPE_LABEL[c['type']].lower()} card {c['id']} to '{o['title']}': {c['text']}")
    return f"Add {TYPE_LABEL[c['type']].lower()} card to {o['title']}: {c['text'].splitlines()[0]}"


def cmd_edit(data, a):
    lvl, n, _, _ = locate(data, a.id)
    text = clean_text(a.text)
    if lvl == "card":
        old, n["text"] = n["text"], text
        if a.type:
            n["type"] = norm_type(a.type)
    else:
        if a.type:
            raise Fail("--type only applies to cards.")
        old, n["title"] = n["title"], text
    print(f"Edited {lvl} {a.id}: '{old}' -> '{text}'")
    return f"Edit {lvl}: {text.splitlines()[0]}"


def cmd_retype(data, a):
    lvl, n, _, _ = locate(data, a.id)
    if lvl != "card":
        raise Fail("Only cards have a type.")
    n["type"] = norm_type(a.type)
    print(f"Card {a.id} is now {TYPE_LABEL[n['type']].lower()}")
    return f"Change card type: {n['text'].splitlines()[0]}"


def _set_done(data, a, value):
    msgs = []
    for id_ in a.ids:
        lvl, n, _, _ = locate(data, id_)
        if lvl == "outcome":
            label = n["title"]
            if value:
                if not n.get("done"):
                    n["done"] = True
                    n["doneAt"] = now_iso()
                left = [c["text"].splitlines()[0] for c in n["items"] if not c.get("done")]
                print(f"Completed outcome: {label} (moves to the Completed row)")
                if left:
                    print(f"  Note: {len(left)} card(s) under it are still open: " + "; ".join(left))
            else:
                n.pop("done", None); n.pop("doneAt", None)
                print(f"Reopened outcome: {label} (back under '{where(data, id_)}')")
            msgs.append(label)
            continue
        if lvl != "card":
            raise Fail(f"'{id_}' is {an(lvl)}; only cards and blue outcomes can be ticked off.")
        n["done"] = value
        msgs.append(n["text"].splitlines()[0])
        print(("Done: " if value else "Reopened: ") + n["text"].splitlines()[0])
    return ("Done: " if value else "Reopen: ") + "; ".join(msgs)


def cmd_done(data, a):
    return _set_done(data, a, True)


def cmd_undo(data, a):
    return _set_done(data, a, False)


def _outcomes_only(data, a):
    for id_ in a.ids:
        lvl, n, _, _ = locate(data, id_)
        if lvl != "outcome":
            raise Fail(f"'{id_}' is {an(lvl)}; complete/reopen only work on blue outcomes. Use done/undo for cards.")


def cmd_complete(data, a):
    _outcomes_only(data, a)
    return _set_done(data, a, True)


def cmd_reopen(data, a):
    _outcomes_only(data, a)
    return _set_done(data, a, False)


def cmd_move(data, a):
    lvl, n, plist, _ = locate(data, a.id)
    if lvl == "category":
        if a.to:
            raise Fail("Categories only reorder: use --index, not --to.")
        plist.remove(n)
        insert(data["groups"], n, a.index)
        print(f"Moved category '{n['title']}' to position {a.index if a.index is not None else 'end'}")
        return f"Move category: {n['title']}"
    if not a.to:
        dest_list = plist
    else:
        tl, tnode, _, _ = locate(data, a.to)
        allowed = {"card": ("outcome",), "outcome": ("category", "epic"), "epic": ("category",)}[lvl]
        if tl not in allowed:
            raise Fail(f"{an(lvl).capitalize()} can move to {' or '.join(an(x) for x in allowed)}; '{a.to}' is {an(tl)}.")
        dest_list = tnode["items"] if lvl == "card" else tnode["outcomes"]
    plist.remove(n)
    insert(dest_list, n, a.index)
    label = n.get("text", n.get("title", "")).splitlines()[0]
    print(f"Moved {lvl} '{label}'")
    return f"Move {lvl}: {label}"


def cmd_remove(data, a):
    lvl, n, plist, _ = locate(data, a.id)
    children = len(n.get("outcomes", n.get("items", []))) if lvl != "card" else 0
    if children and not a.force:
        raise Fail(f"That {lvl} still has {children} item(s) under it. Move them first, or re-run with --force to delete everything under it.")
    plist.remove(n)
    label = n.get("text", n.get("title", "")).splitlines()[0]
    print(f"Removed {lvl} '{label}'" + (f" and {children} item(s) under it" if children else ""))
    return f"Remove {lvl}: {label}"


def cmd_import(data, a):
    with open(a.path, encoding="utf-8") as f:
        new = json.load(f)
    migrate(new)
    probs = validate(new)
    if probs:
        raise Fail("Import file is invalid:\n- " + "\n- ".join(probs))
    data["groups"] = new["groups"]
    print(f"Imported {len(new['groups'])} categories from {a.path}")
    return "Import board from George's edits"


def cmd_self_update(data, a):
    """In this NanoClaw install the skill is part of the NanoClaw repo, so it is updated there."""
    raise Fail("self-update isn't used in this install: the story-map skill ships with NanoClaw and is updated "
               "by George on the server (a change merged into the NanoClaw repo). Tell George the tool needs updating.")


# ---------- main ----------

def build_parser():
    p = argparse.ArgumentParser(prog="storymap.py", description="Manage George's Life Story Map board (map.json).")
    p.add_argument("--file", help="Edit a local map.json instead of the GitHub copy (no commit).")
    p.add_argument("--message", "-m", help="Override the commit message.")
    p.add_argument("--dry-run", action="store_true", help="Show what would change; save nothing.")
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("show", help="Print the whole board with ids.")
    s.add_argument("--json", action="store_true", help="Print raw JSON.")
    s.add_argument("--open-only", action="store_true", help="Hide cards already done.")
    s.set_defaults(fn=cmd_show, write=False)

    s = sp.add_parser("find", help="Search titles and card text (case-insensitive).")
    s.add_argument("text"); s.set_defaults(fn=cmd_find, write=False)

    s = sp.add_parser("validate", help="Check map.json is well-formed.")
    s.set_defaults(fn=cmd_validate, write=False)

    s = sp.add_parser("add-category", help="Add a green category (top row).")
    s.add_argument("title"); s.add_argument("--index", type=int, help="0-based position (default: end).")
    s.set_defaults(fn=cmd_add_category, write=True)

    s = sp.add_parser("add-epic", help="Add a green epic under a category (the category becomes a super epic).")
    s.add_argument("category_id"); s.add_argument("title")
    s.add_argument("--index", type=int, help="0-based position within the category (default: end).")
    s.set_defaults(fn=cmd_add_epic, write=True)

    s = sp.add_parser("add-outcome", help="Add a blue outcome column under a category or an epic.")
    s.add_argument("parent_id", help="Category id or epic id."); s.add_argument("title")
    s.add_argument("--index", type=int, help="0-based position within the category or epic (default: end).")
    s.set_defaults(fn=cmd_add_outcome, write=True)

    s = sp.add_parser("add-card", help="Add a yellow result or pink unknown card under a blue outcome.")
    s.add_argument("outcome_id"); s.add_argument("type", help="result | unknown"); s.add_argument("text")
    s.add_argument("--index", type=int, help="0-based position in the column (default: bottom).")
    s.add_argument("--done", action="store_true", help="Add it already ticked off.")
    s.set_defaults(fn=cmd_add_card, write=True)

    s = sp.add_parser("edit", help="Change the text of any card, outcome, epic or category.")
    s.add_argument("id"); s.add_argument("text"); s.add_argument("--type", help="Also change a card's type.")
    s.set_defaults(fn=cmd_edit, write=True)

    s = sp.add_parser("retype", help="Switch a card between result and unknown.")
    s.add_argument("id"); s.add_argument("type"); s.set_defaults(fn=cmd_retype, write=True)

    s = sp.add_parser("done", help="Tick off cards (result achieved / unknown answered) or complete blue outcomes (moves them to the Completed row).")
    s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_done, write=True)

    s = sp.add_parser("undo", help="Reopen ticked cards, or move completed outcomes back into their category.")
    s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_undo, write=True)

    s = sp.add_parser("complete", help="Complete one or more blue outcomes (moves them to the Completed row).")
    s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_complete, write=True)

    s = sp.add_parser("reopen", help="Move completed blue outcomes back into their category.")
    s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_reopen, write=True)

    s = sp.add_parser("move", help="Move a card to another outcome, an outcome to a category or epic, an epic to another category, or reorder.")
    s.add_argument("id"); s.add_argument("--to", help="Destination: outcome (for a card), category or epic (for an outcome), category (for an epic). Omit to reorder in place.")
    s.add_argument("--index", type=int, help="0-based position at the destination (default: end).")
    s.set_defaults(fn=cmd_move, write=True)

    s = sp.add_parser("remove", help="Delete a card, outcome, epic or category.")
    s.add_argument("id"); s.add_argument("--force", action="store_true", help="Also delete everything under it.")
    s.set_defaults(fn=cmd_remove, write=True)

    s = sp.add_parser("self-update", help="Download the latest storymap.py and SKILL.md from the repo into this folder.")
    s.add_argument("--to", help="Folder to download into instead of this script's folder (use when the skill folder is read-only).")
    s.set_defaults(fn=cmd_self_update, write=False, no_load=True)

    s = sp.add_parser("import", help="Replace the board with JSON George copied from the page ('Copy / load map').")
    s.add_argument("path"); s.set_defaults(fn=cmd_import, write=True)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        if getattr(a, "no_load", False):
            a.fn(None, a)
            return 0
        store = Store(a.file)
        for attempt in range(3):
            data = store.load()
            migrated = migrate(data)
            msg = a.fn(data, a)
            if not a.write:
                return 0
            probs = validate(data)
            if probs:
                raise Fail("Change would make the board invalid, nothing saved:\n- " + "\n- ".join(probs))
            if a.dry_run:
                print("(dry run: nothing saved)")
                return 0
            data["version"] = 2
            data["updated"] = now_iso()
            # keep key order tidy: version, updated, groups
            data = {"version": 2, "updated": data["updated"], "groups": data["groups"]}
            try:
                result = store.save(data, a.message or ("storymap: " + msg))
                print(result + ("" if a.file else ". The board updates in about a minute."))
                return 0
            except Conflict:
                if attempt == 2:
                    raise Fail("map.json kept changing underneath this edit. Try again.")
                print("map.json changed on GitHub while editing; retrying on the latest version…", file=sys.stderr)
    except Fail as e:
        print("ERROR: " + str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
