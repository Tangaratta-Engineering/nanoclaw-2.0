#!/usr/bin/env python3
"""Build a pre-filled cart link for George's regular online shops. See SKILL.md.

Read-only by design: only GET requests to a store's public product list and its cart link; no logins, no
checkout, no payment. A shop must be set up in <data dir>/<name>.json first, which also fixes the domain
(this tool refuses to talk to any other host).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

DATA = os.environ.get("SHOP_DATA", "/workspace/projects/.nanoclaw-data/shopping")
UA = "Mozilla/5.0 (compatible; NanoClaw cart builder)"


class ShopError(Exception):
    pass


def fetch(url, jar=None, runner=subprocess.run, want_headers=False):
    cmd = ["curl", "-sS", "-m", "40", "-L", "-A", UA, "-w", "\n%{http_code}|%{url_effective}", url]
    if jar:
        cmd[1:1] = ["-b", jar, "-c", jar]
    p = runner(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise ShopError(f"could not reach the shop: {p.stderr.strip()[:150] or p.returncode}")
    body, _, tail = p.stdout.rpartition("\n")
    code, _, final = tail.partition("|")
    return int(code or 0), body, final


def load_shop(name):
    path = os.path.join(DATA, f"{name}.json")
    try:
        with open(path) as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        raise ShopError(f"no shop set up called '{name}' (expected {path})")
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", cfg.get("store", "")):
        raise ShopError("the shop config needs a valid 'store' domain")
    return cfg


def products(cfg, runner=subprocess.run):
    out, page = [], 1
    while page <= 6:
        code, body, _ = fetch(f"https://{cfg['store']}/products.json?limit=250&page={page}", None, runner)
        if code != 200:
            raise ShopError(f"the shop's product list is not available (HTTP {code}); it may not be a Shopify store")
        try:
            batch = json.loads(body)["products"]
        except (ValueError, KeyError):
            raise ShopError("the shop's product list was not in the expected format")
        out += batch
        if len(batch) < 250:
            break
        page += 1
    return out


def resolve(cfg, prods, key):
    """Map a nickname from the config (or 'handle|variant text') to a live product variant."""
    spec = cfg.get("items", {}).get(key)
    if spec is None and "|" in key:
        handle, _, variant = key.partition("|")
        spec = {"handle": handle, "variant": variant}
    if spec is None:
        raise ShopError(f"unknown item '{key}' (known: {', '.join(sorted(cfg.get('items', {}))) or 'none'})")
    prod = next((p for p in prods if p["handle"] == spec["handle"]), None)
    if prod is None:
        raise ShopError(f"'{key}' is no longer sold under '{spec['handle']}': ask George, do not substitute")
    wanted = spec.get("variant", "").lower()
    vs = [v for v in prod["variants"] if wanted in str(v["title"]).lower()] if wanted else prod["variants"]
    if len(vs) != 1:
        raise ShopError(f"'{key}' matches {len(vs)} variants of {prod['title']}: be more specific")
    return prod, vs[0], spec


def parse_items(cfg, pairs):
    """['tissues=3', 'toilet_paper'] -> [(key, qty)]; a bare name uses the usual quantity."""
    out = []
    for p in pairs:
        key, _, q = p.partition("=")
        qty = int(q) if q else int(cfg.get("items", {}).get(key, {}).get("usual_qty", 1))
        if qty < 1 or qty > 20:
            raise ShopError(f"quantity for {key} must be 1-20")
        out.append((key, qty))
    if not out:
        raise ShopError("name at least one item (or use --usual)")
    return out


def build(cfg, wanted, runner=subprocess.run, verify=True):
    prods = products(cfg, runner)
    lines, parts, subtotal, notes = [], [], 0.0, []
    for key, qty in wanted:
        prod, var, spec = resolve(cfg, prods, key)
        if not var.get("available", True):
            raise ShopError(f"{prod['title']} ({var['title']}) is out of stock right now: tell George, do not substitute")
        price = float(var["price"])
        subtotal += price * qty
        label = f"{prod['title']} ({var['title']})"
        lines.append(f"{qty} x {label} ${price:.2f} = ${price * qty:.2f}")
        last = spec.get("last_price")
        if last is not None and abs(float(last) - price) > 0.004:
            notes.append(f"{label}: ${price:.2f} now, was ${float(last):.2f} last time")
        parts.append(f"{var['id']}:{qty}")
    link = f"https://{cfg['store']}/cart/{','.join(parts)}"
    check = ""
    if verify:
        jar = tempfile.mkstemp()[1]
        try:
            code, _, final = fetch(link, jar, runner)
            if code != 200:
                raise ShopError(f"the store rejected the cart link (HTTP {code}); do not send it")
            code, body, _ = fetch(f"https://{cfg['store']}/cart.js", jar, runner)
            cart = json.loads(body)
            got = {i["variant_id"]: i["quantity"] for i in cart.get("items", [])}
            want = {int(p.split(":")[0]): int(p.split(":")[1]) for p in parts}
            if got != want:
                raise ShopError(f"the store's cart did not match what was asked for ({got}); do not send the link")
            check = f"Store check: the live cart holds exactly these items, subtotal ${cart['total_price'] / 100:.2f} {cart.get('currency', '')}."
        finally:
            try:
                os.unlink(jar)
            except OSError:
                pass
    out = [f"Cart for {cfg.get('label', cfg['store'])} (live prices):"] + [f"  {l}" for l in lines]
    out.append(f"Subtotal: ${subtotal:.2f}. Shipping, discounts and GST are shown at checkout.")
    if check:
        out.append(check)
    out += [f"Price change: {n}" for n in notes]
    out += [f"Link: {link}", "Open the link, check the checkout page, and pay there. Nothing has been bought."]
    return "\n".join(out)


def cmd_catalog(a, runner=subprocess.run):
    cfg = load_shop(a.shop)
    lines = []
    for p in products(cfg, runner):
        for v in p["variants"]:
            lines.append(f"{p['handle']} | {v['title']} | ${float(v['price']):.2f} | {'in stock' if v.get('available', True) else 'OUT OF STOCK'}")
    nick = ", ".join(f"{k}={v['handle']}|{v.get('variant', '')}" for k, v in cfg.get("items", {}).items())
    return "\n".join(lines) + f"\n\nNicknames on file: {nick or 'none'}"


def cmd_cart(a, runner=subprocess.run):
    cfg = load_shop(a.shop)
    if a.usual:
        wanted = [(k, int(v.get("usual_qty", 1))) for k, v in cfg.get("items", {}).items() if v.get("in_usual_order", True)]
    else:
        wanted = parse_items(cfg, a.items)
    return build(cfg, wanted, runner, verify=not a.no_verify)


def main(argv=None, runner=subprocess.run):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("catalog"); s.add_argument("shop")
    s = sub.add_parser("cart"); s.add_argument("shop"); s.add_argument("items", nargs="*", help="nickname or nickname=qty, e.g. tissues=3 paper_towels")
    s.add_argument("--usual", action="store_true", help="every item marked in_usual_order, at its usual quantity"); s.add_argument("--no-verify", action="store_true")
    a = ap.parse_args(argv)
    try:
        print({"catalog": cmd_catalog, "cart": cmd_cart}[a.cmd](a, runner))
        return 0
    except (ShopError, ValueError) as e:
        print(f"shop: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
