import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(__file__))
import xlsx_tool as x

try:
    x.load_openpyxl()
    HAVE = True
except x.XlsxError:
    HAVE = False

SPEC = {"sheets": [{"name": "Budget", "columns": [{"header": "Item"}, {"header": "Cost", "format": "$#,##0.00"}, {"header": "Due", "type": "date"}],
                    "rows": [["Rent", 1200, "2026-11-01"], ["Power", 180.5, "2026-11-15"]], "totals": {"columns": ["B"]}}]}


@unittest.skipUnless(HAVE, "openpyxl not installed")
class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.out = os.path.join(self.d, "b.xlsx")

    def test_build_and_inspect(self):
        r = x.build(SPEC, self.out)
        self.assertEqual(r["sheets"], ["Budget"])
        self.assertEqual(r["formulas"], 1)
        rows = x.inspect(self.out)[0]["rows"]
        self.assertEqual(rows[0], ["Item", "Cost", "Due"])
        self.assertEqual(rows[3][1], "=SUM(B2:B3)")

    def test_dates_are_real_dates_and_formatted(self):
        x.build(SPEC, self.out)
        import openpyxl
        c = openpyxl.load_workbook(self.out)["Budget"]["C2"]
        self.assertEqual(c.number_format, "yyyy-mm-dd")
        self.assertEqual(c.value.year, 2026)

    def test_bad_date_rejected(self):
        bad = json.loads(json.dumps(SPEC))
        bad["sheets"][0]["rows"][0][2] = "1/11/2026"
        with self.assertRaises(x.XlsxError):
            x.build(bad, self.out)

    def test_bad_sheet_name(self):
        for n in ["", "a/b", "x" * 32]:
            with self.assertRaises(x.XlsxError):
                x.build({"sheets": [{"name": n, "rows": [[1]]}]}, self.out)

    def test_check_clean(self):
        x.build(SPEC, self.out)
        self.assertTrue(x.check(self.out)["ok"])

    def test_check_flags_problems(self):
        spec = {"sheets": [{"name": "My Data", "rows": [[1, 2, "=A1/0", "=TEXTJOIN(\",\",TRUE,A1:B1)", "=SUM(Nope!A1)", "=My Data!A1", "12"]]},
                           {"name": "Calc", "rows": [["=XLOOKUP(1,A1,B1)"]]}]}
        x.build(spec, self.out)
        res = x.check(self.out)
        text = " ".join(res["problems"] + res["warnings"])
        self.assertFalse(res["ok"])
        for want in ["divides by a literal zero", "TEXTJOIN needs the _xlfn.", "missing sheet 'Nope'", "must be quoted", "spills", "number stored as text"]:
            self.assertIn(want, text)

    def test_csv(self):
        p = os.path.join(self.d, "t.csv")
        open(p, "w").write("a,b\nx,1\ny,2.5\n")
        spec = x.to_csv_spec(p)
        self.assertEqual(spec["sheets"][0]["rows"], [["x", 1], ["y", 2.5]])

    def test_cli_exit_codes(self):
        self.assertEqual(x.main(["check", os.path.join(self.d, "missing.xlsx")]), 2)
        self.assertEqual(x.main(["build", "s.json", os.path.join(self.d, "o.txt")]), 2)


if __name__ == "__main__":
    unittest.main()
