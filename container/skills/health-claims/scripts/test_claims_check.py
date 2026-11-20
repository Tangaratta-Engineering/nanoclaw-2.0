#!/usr/bin/env python3
"""Tests for claims-check (no Gmail needed). Run: python3 test_claims_check.py"""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest

here = os.path.dirname(os.path.abspath(__file__))
loader = importlib.machinery.SourceFileLoader("claims_check", os.path.join(here, "claims-check"))
spec = importlib.util.spec_from_loader("claims_check", loader)
cc = importlib.util.module_from_spec(spec)
loader.exec_module(cc)


class T(unittest.TestCase):
    def test_baseline_then_only_new(self):
        st = os.path.join(tempfile.mkdtemp(), "seen.json")
        r = cc.check(call=lambda m, p: {"messages": [{"id": "a"}, {"id": "b"}]}, state=st)
        self.assertEqual(r, {"wakeAgent": False, "data": {"baseline": 2}})
        r = cc.check(call=lambda m, p: {"messages": [{"id": "a"}, {"id": "c"}]}, state=st)
        self.assertEqual(r, {"wakeAgent": True, "data": {"new_email_ids": ["c"]}})
        r = cc.check(call=lambda m, p: {"messages": [{"id": "a"}, {"id": "c"}]}, state=st)
        self.assertFalse(r["wakeAgent"])

    def test_error_does_not_wake(self):
        def boom(m, p): raise RuntimeError("gmail down")
        self.assertFalse(cc.check(call=boom, state=os.path.join(tempfile.mkdtemp(), "s.json"))["wakeAgent"])


if __name__ == "__main__":
    unittest.main()
