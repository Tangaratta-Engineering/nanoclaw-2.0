"""Run: python3 -m unittest container/skills/handover/scripts/test_recent_context.py"""
import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("rc", os.path.join(os.path.dirname(__file__), "recent_context.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)


def row(kind, content, ts):
    return json.dumps({"type": kind, "timestamp": ts, "message": {"content": content}})


class RecentContext(unittest.TestCase):
    def make(self, rows):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "aaaa1111.jsonl"), "w") as f:
            f.write("\n".join(rows) + "\n")
        return d

    def test_events_and_errors(self):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        d = self.make([
            row("user", '<context timezone="x" />\n<message id="1" from="general" sender="George" time="t">Email Miki about the dance invoice</message>', now),
            row("assistant", [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "gmail send"}}], now),
            row("user", [{"type": "tool_result", "tool_use_id": "t1", "content": "Error: 401 invalid credentials"}], now),
            row("assistant", [{"type": "text", "text": '<message to="general">I could not send it.</message>'}], now),
            row("user", '<message id="2" from="timmy">Do you have the draft?</message>', now),
        ])
        evs = list(rc.events_from_transcript(os.path.join(d, "aaaa1111.jsonl")))
        kinds = [k for _, k, _ in evs]
        self.assertEqual(kinds, ["user", "error", "agent", "user"])
        self.assertIn("George (via general): Email Miki", evs[0][2])
        self.assertIn("Bash gmail send -> Error: 401", evs[1][2])
        self.assertIn("said to general: I could not send it.", evs[2][2])
        self.assertTrue(evs[3][2].startswith("timmy (via timmy)"))  # other agent: no sender name

    def test_day_headers_use_sydney_time(self):
        # 2026-10-19 04:50 UTC is 15:50 on Mon 19 Oct in Sydney (AEDT, UTC+11)
        d = self.make([row("user", '<message id="1" from="general" sender="George">hello</message>', "2026-10-19T04:50:00+00:00")])
        import subprocess, sys
        out = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "recent_context.py"),
                              "--dir", d, "--hours", "100000", "--tz", "Australia/Sydney"],
                             capture_output=True, text=True, env=dict(os.environ, TZ="UTC")).stdout
        self.assertIn("--- Mon 19 Oct ---", out)
        self.assertIn("[15:50] George (via general): hello", out)

    def test_clip(self):
        self.assertEqual(rc.clip("a  b\n c", 50), "a b c")
        self.assertTrue(rc.clip("x" * 100, 10).endswith("…"))
        self.assertEqual(len(rc.clip("x" * 100, 10)), 10)


if __name__ == "__main__":
    unittest.main()
