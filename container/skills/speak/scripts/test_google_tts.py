"""Run: python3 container/skills/speak/scripts/test_google_tts.py"""
import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import google_tts as g  # noqa: E402

spec = importlib.util.spec_from_file_location("speak", os.path.join(HERE, "speak.py"))
speak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(speak)

OGG = b"OggS" + b"\0" * 40


def ok_runner(body_audio=OGG):
    def run(cmd, input=None, **kw):
        run.sent = json.loads(input)
        return NS(returncode=0, stdout=json.dumps({"audioContent": base64.b64encode(body_audio).decode()}) + "\n200", stderr="")
    return run


def fail_runner(returncode=0, stdout="", stderr=""):
    return lambda cmd, input=None, **kw: NS(returncode=returncode, stdout=stdout, stderr=stderr)


class Synthesize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "a.ogg")

    def test_success_writes_ogg_and_sends_the_right_request(self):
        r = ok_runner()
        g.synthesize("Hello there.", "en-US-Chirp3-HD-Aoede", self.out, runner=r)
        self.assertEqual(open(self.out, "rb").read(), OGG)
        self.assertEqual(r.sent["voice"], {"languageCode": "en-US", "name": "en-US-Chirp3-HD-Aoede"})
        self.assertEqual(r.sent["audioConfig"]["audioEncoding"], "OGG_OPUS")

    def test_every_failure_is_a_googletts_error(self):
        cases = {
            "timeout": fail_runner(returncode=28),
            "network": fail_runner(returncode=6, stderr="Could not resolve host"),
            "forbidden": fail_runner(stdout=json.dumps({"error": {"status": "PERMISSION_DENIED"}}) + "\n403"),
            "bad key": fail_runner(stdout=json.dumps({"error": {"status": "INVALID_ARGUMENT"}}) + "\n400"),
            "server": fail_runner(stdout="{}\n503"),
            "quota": fail_runner(stdout=json.dumps({"error": {"status": "RESOURCE_EXHAUSTED"}}) + "\n429"),
            "junk": fail_runner(stdout="<html>\n200"),
            "empty audio": fail_runner(stdout=json.dumps({}) + "\n200"),
            "not ogg": fail_runner(stdout=json.dumps({"audioContent": base64.b64encode(b"RIFFxxxx").decode()}) + "\n200"),
        }
        for name, runner in cases.items():
            with self.subTest(name), self.assertRaises(g.GoogleTtsError):
                g.synthesize("Hi.", "en-US-Chirp3-HD-Aoede", self.out, runner=runner)

    def test_quota_message_is_clear(self):
        with self.assertRaises(g.GoogleTtsError) as cm:
            g.synthesize("Hi.", "en-US-Chirp3-HD-Aoede", self.out, runner=fail_runner(stdout="{}\n429"))
        self.assertIn("quota", str(cm.exception))

    def test_no_secret_in_the_request(self):
        r = ok_runner()
        seen = {}
        def run(cmd, input=None, **kw):
            seen["cmd"] = cmd
            return r(cmd, input=input)
        g.synthesize("Hi.", "en-US-Chirp3-HD-Aoede", self.out, runner=run)
        joined = " ".join(seen["cmd"]).lower()
        for word in ("key", "bearer", "authorization", "token"):
            self.assertNotIn(word, joined.replace("content-type", ""))


def make_wav(path, n, rate=24000):
    import wave as w
    with w.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate)
        f.writeframes(b"\x01\x00" * n)
    return open(path, "rb").read()


class Chunking(unittest.TestCase):
    LONG = " ".join(f"This is sentence number {i} and it has a few more words in it." for i in range(20))

    def test_split_at_sentence_ends_around_the_target(self):
        chunks = g.split_for_google(self.LONG, 320)
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(c.endswith(".") for c in chunks))
        self.assertTrue(all(len(c) <= 330 for c in chunks))
        self.assertEqual(" ".join(chunks).replace("  ", " "), self.LONG)

    def test_short_text_is_one_chunk_and_run_on_text_is_cut_at_spaces(self):
        self.assertEqual(g.split_for_google("Hello there."), ["Hello there."])
        run_on = "word " * 200
        parts = g.split_for_google(run_on, 100)
        self.assertGreater(len(parts), 5)
        self.assertTrue(all(len(p) <= 160 for p in parts))

    def test_long_text_is_synthesised_in_parallel_chunks_joined_in_order_and_encoded(self):
        tmp = tempfile.mkdtemp()
        sent = []
        def run(cmd, input=None, **kw):
            body = json.loads(input)
            sent.append((body["input"]["text"], body["audioConfig"]["audioEncoding"]))
            n = 100 + len(sent) * 0 + len(body["input"]["text"])  # frames proportional to the chunk's length
            wav = make_wav(os.path.join(tmp, f"p{len(sent)}.wav"), n)
            return NS(returncode=0, stdout=json.dumps({"audioContent": base64.b64encode(wav).decode()}) + "\n200", stderr="")
        seen = {}
        def encoder(wav, out):
            import wave as w
            with w.open(wav, "rb") as f:
                seen["frames"] = f.getnframes()
            open(out, "wb").write(b"OggS" + b"\0")
        out = os.path.join(tmp, "o.ogg")
        g.synthesize(self.LONG, "en-US-Chirp3-HD-Aoede", out, runner=run, encoder=encoder)
        self.assertGreater(len(sent), 2)
        self.assertTrue(all(enc == "LINEAR16" for _, enc in sent))
        self.assertEqual(seen["frames"], sum(100 + len(t) for t, _ in sent))
        self.assertTrue(open(out, "rb").read().startswith(b"OggS"))

    def test_a_failing_chunk_fails_the_whole_request(self):
        def run(cmd, input=None, **kw):
            return NS(returncode=0, stdout="{}\n503", stderr="")
        with self.assertRaises(g.GoogleTtsError):
            g.synthesize(self.LONG, "en-US-Chirp3-HD-Aoede", "/tmp/never.ogg", runner=run, encoder=lambda a, b: None)

    def test_without_an_encoder_long_text_is_one_ogg_request(self):
        r = ok_runner()
        tmp = os.path.join(tempfile.mkdtemp(), "o.ogg")
        g.synthesize(self.LONG, "en-US-Chirp3-HD-Aoede", tmp, runner=r)
        self.assertEqual(r.sent["audioConfig"]["audioEncoding"], "OGG_OPUS")
        self.assertEqual(r.sent["input"]["text"], self.LONG)


class Budget(unittest.TestCase):
    def setUp(self):
        self.usage = os.path.join(tempfile.mkdtemp(), "usage.json")

    def test_counts_per_month_and_stops_at_the_limit(self):
        now = 1_793_000_000  # a fixed day
        g.record_usage(500, self.usage, now)
        g.record_usage(250, self.usage, now)
        self.assertEqual(g.used_this_month(self.usage, now), 750)
        g.check_budget(100, self.usage, limit=1000, now=now)
        with self.assertRaises(g.GoogleTtsError):
            g.check_budget(300, self.usage, limit=1000, now=now)

    def test_a_new_month_starts_at_zero(self):
        g.record_usage(900, self.usage, 1_793_000_000)
        self.assertEqual(g.used_this_month(self.usage, 1_793_000_000 + 40 * 86400), 0)

    def test_unwritable_counter_never_blocks_speech(self):
        g.record_usage(10, "/proc/definitely/not/writable.json")  # must not raise


class SpeakLevel(unittest.TestCase):
    """The provider choice, voices.json compatibility and the fallback, with Piper and Google stubbed."""

    CFG = {"default": "en_US-hfc_female-medium", "Tiff": {"provider": "google", "voice": "en-US-Chirp3-HD-Aoede", "fallback": "en_US-hfc_female-medium"},
           "Jimmy": "en_US-ryan-medium"}

    def test_string_entries_still_mean_piper(self):
        self.assertEqual(speak.resolve_voice(None, self.CFG, "Jimmy"), ("piper", "en_US-ryan-medium", None))
        self.assertEqual(speak.resolve_voice(None, self.CFG, "Nobody"), ("piper", "en_US-hfc_female-medium", None))

    def test_object_entry_is_google_with_its_fallback(self):
        self.assertEqual(speak.resolve_voice(None, self.CFG, "Tiff"), ("google", "en-US-Chirp3-HD-Aoede", "en_US-hfc_female-medium"))

    def test_overrides(self):
        self.assertEqual(speak.resolve_voice("piper:en_GB-alan-medium", self.CFG, "Tiff"), ("piper", "en_GB-alan-medium", None))
        self.assertEqual(speak.resolve_voice("en_GB-alan-medium", self.CFG, "Tiff"), ("piper", "en_GB-alan-medium", None))
        self.assertEqual(speak.resolve_voice("google:en-GB-Chirp3-HD-Zephyr", self.CFG, "Tiff"), ("google", "en-GB-Chirp3-HD-Zephyr", "en_US-hfc_female-medium"))

    def test_download_list_includes_fallbacks_only_as_piper_ids(self):
        self.assertEqual(speak.piper_ids(self.CFG), {"en_US-hfc_female-medium", "en_US-ryan-medium"})

    def run_speak(self, google_error=None, budget_error=None):
        calls = []
        orig_piper, orig_syn, orig_budget, orig_rec, orig_secs = speak.synth_piper, g.synthesize, g.check_budget, g.record_usage, speak.ogg_seconds
        speak.synth_piper = lambda text, voice, out: calls.append(("piper", voice)) or 3.0
        speak.ogg_seconds = lambda p: 5.0
        def syn(text, voice, out, runner=None, encoder=None):
            calls.append(("google", voice))
            if google_error:
                raise g.GoogleTtsError(google_error)
        g.synthesize = syn
        g.check_budget = lambda chars, *a, **k: (_ for _ in ()).throw(g.GoogleTtsError(budget_error)) if budget_error else None
        g.record_usage = lambda chars, *a, **k: calls.append(("count", chars))
        try:
            res = speak.speak("Hello there.", "google", "en-US-Chirp3-HD-Aoede", "en_US-hfc_female-medium", "/tmp/x.ogg")
        finally:
            speak.synth_piper, g.synthesize, g.check_budget, g.record_usage, speak.ogg_seconds = orig_piper, orig_syn, orig_budget, orig_rec, orig_secs
        return res, calls

    def test_google_success(self):
        res, calls = self.run_speak()
        self.assertEqual(res, (5.0, "google", "en-US-Chirp3-HD-Aoede", False))
        self.assertIn(("count", len("Hello there.")), calls)
        self.assertNotIn(("piper", "en_US-hfc_female-medium"), calls)

    def test_network_outage_invalid_key_and_quota_fall_back_to_piper(self):
        for reason in ("network error: Could not resolve host", "HTTP 400: API_KEY_INVALID", "quota exceeded (HTTP 429)"):
            res, calls = self.run_speak(google_error=reason)
            self.assertEqual(res, (3.0, "piper", "en_US-hfc_female-medium", True), reason)
            self.assertNotIn("count", [c[0] for c in calls])  # a failed call is not counted

    def test_monthly_limit_falls_back_without_calling_google(self):
        res, calls = self.run_speak(budget_error="monthly character limit reached")
        self.assertEqual(res[1:], ("piper", "en_US-hfc_female-medium", True))
        self.assertNotIn("google", [c[0] for c in calls])


class WorkerProtocol(unittest.TestCase):
    """google_server.handle: one JSON line out per request, with the shared counter."""

    def test_success_and_error_lines(self):
        import io, contextlib
        spec2 = importlib.util.spec_from_file_location("google_server", os.path.join(HERE, "google_server.py"))
        gs = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(gs)
        usage = os.path.join(tempfile.mkdtemp(), "u.json")
        orig = (g.synthesize, g.check_budget, g.record_usage)
        counted = []
        g.synthesize = lambda text, voice, out, **kw: open(out, "wb").write(b"OggS")
        g.check_budget = lambda chars, *a, **k: None
        g.record_usage = lambda chars, *a, **k: counted.append(chars)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                gs.handle({"id": 1, "text": "Hello.", "out": os.path.join(os.path.dirname(usage), "o.ogg")}, "en-US-Chirp3-HD-Aoede")
                g.synthesize = lambda *a, **k: (_ for _ in ()).throw(g.GoogleTtsError("quota exceeded (HTTP 429)"))
                gs.handle({"id": 2, "text": "Again.", "out": "/tmp/x.ogg"}, "en-US-Chirp3-HD-Aoede")
        finally:
            g.synthesize, g.check_budget, g.record_usage = orig
        lines = [json.loads(l) for l in buf.getvalue().splitlines()]
        self.assertEqual(lines[0]["id"], 1); self.assertIn("path", lines[0])
        self.assertEqual(lines[1]["id"], 2); self.assertIn("quota", lines[1]["error"])
        self.assertEqual(counted, [6])  # only the successful request is counted


if __name__ == "__main__":
    unittest.main()
