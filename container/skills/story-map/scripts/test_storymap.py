import json, os, sys, tempfile, unittest
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import storymap as sm

BOARD = {"version": 1, "updated": "x", "groups": [
    {"id": "g1", "title": "Trips", "outcomes": [
        {"id": "o2", "title": "Umina", "items": [
            {"id": "c3", "type": "pink", "text": "Where to park?", "done": False},
            {"id": "c4", "type": "yellow", "text": "Trailer registered", "done": False}]}]}]}


def run(argv, board=BOARD):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "map.json")
        json.dump(board, open(f, "w"))
        rc = sm.main(["--file", f] + argv)
        return rc, json.load(open(f))


class LocalTests(unittest.TestCase):
    def test_add_and_done(self):
        rc, data = run(["add-card", "o2", "result", "Insurance sorted"])
        self.assertEqual(rc, 0)
        cards = data["groups"][0]["outcomes"][0]["items"]
        self.assertEqual(cards[-1]["text"], "Insurance sorted")
        self.assertEqual(cards[-1]["type"], "yellow")
        rc, data = run(["done", "c4"])
        self.assertTrue(data["groups"][0]["outcomes"][0]["items"][1]["done"])

    def test_rejects_long_text_and_unknown_id(self):
        self.assertEqual(run(["add-card", "o2", "result", "x" * 300])[0], 1)
        self.assertEqual(run(["done", "nope"])[0], 1)

    def test_remove_nonempty_needs_force(self):
        self.assertEqual(run(["remove", "o2"])[0], 1)
        rc, data = run(["remove", "o2", "--force"])
        self.assertEqual((rc, data["groups"][0]["outcomes"]), (0, []))

    def test_dry_run_saves_nothing(self):
        rc, data = run(["--dry-run", "done", "c3"])
        self.assertFalse(data["groups"][0]["outcomes"][0]["items"][0]["done"])


class RemoteTests(unittest.TestCase):
    def fake(self, calls, put_code=200):
        import base64
        def runner(cmd, input=None, capture_output=True, text=True):
            method = cmd[cmd.index("-X") + 1]
            calls.append((method, cmd, input))
            if method == "GET":
                body = {"sha": "abc", "content": base64.b64encode(json.dumps(BOARD).encode()).decode()}
                return NS(returncode=0, stdout=json.dumps(body) + "\n200", stderr="")
            return NS(returncode=0, stdout=json.dumps({"commit": {"sha": "deadbeefcafe"}}) + f"\n{put_code}", stderr="")
        return runner

    def test_no_token_needed_and_commit_made(self):
        calls = []
        orig = sm._req
        sm._req = lambda m, u, t, b=None: orig(m, u, t, b, runner=self.fake(calls))
        os.environ.pop("GITHUB_TOKEN", None); os.environ.pop("STORYMAP_TOKEN", None)
        try:
            rc = sm.main(["done", "c3"])
        finally:
            sm._req = orig
        self.assertEqual(rc, 0)
        self.assertEqual([c[0] for c in calls], ["GET", "PUT"])
        self.assertNotIn("Authorization: Bearer", " ".join(calls[0][1]))  # gateway injects it
        sent = json.loads(calls[1][2])
        self.assertEqual(sent["sha"], "abc")
        self.assertTrue(sent["message"].startswith("storymap: Done"))

    def test_http_error_hint(self):
        def runner(cmd, input=None, capture_output=True, text=True):
            return NS(returncode=0, stdout='{"message":"Not Found"}\n404', stderr="")
        with self.assertRaises(sm.Fail) as cm:
            sm.Store().load.__func__  # constructed below with patched request
            orig = sm._req
            sm._req = lambda m, u, t, b=None: orig(m, u, t, b, runner=runner)
            try:
                sm.Store().load()
            finally:
                sm._req = orig
        self.assertIn("credential", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
