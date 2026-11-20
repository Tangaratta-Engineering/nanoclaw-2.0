#!/usr/bin/env python3
"""Tests for claims.py (no bridge needed). Run: python3 test_claims.py"""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(__file__))
import claims as c  # noqa: E402


def out(argv, ask, save=lambda *a, **k: "x.pdf"):
    buf = io.StringIO()
    with redirect_stdout(buf):
        c.run(argv, ask=ask, save=save)
    return buf.getvalue()


ADD = ["add", "--email", "e1", "--provider", "Example Physio", "--patient", "Mr Alex Example", "--invoice-no", "1001",
       "--date", "2026-11-20", "--amount", "90", "--reference", "chiropractor"]
BASE = {"id": 7, "status": "ready", "provider": "Example Physio", "patient": "Mr Alex Example", "patient_known": True,
        "invoice_no": "1001", "date": "2026-11-20", "amount": 90.0, "reference": "physio"}


class T(unittest.TestCase):
    def test_add_sends_file_name_not_path(self):
        seen = []
        def ask(req): seen.append(req); return {**BASE, "duplicate": False, "needs_provider_approval": False}
        o = out(ADD, ask, save=lambda e, w: "e1-invoice.pdf")
        self.assertEqual(seen[0]["pdf"], "e1-invoice.pdf"); self.assertEqual(seen[0]["amount"], 90.0)
        self.assertIn("Registered claim #7", o)

    def test_unknown_provider_tells_agent_to_ask_george(self):
        o = out(ADD, lambda r: {**BASE, "status": "pending_provider", "duplicate": False, "needs_provider_approval": True})
        self.assertIn("NOT on the allowed list", o); self.assertIn("Do not prepare", o)

    def test_duplicate_and_unknown_patient(self):
        self.assertIn("DUPLICATE", out(ADD, lambda r: {**BASE, "duplicate": True}))
        o = out(ADD, lambda r: {**BASE, "patient_known": False, "duplicate": False, "needs_provider_approval": False})
        self.assertIn("FLAG", o)

    def test_prepare_prints_card_with_code(self):
        o = out(["prepare", "7"], lambda r: {**BASE, "status": "prepared", "approval_code": "4821"})
        self.assertIn("Send 4821", o); self.assertIn("Nothing has been lodged", o); self.assertIn("$90.00", o)
        o = out(["prepare", "7"], lambda r: {**BASE, "patient_known": False, "approval_code": "1111"})
        self.assertIn("NOT a known family name", o)

    def test_submit_and_allow(self):
        self.assertIn("Claim_9", out(["submit", "7", "--code", "4821"], lambda r: {**BASE, "peoplecare_ref": "Claim_9"}))
        self.assertIn("Claims now ready: #7", out(["allow", "add", "X"], lambda r: {"provider": "X", "now_ready": [7]}))
        self.assertIn("ask for approval again", out(["allow", "remove", "X"], lambda r: {"removed": "X"}))
        self.assertIn("- A", out(["allow", "list"], lambda r: [{"name": "A"}]))

    def test_status_signed_out(self):
        self.assertIn("NOT signed in", out(["status"], lambda r: {"signed_in": False}))

    def test_ask_roundtrip_and_errors(self):
        q = tempfile.mkdtemp(); os.makedirs(q + "/in"); os.makedirs(q + "/out")
        import json
        def sleeper(_):
            f = os.listdir(q + "/in")[0]
            json.dump({"ok": False, "error": "no"}, open(q + "/out/" + f, "w"))
        with self.assertRaises(c.ClaimsError): c.ask({"op": "status"}, queue=q, timeout=5, sleep=sleeper)
        with self.assertRaises(c.ClaimsError): c.ask({"op": "status"}, queue=q + "/none", timeout=1)


if __name__ == "__main__":
    unittest.main()
