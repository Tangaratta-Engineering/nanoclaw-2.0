import base64, datetime as dt, email, json, os, sys, tempfile, unittest
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import remind as r

REF = dt.datetime(2026, 10, 23, 14, 0, tzinfo=r.TZ)


class Due(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(r.parse_due("in 2h", REF), REF + dt.timedelta(hours=2))
        self.assertEqual(r.parse_due("in 30 minutes", REF), REF + dt.timedelta(minutes=30))
        self.assertEqual(r.parse_due("tomorrow 9am", REF), REF.replace(hour=9) + dt.timedelta(days=1))
        self.assertEqual(r.parse_due("today 5pm", REF), REF.replace(hour=17))
        self.assertEqual(r.parse_due("2026-10-24T09:30", REF), REF.replace(day=24, hour=9, minute=30))
        self.assertEqual(r.parse_due("2026-10-25", REF), REF.replace(day=25, hour=9))  # a date alone means 9am

    def test_refuses_past_and_vague(self):
        for bad in ("2026-10-23T09:00", "yesterday 3pm", "soon", "later today", "tomorrow 25:00"):
            with self.assertRaises(r.RemindError):
                r.parse_due(bad, REF)


class Sending(unittest.TestCase):
    def setUp(self):
        r.DATA = tempfile.mkdtemp()
        self.sent = []

    def runner(self, cmd, input=None, **kw):
        url = [c for c in cmd if c.startswith("https://")][0]
        if url.endswith("/profile"):
            body = {"emailAddress": "george@example.com"}
        else:
            self.sent.append(json.loads(input)["raw"])
            body = {"id": "m1"}
        return NS(returncode=0, stdout=json.dumps(body) + "\n200", stderr="")

    def decode(self, raw):
        m = email.message_from_bytes(base64.urlsafe_b64decode(raw))
        return m, json.loads(m.get_payload(decode=True))

    def args(self, **kw):
        d = dict(title="Pick up Sophie's piano book", due="tomorrow 9am", notes=None)
        d.update(kw)
        return NS(**d)

    def test_needs_setup_first(self):
        with self.assertRaises(r.RemindError) as c:
            r.cmd_add(self.args(), self.runner)
        self.assertIn("not set up", str(c.exception)); self.assertEqual(self.sent, [])

    def test_email_format_for_the_shortcut(self):
        json.dump({"to": "george@icloud.example"}, open(os.path.join(r.DATA, "config.json"), "w"))
        out = r.cmd_add(self.args(notes="from Music4Kids"), self.runner)
        self.assertIn("Reminder sent", out)
        m, payload = self.decode(self.sent[0])
        self.assertEqual(m["To"], "george@icloud.example")
        self.assertTrue(m["Subject"].startswith(r.SUBJECT_TAG))
        self.assertEqual(set(payload), {"title", "due", "notes"})
        self.assertRegex(payload["due"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[+-]\d{2}:\d{2}$")  # ISO with offset

    def test_daily_limit(self):
        json.dump({"to": "x@y.example"}, open(os.path.join(r.DATA, "config.json"), "w"))
        for _ in range(r.MAX_PER_DAY):
            r.cmd_add(self.args(), self.runner)
        with self.assertRaises(r.RemindError):
            r.cmd_add(self.args(), self.runner)

    def test_selftest_goes_only_to_own_address(self):
        json.dump({"to": "phone@elsewhere.example"}, open(os.path.join(r.DATA, "config.json"), "w"))
        r.cmd_selftest(None, self.runner)
        m, payload = self.decode(self.sent[0])
        self.assertEqual(m["To"], "george@example.com"); self.assertIn("TEST", m["Subject"])

    def test_gmail_error_is_explained(self):
        json.dump({"to": "x@y.example"}, open(os.path.join(r.DATA, "config.json"), "w"))
        bad = lambda cmd, **k: NS(returncode=0, stdout=json.dumps({"error": {"message": "Insufficient Permission"}}) + "\n403", stderr="")
        with self.assertRaises(r.RemindError) as c:
            r.cmd_add(self.args(), bad)
        self.assertIn("re-authorise", str(c.exception))


if __name__ == "__main__":
    unittest.main()
