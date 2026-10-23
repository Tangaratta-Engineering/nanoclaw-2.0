import base64, json, os, sys, tempfile, unittest
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import inbox_fetch as f
import inbox_gmail as g


def enc(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def msg(i, frm, subj, body, thread=None, labels=(), extra=(), html=None, atts=()):
    parts = [{"mimeType": "text/plain", "body": {"data": enc(body)}}]
    if html:
        parts.append({"mimeType": "text/html", "body": {"data": enc(html)}})
    for fn in atts:
        parts.append({"mimeType": "application/pdf", "filename": fn, "body": {"attachmentId": "a1", "size": 10}})
    return {"id": i, "threadId": thread or "t" + i, "labelIds": list(labels), "snippet": body[:50],
            "payload": {"headers": [{"name": "From", "value": frm}, {"name": "Subject", "value": subj}, {"name": "Date", "value": "Tue, 20 Oct 2026 08:00:00 +1100"}] + [{"name": k, "value": v} for k, v in extra],
                        "parts": parts}}


MSGS = {
    "m1": msg("m1", "Origin Energy <billing@origin.com.au>", "Your tax invoice is ready", "Amount due $342.17. Due date: 3 November 2026. BPAY Biller code: 1234 Ref: 998877665"),
    "m2": msg("m2", "Deals <news@shop.com>", "50% off everything", "Big sale!", labels=["CATEGORY_PROMOTIONS"], extra=[("List-Unsubscribe", "<x>")]),
    "m3": msg("m3", "Emily <emily@example.com>", "Camping", "Can you book the site?", thread="tc"),
    "m4": msg("m4", "Shop <news@shop.com>", "Invoice reminder 50% off", "Final notice: payment overdue $12.00", labels=["CATEGORY_PROMOTIONS"], extra=[("List-Unsubscribe", "<x>")]),
    "m5": msg("m5", "No Reply <noreply@bank.com>", "Your statement", "Hello", atts=["statement.pdf"]),
    "m6": msg("m6", "Duolingo <hello@duolingo.com>", "Practice time", "learn"),
    "m8": msg("m8", "Flick <no-reply@flick.com.au>", "Your Pest Control Service is Due Soon", "book now", labels=["CATEGORY_PROMOTIONS"], extra=[("List-Unsubscribe", "<x>")]),
    "m9": msg("m9", "George <george@example.com>", "[NC-REMINDER] Pick up the book", '{"title": "Pick up the book", "due": "2026-10-24T09:00+11:00", "notes": "payment due"}'),
    "m7": msg("m7", "Sys <noreply@service.com>", "Verification code", "123456"),
}


def fake(sent_threads=("tc",)):
    def call(method, path, body=None):
        if path.startswith("/messages?"):
            if "in:sent" in path:
                return {"messages": [{"id": "s" + t, "threadId": t} for t in sent_threads]}
            return {"messages": [{"id": i} for i in MSGS]}
        if path.startswith("/messages/m"):
            return MSGS[path.split("/")[2].split("?")[0]]
        if "/attachments/" in path:
            return {"data": enc("not a real pdf")}
        raise AssertionError(path)
    return call


class T(unittest.TestCase):
    def run_fetch(self):
        d = tempfile.mkdtemp()
        f.DATA = d
        rules = os.path.join(d, "rules.json")
        json.dump({"senders_to_ignore": ["hello@duolingo.com"], "keywords_to_ignore": [], "domains_to_ignore": []}, open(rules, "w"))
        out = f.run(NS(days=2, since=None, rules=rules, body_chars=1500, dry_run=False), fake())
        ds = json.load(open(out["data"]["dataset"]))
        return out, ds, d

    def test_filtering(self):
        out, ds, d = self.run_fetch()
        kept = {e["id"] for e in ds["emails"]}
        self.assertEqual(kept, {"m1", "m3", "m4", "m5", "m8"})  # invoice, person, financial-looking promo, attachment, due-soon notice
        self.assertTrue(out["wakeAgent"])
        self.assertEqual(ds["counts"]["skipped"], 4)
        self.assertNotIn("m9", kept)  # NanoClaw's own phone-reminder email, even though its text mentions a payment

    def test_hints_and_replied(self):
        _, ds, _ = self.run_fetch()
        by = {e["id"]: e for e in ds["emails"]}
        self.assertIn("$342.17", by["m1"]["hints"]["amounts"])
        self.assertTrue(by["m1"]["hints"]["due_hints"])
        self.assertTrue(by["m3"]["already_replied"])
        self.assertFalse(by["m1"]["already_replied"])
        self.assertEqual(ds["emails"][0]["hints"]["financial"], True)  # financial first

    def test_state_prevents_duplicates(self):
        out, ds, d = self.run_fetch()
        out2 = f.run(NS(days=2, since=None, rules=os.path.join(d, "rules.json"), body_chars=1500, dry_run=False), fake())
        self.assertFalse(out2["wakeAgent"])
        self.assertEqual(out2["data"]["counts"]["new"], 0)

    def test_html_text(self):
        t = g.html_to_text("<html><style>x{}</style><body><p>Hello&nbsp;<b>there</b></p><div>Pay $5</div></body></html>")
        self.assertIn("Hello there", t); self.assertIn("Pay $5", t); self.assertNotIn("x{}", t)


if __name__ == "__main__":
    unittest.main()
