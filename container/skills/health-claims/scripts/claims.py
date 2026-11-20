#!/usr/bin/env python3
"""Peoplecare health claims for George. See SKILL.md.

Talks to the host's claims bridge (a JSON file in the shared queue). The bridge works inside George's signed-in
Peoplecare browser and keeps the records in Postgres; this tool never sees a login. Nothing is lodged until
George quotes the approval code from the claim card.
"""
import argparse
import json
import os
import re
import secrets
import sys
import time

QUEUE = os.environ.get("CLAIMS_QUEUE", "/workspace/projects/.nanoclaw-data/claims/queue")
FILES = os.environ.get("CLAIMS_FILES", "/workspace/projects/.nanoclaw-data/claims/files")
PDF_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pdf", "scripts")
TIMEOUT = float(os.environ.get("CLAIMS_TIMEOUT", "150"))


class ClaimsError(Exception):
    pass


def ask(req, queue=QUEUE, timeout=TIMEOUT, sleep=time.sleep):
    rid = f"{int(time.time())}-{secrets.token_hex(4)}"
    inbox, outbox = os.path.join(queue, "in", rid + ".json"), os.path.join(queue, "out", rid + ".json")
    if not os.path.isdir(os.path.join(queue, "in")):
        raise ClaimsError("the claims bridge isn't set up on the server (no queue folder)")
    tmp = inbox + ".tmp"
    with open(tmp, "w") as f:
        json.dump(req, f)
    os.chmod(tmp, 0o666)
    os.rename(tmp, inbox)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(outbox):
            with open(outbox) as f:
                res = json.load(f)
            os.remove(outbox)
            if not res.get("ok"):
                raise ClaimsError(res.get("error", "unknown error"))
            return res["data"]
        sleep(0.5)
    try:
        os.remove(inbox)
    except OSError:
        pass
    raise ClaimsError("no answer from the claims bridge (is it running on the server? tell George)")


def money(v):
    return f"${v:.2f}" if isinstance(v, (int, float)) else "n/a"


def line(c):
    return f"#{c['id']} | {c['status']} | {c['provider']} | {c['patient']} | invoice {c['invoice_no']} | {c.get('date') or '?'} | {money(c.get('amount'))}" + (f" | {c['peoplecare_ref']}" if c.get("peoplecare_ref") else "")


def card(c):
    out = [f"CLAIM CARD #{c['id']} (Peoplecare)",
           f"Provider: {c['provider']}", f"Patient: {c['patient']}" + ("" if c["patient_known"] else "   <-- NOT a known family name: check this is right"),
           f"Invoice: {c['invoice_no']}  Date: {c.get('date') or '?'}  Amount: {money(c.get('amount'))}", f"Reference: {c['reference']}",
           "The form is filled and waiting on its Review page. Nothing has been lodged.", f"To lodge it, George replies: Send {c['approval_code']}"]
    return "\n".join(out)


def save_pdf(email_id, which=None, runner=None):
    """Download the PDF attachment of an email into the claims folder; returns the plain file name."""
    sys.path.insert(0, PDF_SCRIPTS)
    try:
        import pdf_text
    except ImportError:
        raise ClaimsError("the pdf skill is not available here")
    kwargs = {"runner": runner} if runner else {}
    try:
        data = pdf_text.fetch_gmail(email_id, which, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise ClaimsError(f"could not fetch the PDF from that email: {e}")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", f"{email_id}-{which or 'invoice'}")[:100]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    os.makedirs(FILES, exist_ok=True)
    path = os.path.join(FILES, name)
    with open(path, "wb") as f:
        f.write(data)
    os.chmod(path, 0o644)
    return name


def run(argv, ask=ask, save=save_pdf):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("add", help="register an invoice from an email")
    s.add_argument("--email", required=True, help="Gmail message id")
    s.add_argument("--pdf-name", help="attachment file name, if the email has several PDFs")
    s.add_argument("--provider", required=True); s.add_argument("--patient", required=True)
    s.add_argument("--invoice-no", required=True); s.add_argument("--date"); s.add_argument("--amount", type=float)
    s.add_argument("--service"); s.add_argument("--reference", required=True)
    s = sub.add_parser("list"); s.add_argument("--status")
    for n in ("show", "prepare", "cancel"):
        s = sub.add_parser(n); s.add_argument("id", type=int)
    s = sub.add_parser("submit"); s.add_argument("id", type=int); s.add_argument("--code", required=True)
    s = sub.add_parser("allow"); a = s.add_subparsers(dest="what", required=True)
    a.add_parser("list")
    for n in ("add", "remove"):
        x = a.add_parser(n); x.add_argument("name")
    args = ap.parse_args(argv)

    if args.cmd == "status":
        r = ask({"op": "status"})
        print("Peoplecare: " + ("signed in" if r.get("signed_in") else "NOT signed in: George must sign in again (ssh tunnel to port 9223)"))
    elif args.cmd == "add":
        name = save(args.email, args.pdf_name)
        r = ask({"op": "claim.add", "provider": args.provider, "patient": args.patient, "invoice_no": args.invoice_no, "date": args.date,
                 "amount": args.amount, "service": args.service, "reference": args.reference, "email_id": args.email, "pdf": name})
        if r.get("duplicate"):
            print(f"DUPLICATE: already registered as claim #{r['id']} ({r['status']}). Do nothing.")
        elif r.get("needs_provider_approval"):
            print(f"Registered claim #{r['id']}, but '{r['provider']}' is NOT on the allowed list. Ask George: 'New provider: {r['provider']}. Add to the allowed list? (Add / No)'. Do not prepare it until he says Add.")
        else:
            print(f"Registered claim #{r['id']} ({r['provider']}, invoice {r['invoice_no']}). Next: claims prepare {r['id']}")
        if not r.get("duplicate") and not r.get("patient_known", True):
            print(f"FLAG: patient '{r['patient']}' is not a known family name. Tell George before going further.")
    elif args.cmd == "list":
        rows = ask({"op": "claim.list", "status": args.status})
        print("\n".join(line(c) for c in rows) or "(no claims)")
    elif args.cmd == "show":
        print(json.dumps(ask({"op": "claim.show", "id": args.id}), indent=1))
    elif args.cmd == "prepare":
        print(card(ask({"op": "claim.prepare", "id": args.id})))
    elif args.cmd == "submit":
        r = ask({"op": "claim.submit", "id": args.id, "code": args.code})
        print(f"LODGED claim #{r['id']}: {r['provider']}, invoice {r['invoice_no']}, {money(r.get('amount'))}. Peoplecare reference {r['peoplecare_ref']}. Now tell George.")
    elif args.cmd == "cancel":
        r = ask({"op": "claim.cancel", "id": args.id}); print(f"Cancelled claim #{r['id']}.")
    elif args.cmd == "allow":
        if args.what == "list":
            rows = ask({"op": "allow.list"}); print("\n".join(f"- {r['name']}" for r in rows) or "(no providers allowed yet)")
        elif args.what == "add":
            r = ask({"op": "allow.add", "name": args.name})
            print(f"Added '{r['provider']}'." + (f" Claims now ready: {', '.join('#' + str(i) for i in r['now_ready'])}." if r["now_ready"] else ""))
        else:
            print(f"Removed '{ask({'op': 'allow.remove', 'name': args.name})['removed']}'. Its invoices will ask for approval again.")


def main():
    try:
        run(sys.argv[1:])
    except ClaimsError as e:
        print(f"claims: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
