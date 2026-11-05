import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(__file__))
import trip_sheet as t
import xlsx_tool as x

try:
    x.load_openpyxl()
    HAVE = True
except x.XlsxError:
    HAVE = False

SPEC = {"trip": "Test", "start_date": "2026-12-20", "travellers": ["A", "B"],
        "days": [{"Morning": "Fly", "Sleep": "Air"}, {"Morning": "Arrive", "Sleep": "Hotel"}, {}],
        "currency": {"home": "AUD", "local": "USD", "rate": 1.5},
        "flights": [{"name": "X", "price_pp": 1000, "chosen": 1}, {"name": "Y", "price_pp": 2000}],
        "hotels": [{"name": "H", "price_per_night": 100, "chosen": 1}],
        "food_per_day": 50, "spending_money": {"A": 10, "B": 10}, "transfers": [{"item": "Taxi", "cost": 40}]}


@unittest.skipUnless(HAVE, "openpyxl not installed")
class T(unittest.TestCase):
    def setUp(self):
        self.out = os.path.join(tempfile.mkdtemp(), "t.xlsx")

    def test_build_layout(self):
        r = t.build(SPEC, self.out)
        self.assertEqual(r["sheets"], ["Itinerary", "Overview", "Flights", "Hotels", "Food & Beverage", "Transfers", "Variables"])
        import openpyxl
        ws = openpyxl.load_workbook(self.out)["Itinerary"]
        self.assertEqual(ws["B1"].value, "=Variables!$B$1")
        self.assertEqual(ws["C1"].value, "=B1+1")
        self.assertEqual(ws["A2"].value, "Day")
        self.assertEqual(ws["B4"].value, "Fly")
        self.assertEqual(ws.freeze_panes, "B4")

    def test_check_clean_and_totals(self):
        t.build(SPEC, self.out)
        res = x.check(self.out)
        self.assertTrue(res["ok"], res["problems"])
        import openpyxl
        wb = openpyxl.load_workbook(self.out)
        self.assertIn("exchange_rate", wb.defined_names)
        self.assertEqual(wb["Overview"]["B6"].value, "=flights_total")

    def test_show_and_set(self):
        t.build(SPEC, self.out)
        t.set_cell(self.out, 3, "Dinner", "Pizza")
        t.set_cell(self.out, 3, "Dinner", "Dessert", append=True)
        text = t.show(self.out)
        self.assertIn("Day 1", text)
        self.assertIn("Dinner: Pizza / Dessert", text)
        with self.assertRaises(t.TripError):
            t.set_cell(self.out, 3, "Nope", "x")
        with self.assertRaises(t.TripError):
            t.set_cell(self.out, 9, "Dinner", "x")

    def test_add_options_links_overview(self):
        t.build(SPEC, self.out)
        t.add_options(self.out, "Rental cars", [{"name": "Hertz", "price": 500, "chosen": 1}], "Price (AUD)", "trip", "1", "AUD")
        import openpyxl
        ov = openpyxl.load_workbook(self.out)["Overview"]
        labels = [ov.cell(row=r, column=1).value for r in range(6, 12)]
        self.assertEqual(labels[-3:], ["Transfers", "Rental cars", "Total"])
        self.assertEqual(ov["B10"].value, "=rental_cars_total")
        self.assertEqual(ov["B11"].value, "=SUM(B6:B10)")
        with self.assertRaises(t.TripError):
            t.add_options(self.out, "Rental cars", [], "P")

    def test_weekend_variant(self):
        spec = {"trip": "Mornington", "start_date": "2026-10-11", "title_row": True, "days": 4,
                "parts": ["Early Morning", "Late Morning", "Lunch", "Early Afternoon", "Late Afternoon", "Dinner"], "tail_rows": []}
        t.build(spec, self.out)
        import openpyxl
        ws = openpyxl.load_workbook(self.out)["Itinerary"]
        self.assertEqual(ws["A1"].value, "Mornington")
        self.assertEqual(ws["A5"].value, "DOW")
        self.assertEqual(ws["A6"].value, "Early Morning")

    def test_bad_input(self):
        with self.assertRaises(t.TripError):
            t.build({"trip": "x", "start_date": "11/2/26", "days": 2}, self.out)
        with self.assertRaises(t.TripError):
            t.build({"trip": "x", "start_date": "2026-01-01", "days": 500}, self.out)


if __name__ == "__main__":
    unittest.main()
