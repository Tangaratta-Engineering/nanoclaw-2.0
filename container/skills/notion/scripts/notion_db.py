"""Notion databases (data sources): create, inspect, add/update rows, query, alter columns.

Used by notion.py. In Notion's 2025+ API a database is a container; its columns and rows live on a
data source, so ids are resolved to the data source before each call.
"""
import json
import re

from notion_core import NotionError, page_id, request, title_of  # noqa: F401

SELECTABLE = ("select", "multi_select", "status")


def rich(text):
    return [{"type": "text", "text": {"content": text}}]


def split_top(spec, sep=","):
    """Split on `sep` outside parentheses."""
    out, depth, cur = [], 0, ""
    for ch in spec:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [x.strip() for x in out if x.strip()]


def parse_column(spec):
    """'Person:select(George|Emily)' -> (name, notion property config)."""
    m = re.fullmatch(r"(.+?):\s*(\w+)(?:\((.*)\))?", spec.strip())
    if not m:
        raise NotionError(f"bad column spec '{spec}' (use Name:type or Name:select(a|b))")
    name, typ, opts = m.group(1).strip(), m.group(2).lower(), m.group(3)
    typ = {"text": "rich_text", "multi": "multi_select", "multiselect": "multi_select"}.get(typ, typ)
    options = [{"name": o.strip()} for o in (opts or "").split("|") if o.strip()]
    if typ in ("title", "rich_text", "date", "checkbox", "url"):
        return name, {"type": typ, typ: {}}
    if typ == "number":
        return name, {"type": "number", "number": {"format": "number"}}
    if typ in ("select", "multi_select"):
        return name, {"type": typ, typ: {"options": options}}
    if typ == "status":
        return name, {"type": "status", "status": ({"options": [dict(o, group="To-do") for o in options]} if options else {})}
    raise NotionError(f"unsupported column type '{typ}' (title, text, number, select, multi, date, checkbox, url, status)")


def parse_columns(spec):
    cols = {}
    for part in split_top(spec):
        n, c = parse_column(part)
        cols[n] = c
    if not any(c["type"] == "title" for c in cols.values()):
        cols = {"Name": {"type": "title", "title": {}}, **cols}
    return cols


def data_source_id(ref, run):
    """Accept a database id/URL or a data source id; return the data source id."""
    pid = page_id(ref)
    try:
        db = request("GET", f"/v1/databases/{pid}", None, run)
        sources = db.get("data_sources") or []
        if sources:
            return sources[0]["id"]
    except NotionError as e:
        if "HTTP 404" not in str(e) and "HTTP 400" not in str(e):
            raise
    return pid


def schema(ds, run):
    r = request("GET", f"/v1/data_sources/{ds}", None, run)
    return {name: p["type"] for name, p in (r.get("properties") or {}).items()}, r


def cell_value(typ, raw):
    """Turn a user string into a Notion property value for `typ`."""
    if raw is None or str(raw).strip().lower() in ("", "null", "none"):
        return {"title": []} if typ == "title" else {"rich_text": []} if typ == "rich_text" else {typ: [] if typ == "multi_select" else None}
    s = str(raw).strip()
    if typ == "title":
        return {"title": rich(s)}
    if typ == "rich_text":
        return {"rich_text": rich(s)}
    if typ == "number":
        try:
            return {"number": float(s) if "." in s else int(s)}
        except ValueError:
            raise NotionError(f"'{s}' is not a number")
    if typ == "checkbox":
        return {"checkbox": s.lower() in ("true", "yes", "y", "1", "x", "done", "☑")}
    if typ == "select":
        return {"select": {"name": s}}
    if typ == "status":
        return {"status": {"name": s}}
    if typ == "multi_select":
        return {"multi_select": [{"name": x.strip()} for x in s.split("|") if x.strip()]}
    if typ == "url":
        return {"url": s}
    if typ == "date":
        start, _, end = s.partition("/")
        return {"date": {"start": start.strip(), "end": end.strip() or None}}
    raise NotionError(f"column type '{typ}' cannot be set with this tool")


def build_props(values, types):
    props = {}
    for k, v in values.items():
        if k not in types:
            raise NotionError(f"no column '{k}' (columns: {', '.join(types)})")
        props[k] = cell_value(types[k], v)
    return props


def show(prop):
    t = prop.get("type")
    v = prop.get(t)
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v or [])
    if t in ("select", "status"):
        return (v or {}).get("name", "")
    if t == "multi_select":
        return "|".join(x["name"] for x in v or [])
    if t == "checkbox":
        return "yes" if v else "no"
    if t == "date":
        return "" if not v else v["start"] + (f"→{v['end']}" if v.get("end") else "")
    if t in ("number", "url", "email", "phone_number"):
        return "" if v is None else str(v)
    if t == "people":
        return "|".join(x.get("name", "") for x in v or [])
    return ""


def row_line(page):
    cells = [f"{k}={show(p)}" for k, p in page.get("properties", {}).items() if show(p) != ""]
    return f"{page['id']} | " + "; ".join(cells)


# --- commands -------------------------------------------------------------------------------

def db_create(a, run):
    body = {"parent": {"type": "page_id", "page_id": page_id(a.parent)}, "title": rich(a.title),
            "initial_data_source": {"properties": parse_columns(a.columns)}}
    r = request("POST", "/v1/databases", body, run)
    ds = (r.get("data_sources") or [{}])[0].get("id", "(see db-schema)")
    return f"Created database: {a.title} | database {r['id']} | data source {ds} | {r.get('url', '')}"


def db_schema(a, run):
    ds = data_source_id(a.db, run)
    types, r = schema(ds, run)
    lines = [f"data source {ds}"]
    for name, p in (r.get("properties") or {}).items():
        opts = ""
        if p["type"] in SELECTABLE:
            opts = "(" + "|".join(o["name"] for o in (p[p["type"]] or {}).get("options", [])) + ")"
        lines.append(f"  {name}: {p['type']}{opts}")
    return "\n".join(lines)


def parse_sets(sets):
    out = {}
    for s in sets or []:
        k, eq, v = s.partition("=")
        if not eq:
            raise NotionError(f"--set needs Column=value, got '{s}'")
        out[k.strip()] = v
    return out


def db_add_row(a, run):
    ds = data_source_id(a.db, run)
    types, _ = schema(ds, run)
    body = {"parent": {"type": "data_source_id", "data_source_id": ds}, "properties": build_props(parse_sets(a.set), types)}
    if a.body_file:
        with open(a.body_file, encoding="utf-8") as f:
            body["markdown"] = f.read()
    r = request("POST", "/v1/pages", body, run)
    return f"Added row: {r['id']} | {r.get('url', '')}"


def db_add_rows(a, run):
    """JSON array of {Column: value} objects."""
    with open(a.file, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise NotionError("rows file must be a JSON array of objects")
    ds = data_source_id(a.db, run)
    types, _ = schema(ds, run)
    done, failed = 0, []
    for i, row in enumerate(rows, 1):
        try:
            props = build_props(row, types)
            request("POST", "/v1/pages", {"parent": {"type": "data_source_id", "data_source_id": ds}, "properties": props}, run)
            done += 1
        except NotionError as e:
            failed.append(f"row {i}: {e}")
    out = f"Added {done} of {len(rows)} rows."
    return out + ("\n" + "\n".join(failed[:10]) if failed else "")


def db_update_row(a, run):
    pid = page_id(a.row)
    page = request("GET", f"/v1/pages/{pid}", None, run)
    ds = (page.get("parent") or {}).get("data_source_id")
    if not ds:
        raise NotionError("that page is not a database row")
    types, _ = schema(ds, run)
    request("PATCH", f"/v1/pages/{pid}", {"properties": build_props(parse_sets(a.set), types)}, run)
    return "Row updated."


def make_filter(expr, types):
    m = re.fullmatch(r"(.+?)(=|~|<|>)(.*)", expr)
    if not m:
        raise NotionError(f"bad --where '{expr}' (use Column=value, Column~text, Column<date, Column>date)")
    col, op, val = m.group(1).strip(), m.group(2), m.group(3).strip()
    if col not in types:
        raise NotionError(f"no column '{col}' (columns: {', '.join(types)})")
    t = types[col]
    f = {"property": col}
    if t == "checkbox":
        f["checkbox"] = {"equals": val.lower() in ("true", "yes", "y", "1", "x")}
    elif t == "date":
        key = {"=": "equals", "<": "before", ">": "after"}.get(op)
        if not key:
            raise NotionError("dates support =, < and >")
        f["date"] = {key: val}
    elif t == "number":
        key = {"=": "equals", "<": "less_than", ">": "greater_than"}.get(op)
        if not key:
            raise NotionError("numbers support =, < and >")
        f["number"] = {key: float(val)}
    elif t in ("title", "rich_text", "url"):
        f[t] = {"contains": val} if op == "~" else {"equals": val}
    elif t in ("select", "status"):
        f[t] = {"equals": val}
    elif t == "multi_select":
        f[t] = {"contains": val}
    else:
        raise NotionError(f"cannot filter on a {t} column")
    return f


def db_query(a, run):
    ds = data_source_id(a.db, run)
    types, _ = schema(ds, run)
    body = {"page_size": min(a.limit, 100)}
    filters = [make_filter(w, types) for w in a.where or []]
    if len(filters) == 1:
        body["filter"] = filters[0]
    elif filters:
        body["filter"] = {"and": filters}
    if a.sort:
        col, _, d = a.sort.partition(":")
        if col not in types:
            raise NotionError(f"no column '{col}'")
        body["sorts"] = [{"property": col, "direction": "descending" if d.startswith("d") else "ascending"}]
    rows, cursor = [], None
    while len(rows) < a.limit:
        if cursor:
            body["start_cursor"] = cursor
        r = request("POST", f"/v1/data_sources/{ds}/query", body, run)
        rows += r.get("results", [])
        cursor = r.get("next_cursor")
        if not r.get("has_more") or not cursor:
            break
    rows = rows[: a.limit]
    return "\n".join(row_line(p) for p in rows) if rows else "No matching rows."


def db_alter(a, run):
    ds = data_source_id(a.db, run)
    props = {}
    for spec in a.add or []:
        n, c = parse_column(spec)
        props[n] = c
    for pair in a.rename or []:
        old, eq, new = pair.partition("=")
        if not eq:
            raise NotionError("--rename needs Old=New")
        props[old.strip()] = {"name": new.strip()}
    for name in a.remove or []:
        if not a.yes_remove:
            raise NotionError("removing a column deletes its data in every row; confirm with George, then add --yes-remove")
        props[name] = None
    if not props:
        raise NotionError("nothing to do: use --add, --rename or --remove")
    request("PATCH", f"/v1/data_sources/{ds}", {"properties": props}, run)
    return "Columns updated."
