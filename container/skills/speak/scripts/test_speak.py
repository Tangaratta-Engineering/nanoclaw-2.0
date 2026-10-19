"""Run: python3 -m unittest container/skills/speak/scripts/test_speak.py"""
import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("speak", os.path.join(os.path.dirname(__file__), "speak.py"))
speak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(speak)


class CleanForSpeech(unittest.TestCase):
    def test_markdown_emoji_links_prices(self):
        t = ("**Good news, George!** 🎉 Flights are **$1,789** total — Jetstar out Fri 21:15 "
             "(https://kiwi.com/u/qzzshq). Book soon.\n\n- Option 2: $1,822")
        out = speak.clean_for_speech(t)
        self.assertNotIn("http", out)
        self.assertNotIn("**", out)
        self.assertNotIn("🎉", out)
        self.assertNotIn("(", out)
        self.assertNotIn(" ,", out)
        self.assertIn("1,789 dollars", out)
        self.assertIn("1,822 dollars", out)

    def test_markdown_links_keep_label(self):
        self.assertEqual(speak.clean_for_speech("See [the booking page](https://x.test/a)"), "See the booking page.")

    def test_code_blocks_dropped(self):
        self.assertNotIn("rm -rf", speak.clean_for_speech("Done.\n```\nrm -rf /\n```\nAll good."))

    def test_truncate_at_sentence(self):
        text = "One short sentence. " * 100
        cut, was = speak.truncate(text, 200)
        self.assertTrue(was)
        self.assertTrue(cut.endswith("."))
        self.assertLessEqual(len(cut), 200)

    def test_voice_url(self):
        self.assertTrue(speak.voice_url("en_GB-alan-medium").endswith("/en/en_GB/alan/medium/en_GB-alan-medium"))


if __name__ == "__main__":
    unittest.main()
