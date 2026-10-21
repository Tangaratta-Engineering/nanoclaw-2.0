import json, os, sys, unittest, datetime as dt
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import inbox_calendar as c

FUT = (dt.date.today() + dt.timedelta(days=5)).isoformat()


def runner(events, created):
    def run(cmd, input=None, **kw):
        method = cmd[cmd.index("-X") + 1]
        if method == "GET":
            return NS(returncode=0, stdout=json.dumps({"items": events}) + "\n200", stderr="")
        created.append(json.loads(input))
        return NS(returncode=0, stdout=json.dumps({"summary": "x", "htmlLink": "L"}) + "\n200", stderr="")
    return run


def args(**kw):
    d = dict(title="Physio", start=FUT + "T08:30", end=None, location="Pitchside", notes="n", source_link="http://l", key="t1", calendar="primary", allow_past=False)
    d.update(kw)
    return NS(**d)


class T(unittest.TestCase):
    def test_timed_event(self):
        made = []
        out = c.cmd_add(args(), runner([], made))
        self.assertIn("Added", out)
        ev = made[0]
        self.assertEqual(ev["start"], {"dateTime": FUT + "T08:30:00", "timeZone": "Australia/Sydney"})
        self.assertEqual(ev["end"]["dateTime"], FUT + "T09:30:00")
        self.assertIn("From email: http://l", ev["description"])
        self.assertEqual(ev["extendedProperties"]["private"]["nanoclawKey"], "t1")

    def test_all_day_end_is_exclusive(self):
        made = []
        c.cmd_add(args(start=FUT, end=None), runner([], made))
        self.assertEqual(made[0]["end"]["date"], (dt.date.fromisoformat(FUT) + dt.timedelta(days=1)).isoformat())

    def test_duplicates_skipped(self):
        made = []
        out = c.cmd_add(args(), runner([{"summary": "Physio for Andrew", "htmlLink": "H"}], made))
        self.assertIn("Already on the calendar", out); self.assertEqual(made, [])
        out = c.cmd_add(args(title="Dentist", key="k9"), runner([{"summary": "x", "extendedProperties": {"private": {"nanoclawKey": "k9"}}}], made))
        self.assertIn("Already", out)

    def test_past_and_bad_dates(self):
        with self.assertRaises(c.CalError):
            c.cmd_add(args(start="2020-01-01T09:00"), runner([], []))
        with self.assertRaises(c.CalError):
            c.parse_start("tomorrow")


class Agenda(unittest.TestCase):
    RULES = {"routine": [], "appointment": [], "calendars": ["primary"]}

    def test_classify(self):
        timed = {"dateTime": "2026-10-22T08:00:00+11:00"}
        cases = [
            ({"summary": "Henry medication", "start": timed, "recurringEventId": "r"}, "routine"),
            ({"summary": "Dr Lam (Psychiatrist)", "start": timed, "recurringEventId": "r"}, "appointment"),
            ({"summary": "Lunch", "start": timed, "location": "Cafe"}, "appointment"),
            ({"summary": "Mothers day", "start": {"date": "2026-10-22"}}, "allday"),
            ({"summary": "Something new", "start": timed}, "appointment"),
        ]
        for ev, want in cases:
            self.assertEqual(c.classify(ev, self.RULES, {})[0], want, ev["summary"])
        self.assertEqual(c.classify({"summary": "Piano", "start": timed}, self.RULES, {"piano": 6})[0], "routine")

    def test_learning_overrides_heuristics_and_persists(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "r.json")
        c.learn("Dr Lam", "routine", path)
        r = c.load_rules(path)
        timed = {"dateTime": "2026-10-22T08:00:00+11:00"}
        self.assertEqual(c.classify({"summary": "Dr Lam (Psychiatrist)", "start": timed}, r, {})[0], "routine")
        c.learn("Dr Lam", "appointment", path)  # the correction replaces the old rule
        r = c.load_rules(path)
        self.assertEqual((r["routine"], r["appointment"]), ([], ["dr lam"]))

    def test_render_leads_with_appointments(self):
        a = {"date": "2026-10-22", "appointment": [{"time": "09:40-10:40", "title": "Dentist", "where": "Lindfield", "calendar": "primary", "why": ""}],
             "routine": [{"time": "08:00-08:15", "title": "Henry medication", "where": "", "calendar": "primary", "why": ""}], "allday": []}
        out = c.render(a).split("\n")
        self.assertEqual(out[1], "APPOINTMENTS")
        self.assertIn("Dentist @ Lindfield", out[2])
        self.assertIn("ROUTINE: Henry medication 08:00", out[3])


if __name__ == "__main__":
    unittest.main()
