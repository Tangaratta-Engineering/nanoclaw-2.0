import base64, json, os, sys, tempfile, unittest
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import inbox_drafts as d
import inbox_gmail as g


def hdrs(**kw):
    return [{"name": k.replace("_", "-"), "value": v} for k, v in kw.items()]


class Gmail:
    """Tiny in-memory Gmail: one thread with a message from Sam, drafts, sends."""
    def __init__(self):
        self.drafts, self.sent, self.n = {}, [], 0

    def __call__(self, method, path, body=None):
        if path == "/profile":
            return {"emailAddress": "george@example.com"}
        if path.startswith("/threads/"):
            return {"messages": [{"id": "m1", "payload": {"headers": hdrs(From="Sam <sam@acme.com>", To="george@example.com", Subject="Quote", Message_ID="<a@x>")}}]}
        if path == "/drafts" and method == "POST":
            self.n += 1
            self.drafts[f"d{self.n}"] = body["message"]["raw"]
            return {"id": f"d{self.n}"}
        if path.startswith("/drafts/") and method == "PUT":
            self.drafts[path.split("/")[2]] = body["message"]["raw"]
            return {}
        if path.startswith("/drafts/") and method == "GET":
            did = path.split("/")[2].split("?")[0]
            import email
            m = email.message_from_bytes(base64.urlsafe_b64decode(self.drafts[did]))
            h = [{"name": k, "value": v} for k, v in m.items()]
            return {"message": {"payload": {"headers": h, "parts": [{"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(m.get_payload(decode=True)).decode()}}]}}}
        if path == "/drafts/send":
            self.sent.append(body["id"])
            return {"id": "sentmsg"}
        raise AssertionError((method, path))


class T(unittest.TestCase):
    def setUp(self):
        d.DATA = tempfile.mkdtemp()
        self.g = Gmail()
        self.body = os.path.join(d.DATA, "b.txt")
        open(self.body, "w").write("Thanks Sam, yes please go ahead.")

    def create(self, **kw):
        return d.cmd_create(NS(thread="t1", body_file=self.body, to=kw.get("to")), self.g)

    def test_send_requires_card(self):
        self.create()
        with self.assertRaises(g.GmailError) as c:
            d.cmd_send(NS(draft="d1"), self.g)
        self.assertIn("not been shown", str(c.exception))
        self.assertIn("sam@acme.com", d.cmd_card(NS(draft="d1"), self.g))
        self.assertIn("sent", d.cmd_send(NS(draft="d1"), self.g))
        self.assertEqual(self.g.sent, ["d1"])
        with self.assertRaises(g.GmailError):  # no double send
            d.cmd_send(NS(draft="d1"), self.g)

    def test_edit_invalidates_card(self):
        self.create(); d.cmd_card(NS(draft="d1"), self.g)
        open(self.body, "w").write("Changed text")
        d.cmd_edit(NS(draft="d1", body_file=self.body), self.g)
        with self.assertRaises(g.GmailError):
            d.cmd_send(NS(draft="d1"), self.g)
        self.assertIn("Changed text", d.cmd_card(NS(draft="d1"), self.g))
        d.cmd_send(NS(draft="d1"), self.g)

    def test_tamper_after_card_blocks_send(self):
        self.create(); d.cmd_card(NS(draft="d1"), self.g)
        import email.message as em
        m = em.EmailMessage(); m["To"] = "sam@acme.com"; m["Subject"] = "Re: Quote"; m.set_content("sneaky different text")
        self.g.drafts["d1"] = base64.urlsafe_b64encode(m.as_bytes()).decode()
        with self.assertRaises(g.GmailError) as c:
            d.cmd_send(NS(draft="d1"), self.g)
        self.assertIn("changed", str(c.exception))

    def test_stranger_recipient_rejected(self):
        with self.assertRaises(g.GmailError) as c:
            self.create(to=["evil@elsewhere.com"])
        self.assertIn("already be on the thread", str(c.exception))

    def test_daily_limit(self):
        for i in range(d.MAX_SENDS_PER_DAY):
            self.create(); d.cmd_card(NS(draft=f"d{i+1}"), self.g); d.cmd_send(NS(draft=f"d{i+1}"), self.g)
        self.create(); d.cmd_card(NS(draft="d11"), self.g)
        with self.assertRaises(g.GmailError) as c:
            d.cmd_send(NS(draft="d11"), self.g)
        self.assertIn("limit", str(c.exception))


if __name__ == "__main__":
    unittest.main()
