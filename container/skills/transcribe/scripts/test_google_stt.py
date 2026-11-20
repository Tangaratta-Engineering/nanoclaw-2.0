#!/usr/bin/env python3
"""Tests for the Google engine of the transcribe skill (no network: curl is faked). Run: python3 test_google_stt.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import google_stt as g

NOW = 1_795_000_000  # 2026-11


def make_wav(seconds):
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(f.name, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * int(16000 * seconds))
    return f.name


def fake_curl(body, code="200"):
    def run(cmd, input=None, **kw):
        run.sent = json.loads(input)
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(body) + "\n" + code, stderr="")
    return run


GOOD = {"results": [{"alternatives": [{"transcript": "add milk to the list", "confidence": 0.93}], "resultEndTime": "2.1s"}],
        "totalBilledTime": "15s"}


class GoogleStt(unittest.TestCase):
    def setUp(self):
        self.usage = os.path.join(tempfile.mkdtemp(), "usage.json")

    def test_phrases_from_vocabulary(self):
        self.assertEqual(g.phrases("Names: Tiff, Timmy, NanoClaw"), ["Tiff", "Timmy", "NanoClaw"])
        self.assertEqual(g.phrases(""), [])

    def test_language_code(self):
        self.assertEqual(g.language_code(None), g.DEFAULT_LANGUAGE)
        self.assertEqual(g.language_code("en"), g.DEFAULT_LANGUAGE)
        self.assertEqual(g.language_code("fr-FR"), "fr-FR")

    def test_request_has_hints_and_model(self):
        r = g.build_request(b"abc", None, ["Tiff"])
        self.assertEqual(r["config"]["speechContexts"][0]["phrases"], ["Tiff"])
        self.assertEqual(r["config"]["model"], g.MODEL)
        self.assertNotIn("speechContexts", g.build_request(b"abc", None, [])["config"])

    def test_success_records_billed_usage(self):
        run = fake_curl(GOOD)
        res = g.transcribe(make_wav(2), None, ["Tiff"], runner=run, usage_path=self.usage, now=NOW)
        self.assertEqual(res["text"], "add milk to the list")
        self.assertEqual(res["confidence"], 0.93)
        self.assertEqual(g.used_seconds(self.usage, NOW), 15)
        self.assertEqual(run.sent["config"]["languageCode"], "en-AU")

    def test_usage_resets_each_month(self):
        g.add_usage(600, self.usage, NOW)
        self.assertEqual(g.used_seconds(self.usage, NOW), 600)
        self.assertEqual(g.used_seconds(self.usage, NOW + 40 * 86400), 0)

    def test_monthly_limit_stops_google(self):
        g.add_usage(300 * 60, self.usage, NOW)
        with self.assertRaisesRegex(g.Unavailable, "limit"):
            g.transcribe(make_wav(1), None, [], runner=fake_curl(GOOD), usage_path=self.usage, now=NOW)

    def test_api_error_is_unavailable_and_not_counted(self):
        run = fake_curl({"error": {"message": "API key not valid"}}, "400")
        with self.assertRaisesRegex(g.Unavailable, "HTTP 400"):
            g.transcribe(make_wav(1), None, [], runner=run, usage_path=self.usage, now=NOW)
        self.assertEqual(g.used_seconds(self.usage, NOW), 0)

    def test_non_wav_and_long_clips_fall_back(self):
        bad = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
        bad.write(b"OggS"); bad.close()
        with self.assertRaises(g.Unavailable):
            g.transcribe(bad.name, None, [], runner=fake_curl(GOOD), usage_path=self.usage, now=NOW)
        with self.assertRaisesRegex(g.Unavailable, "too long"):
            g.transcribe(make_wav(61), None, [], runner=fake_curl(GOOD), usage_path=self.usage, now=NOW)

    def test_no_speech_gives_empty_text(self):
        res = g.parse_response({}, 3.0)
        self.assertEqual(res["text"], "")
        self.assertEqual(res["billed_seconds"], 3)  # no totalBilledTime: the clip length, rounded up

    def test_confidence_folds_into_quality(self):
        self.assertEqual(g.confidence_quality(0.95, "good"), ("good", None))
        self.assertEqual(g.confidence_quality(0.7, "good")[0], "uncertain")
        self.assertEqual(g.confidence_quality(0.4, "good")[0], "poor")
        self.assertEqual(g.confidence_quality(None, "uncertain"), ("uncertain", None))


if __name__ == "__main__":
    unittest.main()
