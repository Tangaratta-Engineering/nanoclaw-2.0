import json, os, sys, tempfile, unittest
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import notion_db as d
from notion_core import NotionError

DB = "0123abcd-0123-abcd-0123-abcd0123abcd"
DS = "ffffabcd-0123-abcd-0123-abcd0123abcd"
SCHEMA = {"Item": {"type": "title"}, "Person": {"type": "select", "select": {"options": [{"name": "George"}]}},
          "Packed": {"type": "checkbox"}, "Due": {"type": "date"}, "Qty": {"type": "number"}, "Tags": {"type": "multi_select", "multi_select": {"options": []}}}


def server(calls, extra=None):
    routes = {
        ("GET", f"/v1/databases/{DB}"): (200, {"data_sources": [{"id": DS}]}),
        ("GET", f"/v1/data_sources/{DS}"): (200, {"properties": SCHEMA}),
        ("POST", "/v1/pages"): (200, {"id": "row1", "url": "u"}),
        ("POST", "/v1/databases"): (200, {"id": DB, "url": "u", "data_sources": [{"id": DS}]}),
        ("PATCH", f"/v1/data_sources/{DS}"): (200, {}),
        ("PATCH", "/v1/pages/" + DB): (200, {}),
        ("GET", "/v1/pages/" + DB): (200, {"parent": {"data_source_id": DS}}),
        ("POST", f"/v1/data_sources/{DS}/query"): (200, {"results": [{"id": "r1", "properties": {
            "Item": {"type": "title", "title": [{"plain_text": "Passport"}]}, "Packed": {"type": "checkbox", "checkbox": False},
            "Due": {"type": "date", "date": {"start": "2026-10-30", "end": None}}}}], "has_more": False}),
    }
    routes.update(extra or {})

    def run(cmd, input=None, **kw):
        method = cmd[cmd.index("-X") + 1]
        path = [c for c in cmd if c.startswith("https://api.notion.com")][0].replace("https://api.notion.com", "")
        calls.append((method, path, json.loads(input) if input else None))
        code, body = routes[(method, path)]
        return NS(returncode=0, stdout=json.dumps(body) + "\n" + str(code), stderr="")
    return run


class T(unittest.TestCase):
    def test_columns(self):
        c = d.parse_columns("Person:select(George|Emily), Packed:checkbox, Qty:number, Notes:text")
        self.assertEqual(list(c)[0], "Name")  # title added when missing
        self.assertEqual(c["Person"]["select"]["options"], [{"name": "George"}, {"name": "Emily"}])
        self.assertEqual(c["Notes"]["type"], "rich_text")
        with self.assertRaises(NotionError):
            d.parse_column("Bad:rocket")

    def test_create(self):
        calls = []
        out = d.db_create(NS(parent=DB, title="Pack", columns="Item:title,Done:checkbox"), server(calls))
        self.assertIn(f"data source {DS}", out)
        self.assertEqual(calls[0][2]["parent"]["page_id"], DB)
        self.assertIn("Done", calls[0][2]["initial_data_source"]["properties"])

    def test_add_row_converts_types(self):
        calls = []
        d.db_add_row(NS(db=DB, set=["Item=Passport", "Packed=yes", "Qty=2", "Due=2026-10-30", "Person=George", "Tags=a|b"], body_file=None), server(calls))
        props = calls[-1][2]["properties"]
        self.assertEqual(calls[-1][2]["parent"]["data_source_id"], DS)
        self.assertEqual(props["Packed"], {"checkbox": True})
        self.assertEqual(props["Qty"], {"number": 2})
        self.assertEqual(props["Due"], {"date": {"start": "2026-10-30", "end": None}})
        self.assertEqual(props["Tags"], {"multi_select": [{"name": "a"}, {"name": "b"}]})

    def test_unknown_column(self):
        with self.assertRaises(NotionError) as c:
            d.db_add_row(NS(db=DB, set=["Nope=1"], body_file=None), server([]))
        self.assertIn("columns:", str(c.exception))

    def test_bulk_reports_failures(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([{"Item": "a"}, {"Bogus": "x"}], f)
        out = d.db_add_rows(NS(db=DB, file=f.name), server([]))
        self.assertIn("Added 1 of 2", out); self.assertIn("row 2", out)

    def test_query_filters_and_render(self):
        calls = []
        out = d.db_query(NS(db=DB, where=["Packed=false", "Due<2026-11-01"], sort="Due:desc", limit=5), server(calls))
        body = calls[-1][2]
        self.assertEqual(body["filter"]["and"][0], {"property": "Packed", "checkbox": {"equals": False}})
        self.assertEqual(body["filter"]["and"][1], {"property": "Due", "date": {"before": "2026-11-01"}})
        self.assertEqual(body["sorts"], [{"property": "Due", "direction": "descending"}])
        self.assertIn("Item=Passport; Packed=no; Due=2026-10-30", out)

    def test_update_row_and_alter(self):
        calls = []
        d.db_update_row(NS(row=DB, set=["Packed=true"]), server(calls))
        self.assertEqual(calls[-1][2], {"properties": {"Packed": {"checkbox": True}}})
        with self.assertRaises(NotionError):
            d.db_alter(NS(db=DB, add=None, rename=None, remove=["Qty"], yes_remove=False), server([]))
        calls = []
        d.db_alter(NS(db=DB, add=["Notes:text"], rename=["Qty=Count"], remove=["Tags"], yes_remove=True), server(calls))
        self.assertEqual(calls[-1][2]["properties"], {"Notes": {"type": "rich_text", "rich_text": {}}, "Qty": {"name": "Count"}, "Tags": None})


if __name__ == "__main__":
    unittest.main()
