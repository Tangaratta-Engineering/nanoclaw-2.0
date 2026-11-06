import io, json, os, sys, unittest, urllib.error
sys.path.insert(0, os.path.dirname(__file__))
import school_posts as sp


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def opener_for(routes, seen):
    def opener(req, timeout=None):
        seen.append((req.get_method(), req.full_url, req.data, dict(req.headers)))
        for key, body in routes.items():
            if key in req.full_url:
                if isinstance(body, int):
                    raise urllib.error.HTTPError(req.full_url, body, "x", {}, None)
                return Resp(json.dumps(body).encode())
        raise AssertionError(req.full_url)
    return opener


POST = {"postId": "p1", "title": "SCHOOL NEWS: Newsletter Week 4", "kind": "newsletter", "groups": ["Orana"], "postedAt": "2026-11-06T00:00:00+00:00",
        "content": "Welcome", "reportedAt": "2026-11-06T01:00:00", "reportedSummary": "Sent: grandparents day recap",
        "documents": [{"name": "Newsletter", "kind": "webpage", "status": "ok", "url": "https://app.smore.com/n/x", "text": "Grandparents morning tea"},
                      {"name": "flyer.png", "kind": "image", "status": "ok", "url": "https://s3/x.png", "text": ""},
                      {"name": "Scan.pdf", "kind": "pdf", "status": "no_text", "url": "https://s3/y.pdf", "text": ""}]}


class T(unittest.TestCase):
    def run_cli(self, argv, routes):
        seen, out, err = [], io.StringIO(), io.StringIO()
        real = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            code = sp.main(argv, opener=opener_for(routes, seen))
        finally:
            sys.stdout, sys.stderr = real
        return code, out.getvalue(), err.getvalue(), seen

    def test_search_prints_hits_and_sends_no_key(self):
        res = {"query": "grandparents", "count": 1, "results": [{**POST, "snippet": "welcome [Grandparents] day"}]}
        code, out, _, seen = self.run_cli(["search", "grandparents", "--kind", "newsletter", "--since", "2026-10-01"], {"/posts/search": res})
        self.assertEqual(code, 0)
        self.assertIn("p1 | 2026-11-06 | newsletter", out)
        self.assertIn("[Grandparents]", out)
        self.assertIn("kind=newsletter", seen[0][1])
        self.assertNotIn("X-api-key", seen[0][3])            # the gateway adds it, never this script

    def test_show_explains_every_document_state(self):
        code, out, _, _ = self.run_cli(["show", "p1"], {"/posts/p1": POST})
        self.assertIn("Grandparents morning tea", out)
        self.assertIn("image: not read", out)
        self.assertIn("no text found", out)
        self.assertIn("What was sent to George", out)

    def test_report_posts_the_summary(self):
        code, out, _, seen = self.run_cli(["report", "p1", "Sent the newsletter recap"], {"/posts/p1/report": {"reported": True}})
        self.assertEqual((code, out.strip()), (0, "recorded"))
        self.assertEqual(json.loads(seen[0][2]), {"summary": "Sent the newsletter recap"})

    def test_missing_key_gives_a_clear_message(self):
        code, _, err, _ = self.run_cli(["latest", "newsletter"], {"/posts/latest": 403})
        self.assertEqual(code, 2)
        self.assertIn("OneCLI", err)

    def test_unknown_post_and_unreachable_service(self):
        code, _, err, _ = self.run_cli(["show", "nope"], {"/posts/nope": 404})
        self.assertEqual((code, "no such post" in err), (2, True))
        def down(req, timeout=None): raise urllib.error.URLError("refused")
        out, e = io.StringIO(), io.StringIO()
        real = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, e
        try:
            code = sp.main(["latest"], opener=down)
        finally:
            sys.stdout, sys.stderr = real
        self.assertEqual(code, 2)
        self.assertIn("cannot reach", e.getvalue())

    def test_unreported_and_empty_search(self):
        code, out, _, _ = self.run_cli(["unreported"], {"/posts/unreported": {"count": 0, "posts": []}})
        self.assertIn("Nothing unreported", out)
        code, out, _, _ = self.run_cli(["search", "zzz"], {"/posts/search": {"query": "zzz", "count": 0, "results": []}})
        self.assertIn("No posts match", out)


if __name__ == "__main__":
    unittest.main()
