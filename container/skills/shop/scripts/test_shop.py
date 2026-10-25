import json, os, re, sys, tempfile, unittest
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import shop as s

PRODUCTS = {"products": [
    {"title": "Tissues", "handle": "tissues-12", "variants": [{"id": 111, "title": "12 Boxes", "price": "27.00", "available": True}]},
    {"title": "Paper Towels", "handle": "towels-6", "variants": [{"id": 222, "title": "6 Rolls", "price": "21.00", "available": True}]},
    {"title": "Toilet Paper", "handle": "tp", "variants": [{"id": 331, "title": "48 Rolls", "price": "69.50", "available": True}, {"id": 332, "title": "24 Rolls", "price": "42.50", "available": True}]},
    {"title": "Gone", "handle": "gone", "variants": [{"id": 441, "title": "1", "price": "5.00", "available": False}]},
]}
CFG = {"store": "shop.example.com", "label": "Example", "items": {
    "tissues": {"handle": "tissues-12", "variant": "12 Boxes", "usual_qty": 3, "last_price": 26.0},
    "towels": {"handle": "towels-6", "usual_qty": 2, "in_usual_order": False},
    "toilet_paper": {"handle": "tp", "variant": "48", "usual_qty": 1},
    "tp_any": {"handle": "tp", "in_usual_order": False}, "gone": {"handle": "gone", "in_usual_order": False}, "renamed": {"handle": "old-handle", "in_usual_order": False}}}


def runner(cart_override=None):
    state = {}

    def run(cmd, **kw):
        url = [c for c in cmd if c.startswith("https://")][0]
        assert "shop.example.com" in url, url  # never talks to another host
        if "/products.json" in url:
            return NS(returncode=0, stdout=json.dumps(PRODUCTS) + "\n200|" + url, stderr="")
        if "/cart/" in url:
            state["items"] = {int(p.split(":")[0]): int(p.split(":")[1]) for p in url.split("/cart/")[1].split(",")}
            return NS(returncode=0, stdout="<html>checkout</html>\n200|https://shop.example.com/checkouts/abc", stderr="")
        if url.endswith("/cart.js"):
            items = cart_override if cart_override is not None else state["items"]
            allv = {v["id"]: float(v["price"]) for p in PRODUCTS["products"] for v in p["variants"]}
            body = {"items": [{"variant_id": k, "quantity": q} for k, q in items.items()], "total_price": int(sum(allv[k] * q for k, q in items.items()) * 100), "currency": "AUD"}
            return NS(returncode=0, stdout=json.dumps(body) + "\n200|" + url, stderr="")
        raise AssertionError(url)
    return run


class T(unittest.TestCase):
    def test_cart_link_summary_and_verification(self):
        out = s.build(CFG, [("tissues", 2), ("towels", 2)], runner())
        self.assertIn("2 x Tissues (12 Boxes) $27.00 = $54.00", out)
        self.assertIn("Subtotal: $96.00", out); self.assertIn("exactly these items, subtotal $96.00", out)
        self.assertIn("Link: https://shop.example.com/cart/111:2,222:2", out)
        self.assertIn("Nothing has been bought", out)
        self.assertIn("was $26.00 last time", out)  # price change is surfaced

    def test_usual_order_skips_items_marked_out(self):
        args = NS(shop="x", usual=True, items=[], no_verify=False)
        s.load_shop = lambda name: CFG
        out = s.cmd_cart(args, runner())
        self.assertIn("3 x Tissues", out); self.assertIn("1 x Toilet Paper (48 Rolls)", out); self.assertNotIn("Paper Towels", out)

    def test_bare_name_uses_usual_quantity(self):
        self.assertEqual(s.parse_items(CFG, ["tissues", "towels=4"]), [("tissues", 3), ("towels", 4)])
        with self.assertRaises(s.ShopError):
            s.parse_items(CFG, ["tissues=99"])

    def test_refuses_instead_of_substituting(self):
        for key, msg in (("gone", "out of stock"), ("renamed", "no longer sold"), ("tp_any", "2 variants"), ("mystery", "unknown item")):
            with self.assertRaises(s.ShopError) as c:
                s.build(CFG, [(key, 1)], runner())
            self.assertIn(msg, str(c.exception), key)

    def test_does_not_send_a_link_the_store_did_not_honour(self):
        with self.assertRaises(s.ShopError) as c:
            s.build(CFG, [("tissues", 2)], runner(cart_override={111: 1}))
        self.assertIn("did not match", str(c.exception))

    def test_unconfigured_shop_and_bad_domain(self):
        s.DATA = tempfile.mkdtemp()
        with self.assertRaises(s.ShopError):
            s.load_shop("nothere")
        json.dump({"store": "not a domain"}, open(os.path.join(s.DATA, "bad.json"), "w"))
        with self.assertRaises(s.ShopError):
            s.load_shop("bad")


if __name__ == "__main__":
    unittest.main()
