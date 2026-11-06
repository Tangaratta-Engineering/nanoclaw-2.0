import datetime, io, json, os, sys, unittest, urllib.error
sys.path.insert(0, os.path.dirname(__file__))
import discord_history as dh

NOW = datetime.datetime(2026, 11, 6, 12, 0, tzinfo=datetime.timezone.utc)


def msg(i, hours_ago, who, text, type_=0, bot=False, **kw):
    t = (NOW - datetime.timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
    return {"id": str(i), "timestamp": t, "type": type_, "content": text,
            "author": {"username": who.lower(), "global_name": who, "bot": bot}, "attachments": [], "embeds": [], **kw}


CHAT = [  # newest first, as Discord returns it
    msg(9, 1, "Tiff", "Reminder: bins out tonight", bot=True),
    msg(8, 2, "firsthalfhero", "can you check flights to Auckland"),
    msg(7, 3, "Jimmy", "Cheapest SYD to AKL on the 4th is $650 return", bot=True),
    msg(6, 3, "Jimmy", "joined", type_=7),
    msg(5, 30, "Jack", "Old thought about stoicism", bot=True),
    msg(4, 80, "Tiff", "Newsletter recap: grandparents day", bot=True, embeds=[{"title": "Week 4", "description": "Summer market form due"}],
        attachments=[{"filename": "form.pdf"}]),
]


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def fake(pages, calls):
    def opener(req, timeout=None):
        calls.append(req.full_url)
        assert "Authorization" not in {k.title() for k in req.headers}      # the gateway adds the token, never this script
        before = req.full_url.split("before=")[1] if "before=" in req.full_url else None
        data = [m for m in pages if before is None or int(m["id"]) < int(before)][:dh.PAGE]
        return Resp(json.dumps(data).encode())
    return opener


class T(unittest.TestCase):
    def run_cli(self, argv, pages=CHAT, opener=None):
        calls, out, err = [], io.StringIO(), io.StringIO()
        real = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        orig = dh.parse_since
        dh.parse_since = lambda t, now=None: orig(t, NOW)
        try:
            code = dh.main(argv, opener=opener or fake(pages, calls), sleep=lambda s: None)
        finally:
            sys.stdout, sys.stderr = real
            dh.parse_since = orig
        return code, out.getvalue(), err.getvalue(), calls

    def test_history_is_chronological_skips_system_messages_and_shows_cards(self):
        code, out, _, calls = self.run_cli(["history", "--since", "5d"])
        self.assertEqual(code, 0)
        self.assertLess(out.index("Newsletter recap"), out.index("bins out"))
        self.assertNotIn("joined", out)
        self.assertIn("[card] Week 4 - Summer market form due", out)
        self.assertIn("[attachment: form.pdf]", out)
        self.assertIn("/channels/1508404737056182339/messages", calls[0])

    def test_since_stops_paging_at_the_cutoff(self):
        _, out, _, _ = self.run_cli(["history", "--since", "5h"])
        self.assertIn("Cheapest SYD", out)
        self.assertNotIn("Old thought", out)

    def test_from_filters_by_person(self):
        _, out, _, _ = self.run_cli(["history", "--since", "5d", "--from", "Jimmy"])
        self.assertIn("Cheapest", out)
        self.assertNotIn("bins out", out)

    def test_search_needs_all_words_and_can_show_context(self):
        _, out, _, _ = self.run_cli(["search", "flights auckland", "--since", "5d", "--context", "1"])
        self.assertIn("1 message(s) match", out)
        self.assertIn("check flights to Auckland", out)
        self.assertIn("Cheapest SYD", out)                                 # the context line
        _, none, _, _ = self.run_cli(["search", "flights tokyo"])
        self.assertIn("No messages found", none)

    def test_paging_uses_before_and_reports_when_it_hit_the_page_limit(self):
        many = [msg(1000 - i, i / 10, "Tiff", f"m{i}", bot=True) for i in range(250)]
        _, out, _, calls = self.run_cli(["search", "m249", "--since", "30d", "--max-pages", "2"], pages=many)
        self.assertEqual(len(calls), 2)
        self.assertIn("before=", calls[1])
        self.assertIn("searched only part", out)

    def test_long_output_is_cut_with_a_note(self):
        _, out, _, _ = self.run_cli(["history", "--since", "5d", "--max-chars", "120"])
        self.assertIn("older messages cut", out)

    def test_refused_request_says_what_to_tell_george(self):
        def deny(req, timeout=None): raise urllib.error.HTTPError(req.full_url, 403, "x", {}, io.BytesIO(b""))
        code, _, err, _ = self.run_cli(["history"], opener=deny)
        self.assertEqual(code, 2)
        self.assertIn("OneCLI", err)

    def test_rate_limit_is_retried(self):
        n = {"i": 0}
        def flaky(req, timeout=None):
            n["i"] += 1
            if n["i"] == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "x", {}, io.BytesIO(b'{"retry_after": 0.5}'))
            return Resp(json.dumps(CHAT).encode())
        code, out, _, _ = self.run_cli(["history", "--since", "5d"], opener=flaky)
        self.assertEqual(code, 0)
        self.assertIn("bins out", out)

    def test_bad_time_and_unknown_channel(self):
        code, _, err, _ = self.run_cli(["history", "--since", "yesterday-ish"])
        self.assertEqual(code, 2)
        self.assertIn("3d", err)
        with self.assertRaises(SystemExit):
            self.run_cli(["--channel", "tiff-dm", "history"])


if __name__ == "__main__":
    unittest.main()
