import json, os, sys, tempfile, unittest
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
import pdf_text as p

try:
    import pypdf  # noqa: F401
    HAVE = True
except ImportError:
    sys.path.insert(0, p.PDF_SITE)
    try:
        import pypdf  # noqa: F401
        HAVE = True
    except ImportError:
        HAVE = False


def make_pdf(pages):
    """Minimal valid PDF; each page's text is drawn in Helvetica ('' = an empty page)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for t in pages:
        n = len(objs)
        stream = f"BT /F1 12 Tf 50 700 Td ({t}) Tj ET" if t else ""
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {n + 2} 0 R /Resources << /Font << /F1 3 0 R >> >> >>")
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        kids.append(f"{n + 1} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    return out


@unittest.skipUnless(HAVE, "pypdf not installed")
class T(unittest.TestCase):
    def test_extracts_text_and_pages(self):
        data = make_pdf(["Invoice 123 Amount due 50.00", "Page two Reference 998877"])
        text, notes = p.extract(data)
        self.assertIn("Invoice 123 Amount due 50.00", text)
        self.assertIn("--- page 2 of 2 ---", text)
        self.assertEqual(notes, [])
        t2, _ = p.extract(data, pages="2")
        self.assertNotIn("Invoice 123", t2); self.assertIn("Reference 998877", t2)

    def test_scanned_pdf_is_flagged(self):
        _, notes = p.extract(make_pdf(["", ""]))
        self.assertTrue(any("NO TEXT LAYER" in n for n in notes))
        _, notes = p.extract(make_pdf(["Has text", ""]))
        self.assertTrue(any("1 of 2 pages had no text" in n for n in notes))

    def test_max_chars_and_garbage(self):
        text, notes = p.extract(make_pdf(["x" * 500]), max_chars=100)
        self.assertEqual(len(text), 100); self.assertTrue(any("cut" in n for n in notes))
        with self.assertRaises(p.PdfError):
            p.extract(b"not a pdf at all")

    def test_cli_file_and_url_checks(self):
        d = tempfile.mkdtemp(); f = os.path.join(d, "a.pdf")
        open(f, "wb").write(make_pdf(["Hello PDF"]))
        self.assertEqual(p.main([f], None), 0)
        with self.assertRaises(p.PdfError):
            p.fetch_url("ftp://x/y.pdf")
        html = lambda cmd, **k: NS(returncode=0, stdout=b"<html>", stderr=b"")
        with self.assertRaises(p.PdfError) as c:
            p.fetch_url("https://example.com/page", html)
        self.assertIn("WebFetch", str(c.exception))

    def test_gmail_attachment_lookup(self):
        import base64
        pdf = make_pdf(["From email"])
        calls = []

        def run(cmd, **k):
            url = [c for c in cmd if c.startswith("https://")][0]
            calls.append(url)
            if url.endswith("format=full"):
                body = {"payload": {"parts": [{"filename": "Invoice-42.pdf", "body": {"attachmentId": "A1"}}, {"filename": "logo.png", "body": {"attachmentId": "A2"}}]}}
            else:
                body = {"data": base64.urlsafe_b64encode(pdf).decode()}
            return NS(returncode=0, stdout=json.dumps(body).encode(), stderr=b"")

        self.assertEqual(p.fetch_gmail("m1", "invoice", run), pdf)
        self.assertTrue(calls[-1].endswith("/attachments/A1"))
        with self.assertRaises(p.PdfError):
            p.fetch_gmail("m1", "statement", run)


if __name__ == "__main__":
    unittest.main()
