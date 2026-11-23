#!/usr/bin/env python3
"""Woolworths shopping lists for George. See SKILL.md.

Sends a request to the host's Woolworths bridge (a JSON file in the shared queue) and prints the answer.
The bridge works inside George's signed-in browser; this tool never sees a password or session.
"""
import argparse
import json
import os
import re
import secrets
import sys
import time

QUEUE = os.environ.get("WOOLIES_QUEUE", "/workspace/projects/.nanoclaw-data/woolies/queue")
DEFAULT_LIST = os.environ.get("WOOLIES_LIST", "NanoClaw")
TIMEOUT = float(os.environ.get("WOOLIES_TIMEOUT", "70"))


class WooliesError(Exception):
    pass


def ask(req, queue=QUEUE, timeout=TIMEOUT, sleep=time.sleep):
    rid = f"{int(time.time())}-{secrets.token_hex(4)}"
    inbox = os.path.join(queue, "in", rid + ".json")
    outbox = os.path.join(queue, "out", rid + ".json")
    if not os.path.isdir(os.path.join(queue, "in")):
        raise WooliesError("the Woolworths bridge isn't set up on the server (no queue folder)")
    tmp = inbox + ".tmp"
    with open(tmp, "w") as f:
        json.dump(req, f)
    os.chmod(tmp, 0o666)
    os.rename(tmp, inbox)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(outbox):
            with open(outbox) as f:
                res = json.load(f)
            os.remove(outbox)
            if not res.get("ok"):
                raise WooliesError(res.get("error", "unknown error"))
            return res["data"]
        sleep(0.5)
    try:
        os.remove(inbox)
    except OSError:
        pass
    raise WooliesError("no answer from the Woolworths bridge (is it running on the server? tell George)")


def money(v):
    return f"${v:.2f}" if isinstance(v, (int, float)) else "n/a"


def fmt_item(p):
    tags = []
    if p.get("boughtBefore"):
        tags.append("bought before")
    if p.get("special"):
        tags.append("on special")
    if not p.get("available", True):
        tags.append("UNAVAILABLE")
    return f"{p['stockcode']} | {p['name']} | {p.get('size') or ''} | {money(p.get('price'))}" + (f" | {p['cup']}" if p.get("cup") else "") + (f" | {', '.join(tags)}" if tags else "")


def parse_item(s):
    code, _, qty = s.partition("=")
    try:
        return {"stockcode": int(code), "qty": int(qty) if qty else 1}
    except ValueError:
        raise WooliesError(f"'{s}' isn't STOCKCODE or STOCKCODE=QTY")


MAX_OWN_STOCKCODE = 99999999  # longer codes are Marketplace items (third-party sellers); the bridge refuses them too


def own_stockcode(code):
    if not isinstance(code, int) or code < 1 or code > MAX_OWN_STOCKCODE:
        raise WooliesError(f"'{code}' isn't a Woolworths stockcode (up to 8 digits; Marketplace items are not supported)")
    return code


# ---- ingredient / allergen checking -------------------------------------------------------------
# Word groups for --avoid. A term that is not a key here is matched as the literal word itself.
GROUPS = {
    "dairy": ["dairy", "milk", "milkfat", "whey", "casein", "caseinate", "lactose", "lactoglobulin", "lactalbumin", "butter",
              "buttermilk", "butterfat", "cream", "cheese", "curd", "yoghurt", "yogurt", "ghee", "custard"],
    "egg": ["egg", "albumen", "albumin", "ovalbumin", "ovomucoid", "lysozyme", "meringue"],
    "gluten": ["gluten", "wheat", "barley", "rye", "oat", "spelt", "kamut", "triticale", "semolina", "couscous", "durum", "malt", "farro", "bulgur"],
    "peanut": ["peanut", "groundnut", "arachis"],
    "treenut": ["nut", "almond", "cashew", "hazelnut", "walnut", "pecan", "pistachio", "macadamia", "brazil nut", "pine nut", "chestnut",
                "praline", "marzipan", "tree nut"],
    "soy": ["soy", "soya", "soybean", "edamame", "tofu", "tempeh", "miso"],
    "sesame": ["sesame", "tahini"],
    "fish": ["fish", "anchovy", "anchovies", "salmon", "tuna", "cod", "barramundi"],
    "shellfish": ["shellfish", "crustacean", "prawn", "shrimp", "crab", "lobster", "crayfish", "krill", "mollusc", "mollusk", "oyster",
                  "mussel", "scallop", "squid", "clam"],
}
GROUPS["nuts"] = GROUPS["treenut"] + GROUPS["peanut"]  # "nut-free" in practice means no peanuts either
ALIASES = {"milk": "dairy", "lactose": "dairy", "egg": "egg", "eggs": "egg", "wheat": "gluten", "nut": "nuts", "nuts": "nuts",
           "treenut": "treenut", "treenuts": "treenut", "peanuts": "peanut", "soya": "soy", "crustacean": "shellfish",
           "crustaceans": "shellfish", "molluscs": "shellfish"}

# Phrases that contain a trigger word but are not that allergen. Only applied to the group named, so for example
# "soy milk" is hidden from a dairy check but still found by a soy check. "X free" statements are never a mention.
EXCLUSIONS = {
    "dairy": ["cocoa butter", "peanut butter", "nut butter", "almond butter", "cashew butter", "shea butter", "coconut cream",
              "coconut milk", "almond milk", "soy milk", "soya milk", "oat milk", "rice milk", "cream of tartar", "milk thistle",
              "dairy free", "lactose free", "milk free", "no dairy", "non dairy", "non-dairy"],
    "egg": ["egg free", "eggplant", "no egg"],
    "gluten": ["gluten free", "wheat free", "no gluten", "oat milk"],
    "peanut": ["peanut free", "nut free", "no peanut"],
    "treenut": ["nut free", "tree nut free", "no nuts", "peanut butter", "butternut", "water chestnut", "water chestnuts"],
    "soy": ["soy free", "soya free", "no soy"],
    "sesame": ["sesame free"],
    "fish": ["fish free", "no fish", "fish free"],
    "shellfish": ["shellfish free", "no shellfish"],
}
EXCLUSIONS["nuts"] = EXCLUSIONS["treenut"] + [e for e in EXCLUSIONS["peanut"] if e not in EXCLUSIONS["treenut"]]
# Text after these markers is a "may contain" statement rather than an ingredient.
MAY_RE = re.compile(r"\b(may\s+contain|may\s+be\s+present|contains?\s+traces|traces\s+of|produced\s+in\s+a|made\s+(?:in|on)\s+(?:a|shared)|manufactured\s+(?:in|on)\s+(?:a|shared))", re.I)


def _word(term, tolerant=True):
    """Regex for one whole word or phrase. The site's ingredient text has stray spaces inside words ("conta ining"),
    so longer words may have one optional space between any two letters. Spaces in a phrase match any run of spaces."""
    parts = []
    for w in re.split(r"[\s-]+", term.strip().lower()):
        letters = [re.escape(c) for c in w]
        parts.append((r"\s?".join(letters) if tolerant and len(w) > 3 else "".join(letters)))
    return r"\b" + r"[\s-]+".join(parts) + r"(?:e?s)?\b"


def _canon(term):
    t = re.sub(r"[\s_-]+", "", term.strip().lower())
    return ALIASES.get(t, t)


def expand_terms(avoid):
    """[(user term, group key or None, [words])] for the comma list given to --avoid."""
    out = []
    for raw in avoid.split(","):
        raw = raw.strip()
        if not raw:
            continue
        key = _canon(raw)
        if key in GROUPS:
            out.append((raw, key, GROUPS[key]))
        else:
            out.append((raw, None, [raw.lower()]))
    if not out:
        raise WooliesError("--avoid needs at least one term, e.g. --avoid dairy,egg")
    return out


def find_matches(text, terms):
    """Matches of the avoid terms in text: [{'term', 'word', 'fragment'}], at most one per (term, word)."""
    if not text:
        return []
    hits = []
    for raw, key, words in terms:
        masked = text
        for phrase in EXCLUSIONS.get(key, []):
            masked = re.sub(_word(phrase), lambda m: "#" * len(m.group(0)), masked, flags=re.I)
        for word in words:
            m = re.search(_word(word), masked, re.I)
            if m:
                a, b = max(0, m.start() - 30), min(len(text), m.end() + 30)
                frag = ("..." if a else "") + text[a:b].strip() + ("..." if b < len(text) else "")
                hits.append({"term": raw, "word": text[m.start():m.end()], "fragment": frag})
    return hits


def check_product(p, terms):
    """Verdict for one product from the `ingredients` op: ('clear'|'blocked'|'unknown', [reasons])."""
    if p.get("error"):
        return "unknown", [f"couldn't read the product page ({p['error']})"]
    ing = p.get("ingredients") or ""
    split = MAY_RE.search(ing)
    main, maybe = (ing[:split.start()], ing[split.start():]) if split else (ing, "")
    reasons = []
    for where, text, may in (("ingredients", main, False), ("declared allergens", p.get("allergensContain"), False),
                             ("'may contain' statement", " ".join(x for x in (maybe, p.get("mayContain")) if x), True)):
        for h in find_matches(text, terms):
            reasons.append(f"{'MAY CONTAIN ' if may else 'contains '}'{h['word']}' (avoiding {h['term']}) in {where}: \"{h['fragment']}\"")
    if reasons:
        return "blocked", reasons
    if not ing:
        return "unknown", ["no ingredient list on the site, so it can't be verified"]
    return "clear", []


def fmt_ingredients(p):
    if p.get("error"):
        return f"{p['stockcode']}: ERROR {p['error']}"
    lines = [f"{p['stockcode']} | {p.get('name') or ''} | {p.get('size') or ''}"]
    lines.append(f"  ingredients: {p['ingredients']}" if p.get("ingredients") else "  ingredients: NOT AVAILABLE")
    lines.append(f"  declared allergens (contains): {p.get('allergensContain') or 'none listed'}")
    lines.append(f"  may be present: {p.get('mayContain') or 'none listed'}")
    if p.get("dietary"):
        lines.append("  dietary/lifestyle claims (the site's labels): " + ", ".join(p["dietary"]))
    if p.get("freeFrom"):
        lines.append("  'free from' claims (the site's labels, NOT proof): " + p["freeFrom"])
    return "\n".join(lines)


def _run(argv, ask=ask):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="is the server's Woolworths login working?")
    s = sub.add_parser("usual", help="search what George has bought before (best way to find his usual brand and size)")
    s.add_argument("query"); s.add_argument("-n", type=int, default=6)
    s = sub.add_parser("search", help="search all Woolworths products")
    s.add_argument("query"); s.add_argument("-n", type=int, default=6)
    sub.add_parser("lists", help="George's Woolworths lists")
    s = sub.add_parser("show", help="what is on a list")
    s.add_argument("--list", default=DEFAULT_LIST)
    s = sub.add_parser("add", help="ADD products (STOCKCODE or STOCKCODE=QTY) to a list: the quantity is added to what is already there; creates the list if missing")
    s.add_argument("--list", default=DEFAULT_LIST); s.add_argument("items", nargs="+")
    s.add_argument("--avoid", help="comma list of things this must NOT contain, e.g. dairy,egg,gluten,nuts,peanut,soy,sesame,fish,shellfish "
                   "(or any word): the ingredients are checked first and products that match are NOT added")
    s.add_argument("--allow-unknown", action="store_true", help="with --avoid: still add products whose ingredient list the site doesn't show")
    s = sub.add_parser("ingredients", help="ingredients, declared allergens and claims for products (STOCKCODE ...)")
    s.add_argument("stockcodes", nargs="+")
    s = sub.add_parser("set", help="make the list hold exactly this quantity of each product (STOCKCODE=QTY)")
    s.add_argument("--list", default=DEFAULT_LIST); s.add_argument("items", nargs="+")
    s = sub.add_parser("remove", help="take products (STOCKCODE ...) off the NanoClaw list")
    s.add_argument("items", nargs="+")
    s = sub.add_parser("clear", help="empty the NanoClaw list (needs --yes, i.e. George asked for it)")
    s.add_argument("--yes", action="store_true", help="George has asked for the list to be cleared")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "ingredients":
            codes = [own_stockcode(parse_item(c)["stockcode"]) for c in a.stockcodes]
            return "\n".join(fmt_ingredients(p) for p in ask({"op": "ingredients", "stockcodes": codes})["items"])
        if a.cmd == "status":
            d = ask({"op": "status"})
            return "Signed in to Woolworths." if d["signedIn"] else "NOT signed in: George needs to sign in to the server's browser again."
        if a.cmd in ("usual", "search"):
            op = "history" if a.cmd == "usual" else "search"
            d = ask({"op": op, "query": a.query, "limit": a.n})
            if not d["items"]:
                hidden = d.get("marketplaceHidden") or 0
                if hidden and op == "search":
                    return f"No matches in Woolworths' own range ({hidden} Marketplace item(s) hidden: George does not buy from third-party sellers)."
                return "No matches." if op == "search" else "Nothing like that in his purchase history. Try `search`."
            head = "From what George has bought before:" if op == "history" else "Woolworths search results:"
            hidden = d.get("marketplaceHidden") or 0
            note = f"\n({hidden} Marketplace item(s) hidden: George does not buy from third-party sellers)" if hidden else ""
            return head + "\n" + "\n".join(fmt_item(p) for p in d["items"]) + note
        if a.cmd == "lists":
            d = ask({"op": "lists"})
            return "\n".join(f"{l['name']} ({l['count']} items)" for l in d["lists"])
        if a.cmd == "show":
            try:
                d = ask({"op": "show", "list": a.list})
            except WooliesError as e:
                if a.list == DEFAULT_LIST and "no list called" in str(e):
                    return f"The '{a.list}' list doesn't exist yet; it is created the first time something is added."
                raise
            return f"{d['list']}: {d['total']} items\n" + "\n".join(f"x{p.get('qty', 1)} | " + fmt_item(p) for p in d["items"])
        if a.cmd == "remove":
            d = ask({"op": "remove", "list": DEFAULT_LIST, "items": [{"stockcode": parse_item(i)["stockcode"]} for i in a.items]})
            out = f"Removed from the Woolworths list '{d['list']}': " + (", ".join(map(str, d["removed"])) or "nothing")
            if d["notOnList"]:
                out += "\nWasn't on the list: " + ", ".join(map(str, d["notOnList"]))
            return out
        if a.cmd == "clear":
            if not a.yes:
                raise WooliesError("clear empties the whole list: only run it with --yes after George has asked you to clear or empty it")
            d = ask({"op": "clear", "list": DEFAULT_LIST, "confirm": True})
            return f"Cleared the Woolworths list '{d['list']}': removed {len(d['removed'])} item(s)."
        if a.cmd == "add" and a.avoid:
            return add_checked(a, ask)
        if a.cmd in ("add", "set"):
            d = ask({"op": a.cmd, "list": a.list, "create": a.list == DEFAULT_LIST, "items": [parse_item(i) for i in a.items]})
            lines = []
            for r in d.get("results", []):
                label = f"{r['stockcode']} {r.get('name') or ''}".strip()
                lines.append(f"On the Woolworths list '{d['list']}': x{r['quantity']} {label}" if r.get("quantity") else f"NOT confirmed on the list yet: {label}")
            out = "\n".join(lines) or f"Done on '{d['list']}'"
            if d["failed"]:
                out += "\nFAILED: " + ", ".join(f"{x['stockcode']} (HTTP {x['status']})" for x in d["failed"])
            return out
    except WooliesError as e:
        print(f"woolies: {e}", file=sys.stderr)
        raise SystemExit(1)


def run_with_status(argv, ask=ask):
    """(text, exit status): add --avoid exits 1 when it withheld something; everything else is 0."""
    r = _run(argv, ask)
    return r if isinstance(r, tuple) else (r, 0)


def run(argv, ask=ask):
    return run_with_status(argv, ask)[0]


def add_checked(a, ask):
    """add --avoid: check each product's ingredients first; add only the clear ones. Exit status 1 if any was withheld."""
    terms = expand_terms(a.avoid)
    items = [parse_item(i) for i in a.items]
    for i in items:
        own_stockcode(i["stockcode"])
    data = ask({"op": "ingredients", "stockcodes": list(dict.fromkeys(i["stockcode"] for i in items))})["items"]
    info = {p["stockcode"]: p for p in data}
    ok, lines, withheld = [], [], 0
    for i in items:
        p = info.get(i["stockcode"]) or {"stockcode": i["stockcode"], "error": "no data returned"}
        label = f"{p['stockcode']} {p.get('name') or ''}".strip()
        verdict, reasons = check_product(p, terms)
        if verdict == "unknown" and a.allow_unknown:
            lines.append(f"Adding {label} WITHOUT a check (--allow-unknown): " + "; ".join(reasons))
            ok.append(i)
        elif verdict == "clear":
            ok.append(i)
        else:
            withheld += 1
            head = "NOT ADDED (can't verify)" if verdict == "unknown" else "NOT ADDED"
            lines.append(f"{head}: {label}: " + "; ".join(reasons))
    out = list(lines)
    if ok:
        d = ask({"op": "add", "list": a.list, "create": a.list == DEFAULT_LIST, "items": ok})
        for r in d.get("results", []):
            label = f"{r['stockcode']} {r.get('name') or ''}".strip()
            out.append(f"On the Woolworths list '{d['list']}': x{r['quantity']} {label}" if r.get("quantity") else f"NOT confirmed on the list yet: {label}")
        if d["failed"]:
            out.append("FAILED: " + ", ".join(f"{x['stockcode']} (HTTP {x['status']})" for x in d["failed"]))
    else:
        out.append("Nothing was added.")
    out.append(f"Checked against: {a.avoid}. Site data can be out of date: George should still read the label on the pack.")
    return "\n".join(out), (1 if withheld else 0)


if __name__ == "__main__":
    text, code = run_with_status(sys.argv[1:])
    print(text)
    sys.exit(code)
