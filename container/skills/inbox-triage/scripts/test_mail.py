import base64, json, os, sys, unittest
from io import StringIO
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import inbox_gmail as g
import inbox_mail as m


def enc(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def booking(plain="No Content"):
    html = "<html><body><p>Booking ID: 505157</p><p>Accommodation type: Sunset Villa</p><p>Check in: 2pm</p><style>.x{}</style></body></html>"
    return {"id": "m1", "threadId": "t1", "snippet": "", "payload": {"headers": [{"name": "Subject", "value": "Booking Confirmation"}, {"name": "From", "value": "Resort <r@example.com>"}, {"name": "Date", "value": "Wed, 21 Oct 2026 06:24:06 +0000"}, {"name": "To", "value": "g@example.com"}],
            "parts": [{"mimeType": "multipart/alternative", "parts": [{"mimeType": "text/plain", "body": {"data": enc(plain)}}, {"mimeType": "text/html", "body": {"data": enc(html)}}]},
                      {"mimeType": "application/pdf", "filename": "Receipt_1.pdf", "body": {"attachmentId": "A1", "size": 100}}]}}


class Body(unittest.TestCase):
    def test_placeholder_plain_text_falls_back_to_html(self):
        t = g.body_text(booking("No Content"))
        self.assertIn("Sunset Villa", t); self.assertIn("Check in: 2pm", t); self.assertNotIn(".x{}", t)

    def test_other_placeholders_and_tiny_plain(self):
        for ph in ("No content.", "This email requires HTML to be viewed.", "View in browser", "ok"):
            self.assertIn("Sunset Villa", g.body_text(booking(ph)), ph)

    def test_real_plain_text_is_still_preferred(self):
        real = "Hi George, your booking is confirmed. See you on the 30th, the team at the resort."
        self.assertEqual(g.body_text(booking(real)), real)


class Tools(unittest.TestCase):
    def fake(self):
        def call(method, path, body=None):
            if path.startswith("/messages?"):
                self.last_query = path
                return {"messages": [{"id": "m1"}]}
            if path.startswith("/messages/m1"):
                return booking()
            raise AssertionError(path)
        return call

    def test_search_covers_the_whole_mailbox_and_lists_attachments(self):
        out = m.cmd_search(NS(query="505157", limit=5, spam=False), self.fake())
        self.assertIn("in%3Aanywhere", self.last_query)
        self.assertIn("Booking Confirmation", out); self.assertIn("Receipt_1.pdf", out)

    def test_search_keeps_an_explicit_scope(self):
        m.cmd_search(NS(query="from:resort in:inbox", limit=5, spam=False), self.fake())
        self.assertNotIn("anywhere", self.last_query)

    def test_read_shows_html_body_and_hints_at_the_pdf(self):
        out = m.cmd_read(NS(id="m1", pdf=False, max_chars=6000), self.fake())
        self.assertIn("Accommodation type: Sunset Villa", out); self.assertIn("run again with --pdf", out)

    def test_empty_search_says_how_to_widen(self):
        out = m.cmd_search(NS(query="nothing", limit=5, spam=False), lambda *a, **k: {})
        self.assertIn("Widen it", out)


if __name__ == "__main__":
    unittest.main()
