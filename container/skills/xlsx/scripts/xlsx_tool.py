#!/usr/bin/env python3
"""Build, inspect and check Excel (.xlsx) workbooks. See SKILL.md."""
import argparse
import datetime
import json
import os
import re
import sys

XLSX_SITE = "/workspace/projects/.nanoclaw-tools/xlsx/site"
DEFAULT_FONT = "Arial"
MAX_CELLS = 500_000

# Functions Excel stores with an _xlfn. prefix; openpyxl writes formulas verbatim, so a bare name is #NAME? in Excel.
XLFN = {"TEXTJOIN", "CONCAT", "IFS", "SWITCH", "MAXIFS", "MINIFS", "XLOOKUP", "XMATCH", "SORT", "FILTER",
        "UNIQUE", "SEQUENCE", "LET", "LAMBDA", "STDEV.S", "STDEV.P", "RANK.EQ", "DAYS", "ISOWEEKNUM"}
# Dynamic-array functions: an openpyxl-written file has no spill metadata, so only the top-left cell fills.
SPILLING = {"SORT", "FILTER", "UNIQUE", "SEQUENCE", "XLOOKUP", "XMATCH", "LET", "LAMBDA"}
ERRORS = ("#REF!", "#NAME?", "#VALUE!", "#DIV/0!", "#N/A", "#NUM!", "#NULL!")


class XlsxError(Exception):
    pass


def load_openpyxl():
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        sys.path.insert(0, XLSX_SITE)
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            raise XlsxError("openpyxl is not installed: tell George to run container/skills/xlsx/setup.sh on the host")
    return openpyxl


def col_letter(i):
    from openpyxl.utils import get_column_letter
    return get_column_letter(i)


def parse_value(v, kind):
    """Coerce a JSON value for a column of the given kind ('date' strings become real dates)."""
    if kind == "date" and isinstance(v, str) and v:
        try:
            return datetime.date.fromisoformat(v[:10]) if len(v) <= 10 else datetime.datetime.fromisoformat(v)
        except ValueError:
            raise XlsxError(f"not an ISO date (YYYY-MM-DD): {v!r}")
    return v


def build(spec, out):
    """Write the workbook described by spec to out. Returns a summary dict."""
    op = load_openpyxl()
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.workbook.properties import CalcProperties

    sheets = spec.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        raise XlsxError('spec needs a non-empty "sheets" list')
    font_name = spec.get("font", DEFAULT_FONT)
    wb = op.Workbook()
    wb.remove(wb.active)
    wb.calculation = CalcProperties(fullCalcOnLoad=True)  # Excel/Sheets/LibreOffice compute every formula on open
    head_fill = PatternFill("solid", fgColor=spec.get("header_fill", "1F3864"))
    thin = Side(style="thin", color="BFBFBF")
    cells = formulas = 0

    for sh in sheets:
        name = str(sh.get("name", "")).strip()
        if not name or len(name) > 31 or re.search(r"[\[\]:*?/\\]", name):
            raise XlsxError(f"bad sheet name {name!r}: 1-31 characters, none of [ ] : * ? / \\")
        if name in wb.sheetnames:
            raise XlsxError(f"duplicate sheet name {name!r}")
        ws = wb.create_sheet(name)
        columns = sh.get("columns") or []
        rows = sh.get("rows") or []
        ncols = max([len(columns)] + [len(r) for r in rows] or [0])
        if not ncols:
            raise XlsxError(f"sheet {name!r} has no columns or rows")
        kinds = [c.get("type") if isinstance(c, dict) else None for c in columns] + [None] * ncols
        fmts = [c.get("format") if isinstance(c, dict) else None for c in columns] + [None] * ncols
        for t in range(len(columns)):
            if kinds[t] == "date" and not fmts[t]:
                fmts[t] = "yyyy-mm-dd"

        r0 = 1
        if columns:
            for j, c in enumerate(columns, 1):
                cell = ws.cell(row=1, column=j, value=c["header"] if isinstance(c, dict) else str(c))
                cell.font = Font(name=font_name, bold=True, color="FFFFFF")
                cell.fill = head_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            r0 = 2
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                v = parse_value(v, kinds[j])
                cell = ws.cell(row=r0 + i, column=j + 1, value=v)
                cell.font = Font(name=font_name)
                if fmts[j]:
                    cell.number_format = fmts[j]
                if isinstance(v, str) and v.startswith("="):
                    formulas += 1
                cells += 1
        last = r0 + len(rows) - 1

        totals = sh.get("totals")
        if totals and rows:
            tr = last + 1
            ws.cell(row=tr, column=1, value=totals.get("label", "Total")).font = Font(name=font_name, bold=True)
            for letter in totals.get("columns", []):
                j = op.utils.column_index_from_string(letter)
                cell = ws.cell(row=tr, column=j, value=f"=SUM({letter}{r0}:{letter}{last})")
                cell.font = Font(name=font_name, bold=True)
                cell.border = Border(top=thin)
                if fmts[j - 1]:
                    cell.number_format = fmts[j - 1]
                formulas += 1

        for j in range(1, ncols + 1):
            want = columns[j - 1].get("width") if j <= len(columns) and isinstance(columns[j - 1], dict) else None
            if want is None:
                longest = max([len(str(ws.cell(row=r, column=j).value or "")) for r in range(1, min(ws.max_row, 200) + 1)] + [8])
                want = min(longest + 2, 60)
            ws.column_dimensions[col_letter(j)].width = want
        if sh.get("freeze", bool(columns)):
            ws.freeze_panes = sh["freeze"] if isinstance(sh.get("freeze"), str) else "A2"
        if sh.get("autofilter", bool(columns)) and rows:
            ws.auto_filter.ref = f"A1:{col_letter(ncols)}{last}"
        for n, text in enumerate(sh.get("notes", [])):
            ws.cell(row=ws.max_row + (2 if n == 0 else 1), column=1, value=text).font = Font(name=font_name, italic=True, color="595959")
        if cells > MAX_CELLS:
            raise XlsxError(f"over {MAX_CELLS} cells; split the data")

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    return {"path": os.path.abspath(out), "sheets": wb.sheetnames, "cells": cells, "formulas": formulas,
            "note": "formulas have no cached values until the file is opened in Excel/Sheets; previews may show them blank" if formulas else ""}


def formula_functions(f):
    return {m.upper() for m in re.findall(r"(?<![A-Za-z0-9_.])((?:_xlfn\.)?[A-Za-z][A-Za-z0-9.]*)\(", f)}


def check(path):
    """Lint a workbook: returns {"ok", "problems", "warnings", sheets...}."""
    op = load_openpyxl()
    wb = op.load_workbook(path)
    try:
        vals = op.load_workbook(path, data_only=True)
    except Exception:
        vals = None
    problems, warnings = [], []
    names = set(wb.sheetnames)
    nform = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, str) and v.startswith("="):
                    nform += 1
                    where = f"{ws.title}!{c.coordinate}"
                    for fn in formula_functions(v):
                        base = fn.replace("_XLFN.", "")
                        if base in SPILLING:
                            warnings.append(f"{where}: {base} spills in Excel; only the first cell would fill. Use INDEX/MATCH or compute it in Python")
                        elif base in XLFN and not fn.startswith("_XLFN."):
                            problems.append(f"{where}: {base} needs the _xlfn. prefix (write _xlfn.{base}), otherwise Excel shows #NAME?")
                    for ref in re.findall(r"(?:'([^']+)'|([A-Za-z0-9_.]+))!", v):
                        sheet = ref[0] or ref[1]
                        if sheet not in names:
                            problems.append(f"{where}: refers to missing sheet {sheet!r}")
                    for m in re.finditer(r"(?<!['\w])([A-Za-z][\w]*(?: [\w]+)+)!", v):
                        problems.append(f"{where}: sheet name with spaces must be quoted: '{m.group(1)}'!")
                    if "#REF!" in v:
                        problems.append(f"{where}: contains #REF!")
                    if re.search(r"/\s*0(?![\d.])", v):
                        problems.append(f"{where}: divides by a literal zero")
                elif isinstance(v, str) and v in ERRORS:
                    problems.append(f"{ws.title}!{c.coordinate}: holds the error value {v}")
                elif isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v.strip() or "x"):
                    warnings.append(f"{ws.title}!{c.coordinate}: number stored as text ({v!r}); sums will skip it")
                if vals is not None and c.data_type == "f":
                    cv = vals[ws.title][c.coordinate].value
                    if isinstance(cv, str) and cv in ERRORS:
                        problems.append(f"{ws.title}!{c.coordinate}: cached value is {cv}")
    return {"ok": not problems, "formulas": nform, "sheets": [{"name": w.title, "dimensions": w.dimensions} for w in wb.worksheets],
            "problems": problems[:100], "warnings": warnings[:100],
            "truncated": max(0, len(problems) - 100) + max(0, len(warnings) - 100)}


def inspect(path, max_rows=20):
    """Show each sheet's cells (formulas as written, with cached values where present)."""
    op = load_openpyxl()
    wb = op.load_workbook(path)
    vals = op.load_workbook(path, data_only=True)
    out = []
    for ws in wb.worksheets:
        rows = []
        for r, row in enumerate(ws.iter_rows(), 1):
            if r > max_rows:
                break
            cells = []
            for c in row:
                v = c.value
                if isinstance(v, str) and v.startswith("="):
                    cv = vals[ws.title][c.coordinate].value
                    v = f"{v}" + (f" -> {cv}" if cv is not None else "")
                cells.append("" if v is None else str(v))
            rows.append(cells)
        out.append({"sheet": ws.title, "dimensions": ws.dimensions, "rows_shown": len(rows), "total_rows": ws.max_row, "rows": rows})
    return out


def to_csv_spec(path):
    """Quick CSV -> one-sheet spec so `build` can turn a CSV into a formatted workbook."""
    import csv
    with open(path, newline="", encoding="utf-8-sig") as f:
        data = list(csv.reader(f))
    if not data:
        raise XlsxError("empty CSV")

    def num(s):
        try:
            return int(s) if re.fullmatch(r"-?\d+", s.strip()) else float(s) if re.fullmatch(r"-?\d*\.\d+", s.strip()) else s
        except ValueError:
            return s
    return {"sheets": [{"name": os.path.splitext(os.path.basename(path))[0][:31] or "Sheet1",
                        "columns": [{"header": h} for h in data[0]], "rows": [[num(c) for c in r] for r in data[1:]]}]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build, inspect and check .xlsx workbooks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build a workbook from a JSON spec (or a CSV)")
    b.add_argument("spec", help="spec .json file, or a .csv to convert")
    b.add_argument("out", help="output .xlsx path")
    c = sub.add_parser("check", help="lint formulas and values in a workbook")
    c.add_argument("file")
    i = sub.add_parser("inspect", help="show the cells of a workbook")
    i.add_argument("file")
    i.add_argument("--rows", type=int, default=20)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            if not a.out.lower().endswith(".xlsx"):
                raise XlsxError("output must end in .xlsx")
            spec = to_csv_spec(a.spec) if a.spec.lower().endswith(".csv") else json.load(open(a.spec))
            print(json.dumps(build(spec, a.out), indent=2))
        else:
            if not os.path.isfile(a.file):
                raise XlsxError(f"no such file: {a.file}")
            res = check(a.file) if a.cmd == "check" else inspect(a.file, a.rows)
            print(json.dumps(res, indent=2, default=str))
            if a.cmd == "check" and not res["ok"]:
                return 1
    except XlsxError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
