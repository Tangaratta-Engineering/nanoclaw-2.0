import os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import weekly_pack as w


class T(unittest.TestCase):
    def test_pack_has_each_part(self):
        r = w.build({"calendar_week": lambda: "WEEK ...", "ledger_open_items": lambda: {"Open": "none"}})
        self.assertTrue(r["wakeAgent"]); self.assertEqual(r["data"]["calendar_week"], "WEEK ...")

    def test_compact_keeps_the_useful_fields_even_when_the_reasoning_contains_semicolons(self):
        line = "400e92b5-ca60 | Confidence=high; Status=Open; Why=Email says \"pay by Fri; reference 123\"; Thread id=t1; Due=2026-10-29; Type=PAY; Item=Origin bill; Amount=$342.17; Payee=Origin Energy"
        self.assertEqual(w.compact(line), "PAY | Origin bill | due 2026-10-29 | $342.17 | Origin Energy")
        self.assertEqual(w.compact("No matching rows."), "No matching rows.")

    def test_one_failing_part_does_not_stop_the_briefing(self):
        def boom():
            raise RuntimeError("notion is down")
        r = w.build({"calendar_week": lambda: "WEEK ...", "ledger_open_items": boom})
        self.assertEqual(r["data"]["calendar_week"], "WEEK ...")
        self.assertIn("could not load", r["data"]["ledger_open_items"]); self.assertIn("notion is down", r["data"]["ledger_open_items"])


if __name__ == "__main__":
    unittest.main()
