#!/usr/bin/env python3
"""Tests for the nutri-skill AI estimation (the claude CLI is faked; no network). Run: python3 test_ai_estimate.py"""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai_estimate as a

GOOD = json.dumps({"product_name": "Toast", "serving_type": "per_serving", "kcal": "190", "protein_g": 6, "fat_g": 4, "carbs_g": 30})


def fake(result, rc=0, is_error=False, stderr=""):
    def run(cmd, input=None, cwd=None, env=None, **kw):
        run.cmd, run.input, run.cwd, run.env = cmd, input, cwd, env or {}
        run.files = sorted(os.listdir(cwd)) if cwd and os.path.isdir(cwd) else []
        return subprocess.CompletedProcess(cmd, rc, stdout=json.dumps({"type": "result", "is_error": is_error, "result": result}), stderr=stderr)
    return run


class Estimate(unittest.TestCase):
    def test_text_estimate_uses_claude_with_no_tools_and_parses(self):
        run = fake("Here you go:\n" + GOOD)
        d = a.call_text_estimation("two slices of toast", runner=run)
        self.assertEqual(d["kcal"], 190.0)
        self.assertEqual(run.cmd[:2], ["claude", "-p"])
        self.assertIn("--tools", run.cmd)
        self.assertEqual(run.cmd[run.cmd.index("--tools") + 1], "")  # no tools: a plain model call
        self.assertIn("two slices of toast", run.input)
        self.assertNotIn("--allowedTools", run.cmd)

    def test_vision_gives_claude_the_image_file_and_only_the_read_tool(self):
        run = fake(GOOD)
        a.call_vision(b"\x89PNG\r\n\x1a\nxxxx", runner=run)
        self.assertEqual(run.files, ["label.png"])
        self.assertEqual(run.cmd[run.cmd.index("--tools") + 1], "Read")
        self.assertIn("./label.png", run.input)

    def test_a_placeholder_sign_in_is_supplied_when_the_shell_has_none(self):
        saved = {k: os.environ.pop(k, None) for k in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        try:
            run = fake(GOOD)
            a.call_text_estimation("x", runner=run)
            self.assertEqual(run.env.get("CLAUDE_CODE_OAUTH_TOKEN"), a.PLACEHOLDER)
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "already-set"
            run2 = fake(GOOD)
            a.call_text_estimation("x", runner=run2)
            self.assertEqual(run2.env.get("CLAUDE_CODE_OAUTH_TOKEN"), "already-set")  # an existing one is never replaced
        finally:
            os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_sign_in_failure_names_the_cause(self):
        run = fake("Invalid API key · Please run /login", rc=1, is_error=True)
        with self.assertRaisesRegex(a.EstimateError, "sign in.*George"):
            a.call_text_estimation("x", runner=run)

    def test_other_failures(self):
        with self.assertRaisesRegex(a.EstimateError, "did not return JSON"):
            a.call_text_estimation("x", runner=fake("sorry, I cannot help"))
        with self.assertRaisesRegex(a.EstimateError, "Missing required"):
            a.call_text_estimation("x", runner=fake('{"kcal": 5}'))
        with self.assertRaisesRegex(a.EstimateError, "Empty"):
            a.call_text_estimation("x", runner=fake("  "))

        def gone(cmd, **kw):
            raise FileNotFoundError()

        with self.assertRaisesRegex(a.EstimateError, "not installed"):
            a.call_text_estimation("x", runner=gone)


if __name__ == "__main__":
    unittest.main()
