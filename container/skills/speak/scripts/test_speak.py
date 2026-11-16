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
        self.assertIn("one thousand seven hundred and eighty-nine dollars", out)
        self.assertIn("one thousand eight hundred and twenty-two dollars", out)

    def test_numbers_are_written_out_the_australian_way(self):
        c = speak.clean_for_speech
        self.assertEqual(c("It is $1,200"), "It is one thousand two hundred dollars.")
        self.assertIn("fourteen dollars and ninety-nine cents", c("Dettol is $14.99"))
        self.assertIn("one dollar", c("just $1"))
        self.assertIn("two thousand and fifty dollars", c("$2,050"))
        self.assertIn("one million two hundred and thirty-four thousand five hundred and sixty-seven", c("1,234,567 steps"))
        self.assertIn("1200", c("room 1200"))                 # no comma: left to the engine
        self.assertIn("2026", c("in 2026"))                    # years stay digits
        self.assertIn("3.5", c("version 3.5"))                 # decimals untouched
        self.assertIn("1,2", c("grid 1,2"))                    # not a thousands group

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
