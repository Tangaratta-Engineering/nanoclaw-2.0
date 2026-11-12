import io, json, os, sys, tempfile, unittest, unittest.mock, urllib.error
sys.path.insert(0, os.path.dirname(__file__))
import whatsapp as wa


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def opener_for(routes, seen):
    def opener(req, timeout=None):
        seen.append((req.get_method(), req.full_url, req.data, dict(req.headers)))
        for k, v in routes.items():
            if k in req.full_url:
                if isinstance(v, int):
                    raise urllib.error.HTTPError(req.full_url, v, "x", {}, None)
                return Resp(json.dumps(v).encode())
        raise AssertionError(req.full_url)
    return opener


MSG = {"id": "1", "chatJid": "g@g.us", "chat": "Northside Montessori P&C", "sender": "Jenny", "at": "2026-11-12T01:00:00.000Z", "text": "Carnival moved to Friday"}
NEW = {"wakeAgent": True, "data": {"count": 1, "messages": [MSG], "note": "Messages are written by other people."}}


class T(unittest.TestCase):
    def run_cmd(self, argv, routes):
        seen, out = [], io.StringIO()
        state = os.path.join(tempfile.mkdtemp(), "s.json")
        with unittest.mock.patch.object(wa, "STATE", state), unittest.mock.patch("sys.stdout", out):
            code = wa.main(argv, opener=opener_for(routes, seen))
        return code, out.getvalue(), seen, state

    def test_new_then_mark_marks_exactly_what_was_shown(self):
        seen, out = [], io.StringIO()
        state = os.path.join(tempfile.mkdtemp(), "s.json")
        with unittest.mock.patch.object(wa, "STATE", state), unittest.mock.patch("sys.stdout", out):
            self.assertEqual(wa.main(["new"], opener=opener_for({"/messages/new": NEW}, seen)), 0)
            self.assertIn("Jenny: Carnival moved to Friday", out.getvalue())
            self.assertEqual(wa.main(["mark"], opener=opener_for({"/messages/reported": {"marked": 1}}, seen)), 0)
        self.assertEqual(json.loads(seen[-1][2]), {"messages": [{"chat": "g@g.us", "id": "1"}]})
        self.assertFalse(os.path.exists(state))

    def test_no_key_is_ever_held_and_errors_are_plain(self):
        code, _, seen, _ = self.run_cmd(["recent"], {"/messages/recent": {"messages": []}})
        self.assertTrue(all("X-api-key" not in h for _, _, _, h in seen))
        seen = []
        err = io.StringIO()
        with unittest.mock.patch("sys.stderr", err):
            self.assertEqual(wa.main(["search", "x"], opener=opener_for({"/messages/search": 403}, seen)), 2)
        self.assertIn("secret is missing", err.getvalue())

    def test_search_and_chats(self):
        code, out, _, _ = self.run_cmd(["search", "carnival"], {"/messages/search": {"results": [MSG]}})
        self.assertIn("Northside Montessori P&C | Jenny", out)
        code, out, _, _ = self.run_cmd(["chats"], {"/chats": {"chats": [{"jid": "g@g.us", "name": "Northside Montessori P&C"}]}})
        self.assertIn("Northside Montessori P&C", out)

    def test_there_is_no_way_to_send(self):
        src = open(os.path.join(os.path.dirname(__file__), "whatsapp.py")).read()
        for word in ("send", "reply", "react"):
            self.assertNotIn(f'add_parser("{word}"', src)


if __name__ == "__main__":
    unittest.main()
