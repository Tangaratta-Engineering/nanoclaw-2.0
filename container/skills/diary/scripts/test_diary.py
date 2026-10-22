import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(__file__))
import diary_core as c
import diary as cli

TZ = c.TZ
REF = dt.datetime(2026, 10, 23, 14, 0, tzinfo=TZ)  # Fri 23 Oct 2026, 14:00 Sydney

# Generic fixture (not any person's regimen): exercises every rule type.
MEDS = {
    "alpha": {"class": "nsaid", "unit_mg": 7.5, "per_dose_max_mg": 7.5, "min_interval_h": 12, "max_24h_mg": 15},
    "beta": {"class": "nsaid", "unit_mg": 200},
    "para": {"unit_mg": 500, "min_interval_h": 4, "max_24h_mg": 4000, "soft_24h_mg": 3000},
    "combo": {"counts_as": {"para": 500}, "unit_mg": 530, "stopped": True, "stopped_note": "stopped by the doctor"},
    "relaxant": {"unit_mg": 100, "max_24h_units": 2},
}


def dose(drug, hours_ago, mg=None, units=None, i=[0]):
    i[0] += 1
    t = REF - dt.timedelta(hours=hours_ago)
    d = c.make_dose(drug, MEDS, mg=mg, units=units, at=t, ref=REF)
    d.update(id=f"d{i[0]}", t=t)
    return d


def breaches(ds, drug=None):
    return [f for f in c.evaluate(ds, MEDS) if f[3] == "breach" and (drug is None or f[1] == drug)]


class Time(unittest.TestCase):
    def w(self, s):
        return c.parse_when(s, REF)

    def test_relative(self):
        self.assertEqual(self.w("just then")[0], REF)
        self.assertEqual(self.w("30 minutes ago")[0], REF - dt.timedelta(minutes=30))
        self.assertEqual(self.w("about 2 hours ago")[0], REF - dt.timedelta(hours=2))
        self.assertEqual(self.w("half an hour ago")[0], REF - dt.timedelta(minutes=30))
        self.assertEqual(self.w("an hour ago")[0], REF - dt.timedelta(hours=1))

    def test_clock_times(self):
        self.assertEqual(self.w("11am")[0], REF.replace(hour=11))
        self.assertEqual(self.w("~2pm")[0], REF.replace(hour=14))
        t, note = self.w("4pm")  # later than now -> yesterday, and says so
        self.assertEqual(t, REF.replace(hour=16) - dt.timedelta(days=1)); self.assertIn("yesterday", note)
        self.assertEqual(self.w("yesterday 10pm")[0], REF.replace(hour=22) - dt.timedelta(days=1))
        self.assertEqual(self.w("last night 11pm")[0], REF.replace(hour=23) - dt.timedelta(days=1))

    def test_unresolvable_is_an_error_not_a_guess(self):
        for s in ("earlier", "this morning sometime", "a while back"):
            with self.assertRaises(ValueError):
                self.w(s)


class Rules(unittest.TestCase):
    def test_per_dose_max(self):
        self.assertTrue(breaches([dose("alpha", 1, mg=15)], "alpha"))
        self.assertFalse(breaches([dose("alpha", 1)], "alpha"))

    def test_min_interval(self):
        bad = breaches([dose("alpha", 11), dose("alpha", 0.1)], "alpha")
        self.assertTrue(any("minimum 12" in f[2] for f in bad))
        self.assertFalse(breaches([dose("alpha", 13), dose("alpha", 0.1)], "alpha"))

    def test_same_minute_duplicate_is_still_an_interval_breach(self):
        a, b = dose("alpha", 0), dose("alpha", 0)
        self.assertTrue(any("minimum 12" in f[2] for f in breaches([a, b], "alpha")))

    def test_rolling_24h_cap(self):
        ds = [dose("para", 20, units=2), dose("para", 15, units=2), dose("para", 10, units=2), dose("para", 5, units=2), dose("para", 0.5, units=1)]
        self.assertTrue(any("over the 4000" in f[2] for f in breaches(ds, "para")))
        spread = [dose("para", 40, units=2), dose("para", 30, units=2), dose("para", 20, units=2), dose("para", 10, units=2), dose("para", 0.5, units=2)]
        self.assertFalse(any("over the 4000" in f[2] for f in breaches(spread, "para")))  # 5 g overall, but never more than 3 g in any 24 h

    def test_soft_limit_is_a_warning_not_a_breach(self):
        ds = [dose("para", 20, units=2), dose("para", 14, units=2), dose("para", 8, units=2), dose("para", 3, units=1)]
        fs = c.evaluate(ds, MEDS)
        self.assertTrue(any(f[3] == "warning" for f in fs)); self.assertFalse(any(f[3] == "breach" for f in fs))

    def test_combination_product_counts_toward_the_ingredient(self):
        ds = [dose("para", 10, units=4), dose("combo", 5, units=3), dose("para", 0.5, units=1)]  # 2000+1500+500 plus interval
        fs = c.evaluate(ds, MEDS)
        self.assertTrue(any(f[1] == "combo" and "stopped" in f[2] for f in fs))
        ds2 = ds + [dose("combo", 0.2, units=2)]
        self.assertTrue(any("over the 4000" in f[2] for f in breaches(ds2)))

    def test_different_nsaids_same_day(self):
        self.assertTrue(any("same day" in f[2] for f in breaches([dose("alpha", 3), dose("beta", 1)])))
        old = [dose("alpha", 30), dose("beta", 1)]  # different calendar days (30 h apart)
        self.assertFalse(any("same day" in f[2] for f in breaches(old)))

    def test_unit_cap(self):
        self.assertTrue(any("units" in f[2] for f in breaches([dose("relaxant", 8), dose("relaxant", 4), dose("relaxant", 0.5)])))
        self.assertFalse(breaches([dose("relaxant", 8), dose("relaxant", 0.5)]))

    def test_backfilled_dose_checked_in_order(self):
        # recorded late, but time order decides: the later of the two is the one inside the interval
        ds = sorted([dose("alpha", 1), dose("alpha", 6)], key=lambda d: d["t"])
        self.assertTrue(breaches(ds, "alpha"))


class NextAllowed(unittest.TestCase):
    def test_after_interval_and_window(self):
        ds = [dose("alpha", 2)]
        t = c.next_allowed("alpha", MEDS, ds, REF)
        self.assertEqual(t, (REF - dt.timedelta(hours=2)) + dt.timedelta(hours=12))

    def test_free_to_take_now(self):
        self.assertLessEqual(c.next_allowed("para", MEDS, [], REF), REF)

    def test_stopped_drug_has_no_next(self):
        self.assertIsNone(c.next_allowed("combo", MEDS, [], REF))

    def test_waits_for_old_doses_to_leave_the_window(self):
        ds = [dose("para", 23, units=2), dose("para", 19, units=2), dose("para", 15, units=2), dose("para", 11, units=2), dose("para", 7, units=2), dose("para", 3, units=2)]
        # 12 x 500 = 6000 mg is already over; the next allowed is when the total falls back to <= 3500
        t = c.next_allowed("para", MEDS, ds, REF)
        self.assertGreater(t, REF)
        cand = dict(c.make_dose("para", MEDS, at=t, ref=REF), id="x", t=t)
        self.assertFalse([f for f in c.evaluate(ds + [cand], MEDS) if f[0] == "x" and f[3] == "breach"])

    def test_unknown_drug_is_refused(self):
        with self.assertRaises(ValueError):
            c.make_dose("mystery", MEDS, at=REF, ref=REF)


class Storage(unittest.TestCase):
    def setUp(self):
        c.DATA = tempfile.mkdtemp()
        with open(os.path.join(c.DATA, "meds.json"), "w") as f:
            json.dump({"drugs": MEDS}, f)

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["--ref", REF.isoformat(), *args])
        return rc, out.getvalue()

    def test_log_dose_check_and_status(self):
        rc, out = self.run_cli("log", "--severity", "6", "--location", "base of skull", "--at", "30 minutes ago")
        self.assertEqual(rc, 0); self.assertIn("6/10", out)
        rc, out = self.run_cli("dose", "--drug", "alpha", "--at", "just then")
        self.assertIn("Logged alpha 7.5 mg", out); self.assertNotIn("BREACH", out)
        rc, out = self.run_cli("check", "--drug", "alpha")
        self.assertIn("NOT ALLOWED", out); self.assertIn("Earliest allowed: Sat 24 Oct 02:00", out)
        rc, out = self.run_cli("dose", "--drug", "alpha", "--at", "20 minutes ago")
        self.assertIn("BREACH", out.splitlines()[0])  # the breach is the first line
        rc, out = self.run_cli("status")
        self.assertIn("alpha", out)

    def test_amend_keeps_history_and_void_hides_from_totals(self):
        self.run_cli("dose", "--drug", "para", "--units", "2", "--at", "1 hour ago")
        rec = [r for r in c.load() if r["kind"] == "dose"][0]
        self.run_cli("amend", rec["id"], "--units", "1", "--mg", "500", "--reason", "he said one tablet")
        self.assertEqual([r for r in c.load() if r["id"] == rec["id"]][0]["mg"], 500)
        raw = open(os.path.join(c.DATA, "entries.jsonl")).read().splitlines()
        self.assertEqual(len(raw), 2)  # the original line is still there
        self.run_cli("amend", rec["id"], "--void")
        self.assertEqual(c.doses(c.load()), [])
        self.assertEqual(len(open(os.path.join(c.DATA, "entries.jsonl")).read().splitlines()), 3)

    def test_render_and_export(self):
        self.run_cli("log", "--severity", "5", "--location", "temple", "--at", "2 hours ago")
        self.run_cli("dose", "--drug", "para", "--units", "2", "--at", "1 hour ago")
        rc, out = self.run_cli("render", "--days", "1")
        self.assertIn("## Friday 23 October 2026", out); self.assertIn("para 1000 mg", out); self.assertIn("5/10", out)
        rc, out = self.run_cli("export", "--start", "2026-10-23", "--end", "2026-10-23")
        self.assertIn("max 5/10", out); self.assertIn("para 1000 mg", out); self.assertIn("Limit breaches: none", out)

    def test_bad_input_exits_nonzero(self):
        rc, _ = self.run_cli("log", "--severity", "11")
        self.assertEqual(rc, 1)
        rc, _ = self.run_cli("dose", "--drug", "alpha", "--at", "earlier")
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
