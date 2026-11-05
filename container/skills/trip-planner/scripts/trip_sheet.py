#!/usr/bin/env python3
"""Build and edit trip planning workbooks (calendar itinerary + budget tabs). See SKILL.md."""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "xlsx", "scripts"))
import xlsx_tool as xt  # noqa: E402

FONT = "Aptos Narrow"
DEFAULT_PARTS = ["Morning", "Lunch", "Afternoon", "Dinner"]
TAIL_ROWS = ["Sleep", "Accommodation", "Comments", "Actions"]
HEAD_FILL = "E7E6E6"
INPUT_FILL, INPUT_FONT = "FFCC99", "3F3F76"  # Excel's "Input" style: the cells to change
CHOSEN_FILL = "C6EFCE"
MAX_DAYS = 60
# Cost tabs: (sheet name, named total, default currency). "home" = George's currency, "local" = the destination's.
COST_TABS = [("Flights", "flights_total", "home"), ("Hotels", "hotels_total", "local"),
             ("Food & Beverage", "food_beverage_total", "local"), ("Transfers", "transfers_total", "home"),
             ("Activities", "activities_total", "home")]


class TripError(Exception):
    pass


def styles(op):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    thin = Side(style="thin", color="000000")
    return {
        "border": Border(left=thin, right=thin, top=thin, bottom=thin),
        "head_fill": PatternFill("solid", fgColor=HEAD_FILL),
        "input_fill": PatternFill("solid", fgColor=INPUT_FILL),
        "bold": Font(name=FONT, bold=True),
        "plain": Font(name=FONT),
        "input_font": Font(name=FONT, color=INPUT_FONT),
        "wrap": Alignment(wrap_text=True, vertical="center"),
        "center": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "Font": Font, "Alignment": Alignment, "PatternFill": PatternFill,
    }


def parse_date(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except ValueError:
        raise TripError(f"start_date must be YYYY-MM-DD, got {s!r}")


def row_height(texts, width):
    """Rough height so wrapped text is visible: ~15pt a line, width in characters."""
    lines = 1
    for t in texts:
        if t:
            lines = max(lines, sum(max(1, -(-len(l) // max(1, int(width * 1.1)))) for l in str(t).split("\n")))
    return min(409, max(30, 15 * lines + 6))


def build_itinerary(wb, spec, st):
    days = spec.get("days")
    if isinstance(days, int):
        days = [{} for _ in range(days)]
    if not days or len(days) > MAX_DAYS:
        raise TripError(f'"days" must be a count or a list of 1-{MAX_DAYS} day objects')
    parts = spec.get("parts") or DEFAULT_PARTS
    tail = spec.get("tail_rows", TAIL_ROWS)
    title = spec.get("title_row", False)
    ws = wb.create_sheet("Itinerary")
    top = 3 if title else 1  # dates row
    if title:
        ws["A1"] = spec["trip"]
        ws["A1"].font = st["Font"](name=FONT, bold=True, size=22)
        ws.row_dimensions[1].height = 30
    from openpyxl.utils import get_column_letter as L
    n = len(days)
    labels = [(top, ""), (top + 1, "Day"), (top + 2, "DOW")] + [(top + 3 + i, p) for i, p in enumerate(parts + tail)]
    for r, text in labels:
        c = ws.cell(row=r, column=1, value=text)
        c.font, c.border, c.alignment = st["bold"], st["border"], st["center"]
        c.fill = st["head_fill"]
    for j in range(n):
        col = j + 2
        prev = L(col - 1)
        d = ws.cell(row=top, column=col, value="=Variables!$B$1" if j == 0 else f"={prev}{top}+1")
        d.number_format = "ddd d mmm"
        n_ = ws.cell(row=top + 1, column=col, value=1 if j == 0 else f"={prev}{top + 1}+1")
        w = ws.cell(row=top + 2, column=col, value=f'=TEXT({L(col)}{top},"DDDD")')
        for c in (d, n_, w):
            c.font, c.border, c.alignment = st["bold"], st["border"], st["center"]
        for i, p in enumerate(parts + tail):
            text = (days[j].get(p) or days[j].get(p.lower()) or "") if isinstance(days[j], dict) else ""
            c = ws.cell(row=top + 3 + i, column=col, value=text or None)
            c.font, c.border, c.alignment = st["plain"], st["border"], st["wrap"]
        ws.column_dimensions[L(col)].width = spec.get("column_width", 24)
    ws.column_dimensions["A"].width = 16
    for i, p in enumerate(parts + tail):
        r = top + 3 + i
        texts = [ws.cell(row=r, column=j + 2).value for j in range(n)]
        ws.row_dimensions[r].height = row_height(texts, spec.get("column_width", 24))
    ws.row_dimensions[top].height = 30
    ws.freeze_panes = ws.cell(row=top + 3, column=2)
    return ws


def input_cell(c, st, fmt=None):
    c.font, c.fill, c.border = st["input_font"], st["input_fill"], st["border"]
    if fmt:
        c.number_format = fmt


def header_row(ws, row, labels, st):
    for j, t in enumerate(labels, 1):
        c = ws.cell(row=row, column=j, value=t)
        c.font, c.fill, c.border, c.alignment = st["bold"], st["head_fill"], st["border"], st["center"]


def money(cur):
    return '"$"#,##0.00'


def add_name(wb, name, ref):
    from openpyxl.workbook.defined_name import DefinedName
    wb.defined_names[name] = DefinedName(name, attr_text=ref)


def options_sheet(wb, st, name, total_name, items, price_label, mult, currency_note):
    """A 'pick one' comparison tab: options with a 1/0 'chosen' flag; the total uses the chosen ones."""
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.worksheet.datavalidation import DataValidation
    ws = wb.create_sheet(name)
    ws["A1"], ws["A2"] = "Total", f"Total per {mult[0]}"
    last = 4 + max(len(items), 1)
    ws["B2"] = f"=SUMIF(C4:C{last + 6},1,B4:B{last + 6})"
    ws["B1"] = f"=B2*{mult[1]}"
    for a in ("A1", "A2"):
        ws[a].font = st["bold"]
    for a in ("B1", "B2"):
        ws[a].font, ws[a].number_format = st["bold"], money(currency_note)
    header_row(ws, 3, [name.rstrip("s") if name != "Food & Beverage" else "Item", price_label, "Chosen option (1 = yes)", "Notes"], st)
    for i, it in enumerate(items):
        r = 4 + i
        ws.cell(row=r, column=1, value=it.get("name") or it.get("item"))
        p = ws.cell(row=r, column=2, value=it.get("price", it.get("price_pp", it.get("price_per_night"))))
        p.number_format = money(currency_note)
        ws.cell(row=r, column=3, value=1 if it.get("chosen") else 0)
        ws.cell(row=r, column=4, value=it.get("notes"))
        for c in range(1, 5):
            ws.cell(row=r, column=c).font = st["plain"]
            ws.cell(row=r, column=c).border = st["border"]
        input_cell(p, st, money(currency_note))
        input_cell(ws.cell(row=r, column=3), st)
    dv = DataValidation(type="whole", operator="between", formula1="0", formula2="1", allow_blank=True,
                        error="Enter 1 to choose this option, 0 to leave it out")
    ws.add_data_validation(dv)
    dv.add(f"C4:C{last + 6}")
    ws.conditional_formatting.add(f"A4:D{last + 6}", FormulaRule(formula=["$C4=1"], fill=st["PatternFill"]("solid", bgColor=CHOSEN_FILL, fgColor=CHOSEN_FILL)))
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 40
    add_name(wb, total_name, f"'{name}'!$B$1")
    return ws


def list_sheet(wb, st, name, total_name, items, cost_label, currency_note):
    ws = wb.create_sheet(name)
    ws["A1"], ws["B1"] = "Total", f"=SUM(B4:B{4 + max(len(items), 1) + 30})"
    ws["A1"].font, ws["B1"].font = st["bold"], st["bold"]
    ws["B1"].number_format = money(currency_note)
    header_row(ws, 3, ["Item", cost_label, "Notes"], st)
    for i, it in enumerate(items):
        r = 4 + i
        ws.cell(row=r, column=1, value=it.get("item") or it.get("name"))
        c = ws.cell(row=r, column=2, value=it.get("cost"))
        ws.cell(row=r, column=3, value=it.get("notes"))
        for k in range(1, 4):
            ws.cell(row=r, column=k).font, ws.cell(row=r, column=k).border = st["plain"], st["border"]
        input_cell(c, st, money(currency_note))
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 40
    add_name(wb, total_name, f"'{name}'!$B$1")
    return ws


def food_sheet(wb, st, spec, currency_note):
    ws = wb.create_sheet("Food & Beverage")
    ws["A1"], ws["B1"] = "Total", "=B2*exchange_rate_for_local"
    ws["A2"], ws["B2"] = "Total (local currency)", f"=B3*number_of_nights+SUM(B6:B{6 + max(len(spec.get('travellers', [])), 1) + 6})"
    ws["A3"] = "Per day budget (local currency)"
    ws["B3"] = spec.get("food_per_day", 0)
    input_cell(ws["B3"], st, money(currency_note))
    ws["A5"] = "Spending money (local currency)"
    for a in ("A1", "A2", "A3", "A5"):
        ws[a].font = st["bold"]
    for i, who in enumerate(spec.get("travellers", [])):
        ws.cell(row=6 + i, column=1, value=who).font = st["plain"]
        c = ws.cell(row=6 + i, column=2, value=spec.get("spending_money", {}).get(who, 0))
        input_cell(c, st, money(currency_note))
    ws["B1"].number_format = ws["B2"].number_format = money(currency_note)
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 18
    add_name(wb, "food_beverage_total", "'Food & Beverage'!$B$1")
    return ws


def overview_sheet(wb, st, spec, tab_names, nights):
    cur = spec.get("currency", {})
    home, local = cur.get("home", "AUD"), cur.get("local", cur.get("home", "AUD"))
    rate = cur.get("rate", 1)
    ws = wb.create_sheet("Overview", 0)
    ws["A1"] = f"Exchange rate ({local} to {home})"
    ws["B1"] = rate
    input_cell(ws["B1"], st, "0.0000")
    ws["C1"] = cur.get("rate_note", "Check the current rate before relying on this")
    ws["A2"], ws["B2"] = "Number of nights", nights
    input_cell(ws["B2"], st)
    ws["A3"] = "Travellers"
    ws["B3"] = max(1, len(spec.get("travellers", [])))
    input_cell(ws["B3"], st)
    for a in ("A1", "A2", "A3"):
        ws[a].font = st["bold"]
    header_row(ws, 5, ["Item", f"Total ({home})", f"Per person ({home})"], st)
    r = 6
    for name, named in tab_names:
        ws.cell(row=r, column=1, value=name).font = st["plain"]
        c = ws.cell(row=r, column=2, value=f"={named}")
        c.number_format = money(home)
        p = ws.cell(row=r, column=3, value=f"=B{r}/travellers")
        p.number_format = money(home)
        for k in (1, 2, 3):
            ws.cell(row=r, column=k).border = st["border"]
        r += 1
    ws.cell(row=r, column=1, value="Total").font = st["bold"]
    t = ws.cell(row=r, column=2, value=f"=SUM(B6:B{r - 1})")
    t.font, t.number_format = st["bold"], money(home)
    p = ws.cell(row=r, column=3, value=f"=B{r}/travellers")
    p.font, p.number_format = st["bold"], money(home)
    for k in (1, 2, 3):
        ws.cell(row=r, column=k).border = st["border"]
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 22
    add_name(wb, "exchange_rate", "Overview!$B$1")
    add_name(wb, "number_of_nights", "Overview!$B$2")
    add_name(wb, "travellers", "Overview!$B$3")
    add_name(wb, "exchange_rate_for_local", "Overview!$B$1")
    return ws


def build(spec, out):
    op = xt.load_openpyxl()
    st = styles(op)
    for k in ("trip", "start_date", "days"):
        if k not in spec:
            raise TripError(f'spec needs "{k}"')
    start = parse_date(spec["start_date"])
    wb = op.Workbook()
    wb.remove(wb.active)
    from openpyxl.workbook.properties import CalcProperties
    wb.calculation = CalcProperties(fullCalcOnLoad=True)
    itin = build_itinerary(wb, spec, st)
    n = (spec["days"] if isinstance(spec["days"], int) else len(spec["days"]))
    var = wb.create_sheet("Variables")
    var["A1"], var["B1"] = "Start Date", start
    var["A1"].font = st["bold"]
    input_cell(var["B1"], st, "d mmm yyyy")
    var["A2"], var["B2"] = "Trip", spec["trip"]
    var["A2"].font = st["bold"]
    var.column_dimensions["A"].width = 18
    var.column_dimensions["B"].width = 16
    tabs = spec.get("tabs", ["budget"] if any(k in spec for k in ("flights", "hotels", "transfers", "activities", "food_per_day")) else [])
    if tabs:
        cur = spec.get("currency", {})
        home, local = cur.get("home", "AUD"), cur.get("local", cur.get("home", "AUD"))
        cur_of = {name: spec.get("currency_of", {}).get(name, default) for name, _, default in COST_TABS}
        trav = max(1, len(spec.get("travellers", [])))
        tab_names = []
        for name, named, _ in COST_TABS:
            key = {"Flights": "flights", "Hotels": "hotels", "Transfers": "transfers", "Activities": "activities"}.get(name)
            if name == "Food & Beverage":
                if "food_per_day" in spec or spec.get("travellers"):
                    food_sheet(wb, st, spec, local)
                    tab_names.append((name, named))
                continue
            if key not in spec and name not in ("Flights", "Hotels"):
                continue
            items = spec.get(key, [])
            if name == "Flights":
                options_sheet(wb, st, name, named, items, f"Price per person ({home})", ("person", "travellers"), home)
            elif name == "Hotels":
                ws = options_sheet(wb, st, name, "hotels_local_total", items, f"Price per night ({local})", ("night", "number_of_nights"), local)
                ws["A1"] = f"Total ({home})"
                ws["B1"] = "=B2*number_of_nights*exchange_rate_for_local" if cur_of[name] == "local" else "=B2*number_of_nights"
                add_name(wb, named, "'Hotels'!$B$1")
                ws["A2"] = "Price per night (chosen)"
            else:
                list_sheet(wb, st, name, named, items, f"Cost ({home})" if cur_of[name] == "home" else f"Cost ({local})", home)
            tab_names.append((name, named))
        # Food converts local to home on its own sheet
        overview_sheet(wb, st, spec, tab_names, max(1, n - 1))
    # tab order: Overview, Itinerary first
    order = [s for s in ("Itinerary", "Overview") if s in wb.sheetnames] + [s for s in wb.sheetnames if s not in ("Itinerary", "Overview", "Variables")] + ["Variables"]
    wb._sheets = [wb[s] for s in order]
    wb.active = 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    return {"path": os.path.abspath(out), "sheets": wb.sheetnames, "days": n}


def find_itinerary(wb):
    if "Itinerary" not in wb.sheetnames:
        raise TripError("no Itinerary sheet in this workbook")
    ws = wb["Itinerary"]
    day_row = next((r for r in range(1, 6) if str(ws.cell(row=r, column=1).value).strip() == "Day"), None)
    if day_row is None:
        raise TripError('cannot find the "Day" row; this does not look like a trip planner sheet')
    return ws, day_row


def day_col(ws, day_row, day):
    for c in range(2, ws.max_column + 1):
        v = ws.cell(row=day_row, column=c).value
        if v == day or (isinstance(v, str) and v.startswith("=") and c - 1 == day):
            return c
    if ws.cell(row=day_row, column=2).value is not None and 1 <= day <= ws.max_column - 1:
        return day + 1
    raise TripError(f"no day {day}")


def row_for(ws, label, day_row):
    want = label.strip().lower()
    for r in range(day_row + 1, ws.max_row + 1):
        if str(ws.cell(row=r, column=1).value or "").strip().lower() == want:
            return r
    names = [str(ws.cell(row=r, column=1).value) for r in range(day_row + 2, ws.max_row + 1) if ws.cell(row=r, column=1).value]
    raise TripError(f"no row called {label!r}; rows are: {', '.join(names)}")


def set_cell(path, day, row, text, append=False, out=None):
    op = xt.load_openpyxl()
    wb = op.load_workbook(path)
    ws, dr = find_itinerary(wb)
    c = ws.cell(row=row_for(ws, row, dr), column=day_col(ws, dr, day))
    old = c.value
    c.value = f"{old}\n{text}" if append and old else text
    wb.save(path if out is None else out)
    return {"day": day, "row": row, "was": old, "now": c.value}


def show(path):
    op = xt.load_openpyxl()
    wb = op.load_workbook(path)
    vals = op.load_workbook(path, data_only=True)
    ws, dr = find_itinerary(wb)
    vw = vals["Itinerary"]
    out = []
    for c in range(2, ws.max_column + 1):
        if ws.cell(row=dr, column=c).value is None:
            continue
        date = vw.cell(row=dr - 1, column=c).value
        dow = vw.cell(row=dr + 1, column=c).value
        head = f"Day {c - 1}" + (f" ({dow}" + (f" {date:%d %b %Y}" if hasattr(date, "strftime") else "") + ")" if dow or date else "")
        lines = []
        for r in range(dr + 2, ws.max_row + 1):
            v = ws.cell(row=r, column=c).value
            if v:
                lines.append(f"  {ws.cell(row=r, column=1).value}: " + str(v).replace("\n", " / "))
        out.append(head + "\n" + ("\n".join(lines) if lines else "  (nothing planned)"))
    return "\n".join(out)


def add_options(path, name, items, price_label, mult_label="person", multiplier="travellers", currency="AUD", out=None):
    """Add a comparison tab (e.g. 'Rental cars') and link it into the Overview total."""
    op = xt.load_openpyxl()
    st = styles(op)
    wb = op.load_workbook(path)
    if name in wb.sheetnames:
        raise TripError(f"a sheet called {name!r} already exists")
    named = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") + "_total"
    options_sheet(wb, st, name, named, items, price_label, (mult_label, multiplier), currency)
    if "Overview" in wb.sheetnames:
        link_overview(wb, st, name, named)
    wb.save(path if out is None else out)
    return {"added": name, "named_total": named}


def link_overview(wb, st, name, named):
    ov = wb["Overview"]
    tr = next((r for r in range(5, ov.max_row + 1) if str(ov.cell(row=r, column=1).value).strip() == "Total"), None)
    if tr is None:
        raise TripError("Overview has no Total row")
    home_fmt = ov.cell(row=tr - 1, column=2).number_format
    # move the Total row down one and insert the new item above it
    for col in (1, 2, 3):
        src, dst = ov.cell(row=tr, column=col), ov.cell(row=tr + 1, column=col)
        dst._style = src._style
    ov.cell(row=tr + 1, column=1, value="Total")
    ov.cell(row=tr + 1, column=2, value=f"=SUM(B6:B{tr})")
    ov.cell(row=tr + 1, column=3, value=f"=B{tr + 1}/travellers")
    for col in (1, 2, 3):
        ov.cell(row=tr, column=col)._style = ov.cell(row=tr - 1, column=col)._style
    ov.cell(row=tr, column=1, value=name)
    ov.cell(row=tr, column=2, value=f"={named}").number_format = home_fmt
    ov.cell(row=tr, column=3, value=f"=B{tr}/travellers").number_format = home_fmt


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trip planner workbooks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("spec")
    b.add_argument("out")
    s = sub.add_parser("show")
    s.add_argument("file")
    t = sub.add_parser("set")
    t.add_argument("file")
    t.add_argument("--day", type=int, required=True)
    t.add_argument("--row", required=True, help="row label, e.g. Morning, Sleep, Actions")
    t.add_argument("--text", required=True)
    t.add_argument("--append", action="store_true")
    o = sub.add_parser("add-options")
    o.add_argument("file")
    o.add_argument("--name", required=True)
    o.add_argument("--items", required=True, help='JSON list: [{"name":"..","price":123,"chosen":0,"notes":".."}]')
    o.add_argument("--price-label", default="Price")
    o.add_argument("--per", default="person")
    o.add_argument("--multiplier", default="travellers", help="named cell the per-unit total is multiplied by (travellers or number_of_nights)")
    o.add_argument("--currency", default="AUD")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            print(json.dumps(build(json.load(open(a.spec)), a.out), indent=2))
        elif a.cmd == "show":
            print(show(a.file))
        elif a.cmd == "set":
            print(json.dumps(set_cell(a.file, a.day, a.row, a.text, a.append), indent=2))
        else:
            print(json.dumps(add_options(a.file, a.name, json.loads(a.items), a.price_label, a.per, a.multiplier, a.currency), indent=2))
    except (TripError, xt.XlsxError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
