import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(__file__))
import publish as P


class T(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.src = tempfile.mkdtemp()
        with open(os.path.join(self.src, "index.html"), "w") as f:
            f.write("<h1>Trip</h1>")

    def test_put_private_and_list(self):
        out = P.put(self.root, "Tasmania Trip", self.src, "jack")
        self.assertEqual(out["name"], "tasmania-trip")
        self.assertTrue(out["url"].endswith("/tasmania-trip/"))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "tasmania-trip", "index.html")))
        self.assertEqual(P.listing(self.root)[0]["by"], "jack")

    def test_single_file_becomes_index(self):
        f = os.path.join(self.src, "index.html")
        P.put(self.root, "page-one", f, "tiff")
        self.assertTrue(os.path.isfile(os.path.join(self.root, "page-one", "index.html")))

    def test_other_agent_cannot_overwrite(self):
        P.put(self.root, "plan", self.src, "jack")
        with self.assertRaises(P.PublishError):
            P.put(self.root, "plan", self.src, "tiff")
        P.put(self.root, "plan", self.src, "jack")  # the owner can update

    def test_rejects_bad_names_files_and_links(self):
        with self.assertRaises(P.PublishError):
            P.slug("../etc")
        open(os.path.join(self.src, "run.sh"), "w").write("x")
        with self.assertRaises(P.PublishError):
            P.put(self.root, "bad-page", self.src, "jack")
        os.remove(os.path.join(self.src, "run.sh"))
        os.symlink("/etc/passwd", os.path.join(self.src, "a.txt"))
        with self.assertRaises(P.PublishError):
            P.put(self.root, "bad-page", self.src, "jack")

    def test_public_needs_confirmation_and_matching_content(self):
        P.put(self.root, "trip", self.src, "jack")
        calls = []
        api = lambda m, u, b=None, c="application/json": (calls.append((m, u)) or {"id": "s1", "ssl_url": "https://gc-trip.netlify.app"})
        req = P.public_request(self.root, "trip")
        with self.assertRaises(P.PublishError):
            P.public_confirm(self.root, "trip", "bogus", api=api)
        self.assertEqual(calls, [])
        out = P.public_confirm(self.root, "trip", req["code"], api=api)
        self.assertEqual(out["public_url"], "https://gc-trip.netlify.app")
        self.assertEqual([c[0] for c in calls], ["POST", "POST"])
        with self.assertRaises(P.PublishError):  # a code works once
            P.public_confirm(self.root, "trip", req["code"], api=api)

    def test_changed_content_voids_the_code(self):
        P.put(self.root, "trip", self.src, "jack")
        req = P.public_request(self.root, "trip")
        open(os.path.join(self.root, "trip", "index.html"), "w").write("<h1>Changed</h1>")
        with self.assertRaises(P.PublishError):
            P.public_confirm(self.root, "trip", req["code"], api=lambda *a, **k: {})

    def test_expired_code(self):
        P.put(self.root, "trip", self.src, "jack")
        req = P.public_request(self.root, "trip", now=1000)
        with self.assertRaises(P.PublishError):
            P.public_confirm(self.root, "trip", req["code"], now=1000 + P.CODE_TTL + 1, api=lambda *a, **k: {})

    def test_scan_flags_personal_details(self):
        open(os.path.join(self.src, "index.html"), "w").write("Call 0412 345 678 or mail a.b@example.com")
        P.put(self.root, "contact", self.src, "tiff")
        found = P.public_request(self.root, "contact")["possibly_sensitive"]
        self.assertIn("email address", found)
        self.assertIn("phone number", found)

    def test_remove_refuses_while_public(self):
        P.put(self.root, "trip", self.src, "jack")
        meta = P.load_meta(self.root)
        meta["pages"]["trip"]["public_url"] = "https://x.netlify.app"
        P.save_meta(self.root, meta)
        with self.assertRaises(P.PublishError):
            P.remove(self.root, "trip", "jack")


if __name__ == "__main__":
    unittest.main()
