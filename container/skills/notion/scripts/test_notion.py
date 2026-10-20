import json, os, sys, unittest
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(__file__))
import notion

UUID = "0123abcd-0123-abcd-0123-abcd0123abcd"


def fake(responses, calls):
    def run(cmd, input=None, **kw):
        calls.append((cmd, json.loads(input) if input else None))
        code, body = responses.pop(0)
        return SimpleNamespace(returncode=0, stdout=json.dumps(body) + "\n" + str(code), stderr="")
    return run


class T(unittest.TestCase):
    def test_ids(self):
        for ref in ["0123abcd0123abcd0123abcd0123abcd", UUID,
                    "https://www.notion.so/My-Page-Title-0123abcd0123abcd0123abcd0123abcd?pvs=4",
                    "https://www.notion.so/ws/0123abcd0123abcd0123abcd0123abcd"]:
            self.assertEqual(notion.page_id(ref), UUID)
        with self.assertRaises(notion.NotionError):
            notion.page_id("nope")

    def test_get_and_notes(self):
        calls = []
        run = fake([(200, {"markdown": "# Hi", "truncated": True, "unknown_block_ids": [], "warnings": []})], calls)
        out = notion.fmt_markdown(notion.request("GET", "/x", None, run))
        self.assertIn("# Hi", out); self.assertIn("truncated", out)
        self.assertIn("Notion-Version: 2026-03-11", calls[0][0])

    def test_create_fallback(self):
        calls = []
        run = fake([(400, {"code": "validation_error", "message": "bad"}),
                    (200, {"id": "p1", "url": "u", "properties": {"title": {"type": "title", "title": [{"plain_text": "T"}]}}})], calls)
        a = SimpleNamespace(parent=UUID, title="T", file=None)
        import io; sys.stdin = io.StringIO("body")
        self.assertIn("Created: T | p1", notion.cmd_create(a, run))
        self.assertEqual(calls[1][1]["markdown"], "# T\n\nbody")
        self.assertNotIn("properties", calls[1][1])

    def test_errors_have_hints(self):
        run = fake([(404, {"code": "object_not_found", "message": "nope"})], [])
        with self.assertRaises(notion.NotionError) as c:
            notion.request("GET", "/x", None, run)
        self.assertIn("Connections", str(c.exception))

    def test_replace_requires_flag(self):
        with self.assertRaises(notion.NotionError):
            notion.cmd_replace(SimpleNamespace(page=UUID, file=None, yes_overwrite=False), None)

    def test_edit_body(self):
        calls = []
        run = fake([(200, {"markdown": "", "warnings": [{"code": "no_match", "message": "m"}]})], calls)
        out = notion.cmd_edit(SimpleNamespace(page=UUID, old="a", new="b", all=False), run)
        self.assertIn("no_match", out)
        self.assertEqual(calls[0][1]["update_content"]["content_updates"][0]["old_str"], "a")


if __name__ == "__main__":
    unittest.main()
