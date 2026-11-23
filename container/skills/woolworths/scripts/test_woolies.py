import json, os, sys, tempfile, threading, time, unittest
sys.path.insert(0, os.path.dirname(__file__))
import woolies as w


def bridge(queue, reply, seen):
    """A fake host bridge: answers the first request that appears."""
    def loop():
        for _ in range(100):
            for f in os.listdir(os.path.join(queue, "in")):
                if f.endswith(".json"):
                    p = os.path.join(queue, "in", f)
                    seen.append(json.load(open(p)))
                    os.remove(p)
                    json.dump(reply, open(os.path.join(queue, "out", f), "w"))
                    return
            time.sleep(0.02)
    t = threading.Thread(target=loop); t.start(); return t


class T(unittest.TestCase):
    def setUp(self):
        self.q = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.q, "in")); os.makedirs(os.path.join(self.q, "out"))
        self.ask = lambda req, **kw: w.ask(req, queue=self.q, timeout=3)

    def run_cmd(self, argv, reply):
        seen = []
        t = bridge(self.q, reply, seen)
        out = w.run(argv, ask=self.ask)
        t.join()
        return out, seen

    def test_usual_formats_items(self):
        out, seen = self.run_cmd(["usual", "milk"], {"ok": True, "data": {"total": 1, "items": [
            {"stockcode": 88436, "name": "Dairy Farmers Full Cream", "size": "2L", "price": 4.2, "cup": "$2.10 / 1L", "boughtBefore": True, "available": True}]}})
        self.assertEqual(seen[0], {"op": "history", "query": "milk", "limit": 6})
        self.assertIn("88436 | Dairy Farmers Full Cream | 2L | $4.20 | $2.10 / 1L | bought before", out)

    def test_add_parses_quantities_and_reports_what_is_on_the_list(self):
        reply = {"ok": True, "data": {"list": "NanoClaw", "added": [111], "failed": [{"stockcode": 222, "status": 500}], "results": [
            {"stockcode": 111, "name": "Milk 2L", "quantity": 3}, {"stockcode": 222, "name": None, "quantity": None}]}}
        out, seen = self.run_cmd(["add", "111=3", "222"], reply)
        self.assertEqual(seen[0]["op"], "add")
        self.assertEqual(seen[0]["items"], [{"stockcode": 111, "qty": 3}, {"stockcode": 222, "qty": 1}])
        self.assertTrue(seen[0]["create"])
        self.assertIn("x3 111 Milk 2L", out); self.assertIn("NOT confirmed", out); self.assertIn("FAILED: 222 (HTTP 500)", out)

    def test_remove_and_clear(self):
        out, seen = self.run_cmd(["remove", "111", "222"], {"ok": True, "data": {"list": "NanoClaw", "removed": [111], "notOnList": [222]}})
        self.assertEqual(seen[0], {"op": "remove", "list": "NanoClaw", "items": [{"stockcode": 111}, {"stockcode": 222}]})
        self.assertIn("Removed from the Woolworths list 'NanoClaw': 111", out); self.assertIn("Wasn't on the list: 222", out)
        out, seen = self.run_cmd(["clear", "--yes"], {"ok": True, "data": {"list": "NanoClaw", "removed": [1, 2, 3], "notOnList": []}})
        self.assertEqual(seen[0], {"op": "clear", "list": "NanoClaw", "confirm": True})
        self.assertIn("removed 3", out)

    def test_clear_needs_yes(self):
        with self.assertRaises(SystemExit):
            w.run(["clear"], ask=self.ask)

    def test_set_sends_the_set_op(self):
        _, seen = self.run_cmd(["set", "111=2"], {"ok": True, "data": {"list": "NanoClaw", "added": [111], "failed": [], "results": [{"stockcode": 111, "name": "Milk", "quantity": 2}]}})
        self.assertEqual(seen[0]["op"], "set")
        self.assertEqual(seen[0]["items"], [{"stockcode": 111, "qty": 2}])

    def test_other_list_is_not_auto_created(self):
        _, seen = self.run_cmd(["add", "--list", "Party", "5"], {"ok": True, "data": {"list": "Party", "added": [5], "failed": []}})
        self.assertFalse(seen[0]["create"])

    def test_bridge_error_is_a_clean_failure(self):
        seen = []; t = bridge(self.q, {"ok": False, "error": "not signed in"}, seen)
        with self.assertRaises(SystemExit):
            w.run(["lists"], ask=self.ask)
        t.join()

    def test_no_answer_times_out_and_cleans_up(self):
        with self.assertRaises(w.WooliesError):
            w.ask({"op": "status"}, queue=self.q, timeout=0.3)
        self.assertEqual(os.listdir(os.path.join(self.q, "in")), [])

    def test_bad_item_rejected(self):
        with self.assertRaises(SystemExit):
            w.run(["add", "milk"], ask=self.ask)


def multi_bridge(queue, replies, seen):
    """A fake bridge that keeps answering, by op, until stopped. Returns (thread, stop event)."""
    stop = threading.Event()
    def loop():
        while not stop.is_set():
            for f in os.listdir(os.path.join(queue, "in")):
                if f.endswith(".json"):
                    p = os.path.join(queue, "in", f)
                    req = json.load(open(p)); seen.append(req); os.remove(p)
                    json.dump(replies[req["op"]], open(os.path.join(queue, "out", f), "w"))
            time.sleep(0.02)
    t = threading.Thread(target=loop); t.start(); return t, stop


def prod(code, name, ingredients, contains=None, maybe=None, dietary=(), free_from=None):
    return {"stockcode": code, "name": name, "size": "250g", "ingredients": ingredients, "allergensContain": contains, "mayContain": maybe,
            "freeFrom": free_from, "dietary": list(dietary), "ingredientsAvailable": bool(ingredients)}


def add_reply(*codes):
    return {"ok": True, "data": {"list": "NanoClaw", "added": list(codes), "failed": [],
            "results": [{"stockcode": c, "name": f"P{c}", "quantity": 1} for c in codes]}}


class Base(unittest.TestCase):
    def setUp(self):
        self.q = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.q, "in")); os.makedirs(os.path.join(self.q, "out"))
        self.ask = lambda req, **kw: w.ask(req, queue=self.q, timeout=3)


class Avoid(Base):
    def go(self, argv, products, add=None):
        seen = []
        replies = {"ingredients": {"ok": True, "data": {"items": products}}, "add": add or add_reply()}
        t, stop = multi_bridge(self.q, replies, seen)
        try:
            out, code = w.run_with_status(argv, ask=self.ask)
        finally:
            stop.set(); t.join()
        return out, code, seen

    def test_ingredients_command_prints_fields_and_not_available(self):
        seen = []
        replies = {"ingredients": {"ok": True, "data": {"items": [
            prod(111, "Spread", "Vegetable oils, water, salt.", contains="Soy", dietary=["VEGAN"], free_from="Dairy Free"),
            prod(222, "Mystery", None),
            {"stockcode": 333, "error": "product detail failed (HTTP 404)"}]}}}
        t, stop = multi_bridge(self.q, replies, seen)
        try:
            out = w.run(["ingredients", "111", "222", "333"], ask=self.ask)
        finally:
            stop.set(); t.join()
        self.assertEqual(seen[0], {"op": "ingredients", "stockcodes": [111, 222, 333]})
        self.assertIn("ingredients: Vegetable oils, water, salt.", out)
        self.assertIn("declared allergens (contains): Soy", out)
        self.assertIn("VEGAN", out)
        self.assertIn("ingredients: NOT AVAILABLE", out)
        self.assertIn("333: ERROR product detail failed (HTTP 404)", out)

    def test_ingredients_rejects_marketplace_and_junk_codes(self):
        for bad in ("1122348401", "milk", "0"):
            with self.assertRaises(SystemExit):
                w.run(["ingredients", bad], ask=self.ask)
        with self.assertRaises(SystemExit):
            w.run(["add", "--avoid", "dairy", "1122348401"], ask=self.ask)

    def test_milk_product_is_withheld_with_quote_and_clear_one_is_added_with_qty(self):
        out, code, seen = self.go(["add", "--avoid", "dairy,egg", "111=3", "222"], [
            prod(111, "Plain Flour", "Wheat flour."),
            prod(222, "Salted Butter", "Cream (Milk), Salt.")], add_reply(111))
        self.assertEqual(code, 1)
        self.assertIn("NOT ADDED: 222 Salted Butter", out)
        self.assertIn("(avoiding dairy)", out)
        self.assertIn("Cream (Milk), Salt.", out)
        add = [s for s in seen if s["op"] == "add"][0]
        self.assertEqual(add["items"], [{"stockcode": 111, "qty": 3}])
        self.assertIn("On the Woolworths list 'NanoClaw': x1 111 P111", out)  # what WAS added is still listed

    def test_all_clear_adds_everything_and_exits_zero(self):
        out, code, seen = self.go(["add", "--avoid", "dairy", "111"], [prod(111, "Flour", "Wheat flour.")], add_reply(111))
        self.assertEqual(code, 0)
        self.assertIn("x1 111", out)
        self.assertIn("read the label", out)

    def test_flora_style_milk_with_lactose_free_claim_is_flagged_for_dairy(self):
        flora = prod(5, "Lactose Free Spread", "Vegetable oils, skim milk powder (lactose free), salt.", dietary=["Lactose Free"], free_from="Lactose Free")
        out, code, seen = self.go(["add", "--avoid", "dairy", "5"], [flora])
        self.assertEqual(code, 1)
        self.assertIn("'milk'", out)
        self.assertFalse([s for s in seen if s["op"] == "add"])  # nothing to add, so no add request
        self.assertIn("Nothing was added.", out)

    def test_lactose_free_phrase_alone_is_not_a_dairy_mention(self):
        self.assertEqual(w.check_product(prod(1, "x", "Vegetable oil, water. Lactose free."), w.expand_terms("dairy"))[0], "clear")
        self.assertEqual(w.check_product(prod(1, "x", "Water, dairy free flavour."), w.expand_terms("dairy"))[0], "clear")

    def test_free_from_claims_are_not_scanned(self):
        p = prod(1, "x", "Wheat flour.", free_from="Dairy Free,Egg Free")
        self.assertEqual(w.check_product(p, w.expand_terms("dairy,egg"))[0], "clear")

    def test_unknown_data_is_withheld_unless_allowed(self):
        out, code, seen = self.go(["add", "--avoid", "dairy", "9"], [prod(9, "Mystery", None)])
        self.assertEqual(code, 1)
        self.assertIn("can't verify", out)
        self.assertFalse([s for s in seen if s["op"] == "add"])
        out, code, seen = self.go(["add", "--avoid", "dairy", "--allow-unknown", "9"], [prod(9, "Mystery", None)], add_reply(9))
        self.assertEqual(code, 0)
        self.assertIn("WITHOUT a check", out)
        self.assertTrue([s for s in seen if s["op"] == "add"])

    def test_a_failed_product_fetch_is_unknown(self):
        out, code, _ = self.go(["add", "--avoid", "dairy", "9"], [{"stockcode": 9, "error": "product detail failed (HTTP 500)"}])
        self.assertEqual(code, 1)
        self.assertIn("HTTP 500", out)

    def test_may_contain_is_a_withholding_warning(self):
        for p in (prod(1, "A", "Wheat flour. May contain traces of milk."), prod(1, "A", "Wheat flour.", maybe="Milk, Egg")):
            v, reasons = w.check_product(p, w.expand_terms("dairy"))
            self.assertEqual(v, "blocked")
            self.assertIn("MAY CONTAIN", reasons[0])
        out, code, _ = self.go(["add", "--avoid", "milk", "1"], [prod(1, "A", "Wheat flour.", maybe="Milk")])
        self.assertEqual(code, 1)
        self.assertIn("MAY CONTAIN", out)

    def test_synonyms(self):
        cases = [("dairy", "Sugar, whey powder."), ("dairy", "Sodium caseinate (milk)"), ("dairy", "Yoghurt culture"), ("egg", "Albumen, sugar"),
                 ("gluten", "Barley malt extract"), ("nuts", "Roasted almonds"), ("nuts", "Peanut oil"), ("peanut", "peanuts"),
                 ("soy", "Emulsifier (soy lecithin)"), ("shellfish", "Prawn paste"), ("sesame", "Tahini"), ("fish", "Anchovies"),
                 ("treenut", "Cashew paste"), ("coriander", "Coriander seed")]
        for term, text in cases:
            self.assertEqual(w.check_product(prod(1, "x", text), w.expand_terms(term))[0], "blocked", (term, text))
        self.assertEqual(w.check_product(prod(1, "x", "Peanut oil"), w.expand_terms("treenut"))[0], "clear")

    def test_stray_spaces_in_the_sites_text_are_tolerated(self):
        for text in ("Skimmed mi lk powder", "Wh ey protein", "Vegetable oil, but ter"):
            self.assertEqual(w.check_product(prod(1, "x", text), w.expand_terms("dairy"))[0], "blocked", text)

    def test_common_non_dairy_compounds_are_excluded_only_for_dairy(self):
        for text in ("Cocoa butter, sugar", "Peanut butter", "Coconut cream, water", "Cream of tartar", "Shea butter", "Soy milk"):
            self.assertEqual(w.check_product(prod(1, "x", text), w.expand_terms("dairy"))[0], "clear", text)
        self.assertEqual(w.check_product(prod(1, "x", "Soy milk"), w.expand_terms("soy"))[0], "blocked")
        self.assertEqual(w.check_product(prod(1, "x", "Peanut butter"), w.expand_terms("peanut"))[0], "blocked")
        self.assertEqual(w.check_product(prod(1, "x", "Cocoa butter, butter"), w.expand_terms("dairy"))[0], "blocked")

    def test_declared_allergens_are_checked(self):
        v, reasons = w.check_product(prod(1, "x", "Water.", contains="Milk"), w.expand_terms("dairy"))
        self.assertEqual(v, "blocked"); self.assertIn("declared allergens", reasons[0])

    def test_add_without_avoid_sends_no_ingredients_request(self):
        seen = []
        replies = {"add": add_reply(111), "ingredients": {"ok": True, "data": {"items": []}}}
        t, stop = multi_bridge(self.q, replies, seen)
        try:
            out, code = w.run_with_status(["add", "111"], ask=self.ask)
        finally:
            stop.set(); t.join()
        self.assertEqual([s["op"] for s in seen], ["add"])
        self.assertEqual(code, 0)
        self.assertNotIn("read the label", out)


if __name__ == "__main__":
    unittest.main()
