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

    def test_add_parses_quantities_and_reports_failures(self):
        out, seen = self.run_cmd(["add", "111", "222=3"], {"ok": True, "data": {"list": "NanoClaw", "added": [111], "failed": [{"stockcode": 222, "status": 500}]}})
        self.assertEqual(seen[0]["items"], [{"stockcode": 111, "qty": 1}, {"stockcode": 222, "qty": 3}])
        self.assertTrue(seen[0]["create"])
        self.assertIn("Added 1", out); self.assertIn("FAILED: 222 (HTTP 500)", out)

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


if __name__ == "__main__":
    unittest.main()
