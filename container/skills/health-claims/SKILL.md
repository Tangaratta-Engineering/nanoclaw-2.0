---
name: health-claims
description: Lodge George's private health insurance (Peoplecare) claims from provider invoice emails, keep the claim records, and manage the list of providers allowed to be claimed. Use when a provider invoice email arrives (Cliniko, physio, chiro, dentist) or George asks about claims.
allowed-tools: Bash(/app/skills/health-claims/scripts/claims:*), Bash(/app/skills/inbox-triage/scripts/inbox-mail:*)
---

# Health claims (Peoplecare)

```bash
C=/app/skills/health-claims/scripts/claims
$C status                         # is the server's Peoplecare login working?
$C add --email <gmail id> --provider "Example Physio" --patient "Mr Alex Example" \
       --invoice-no 1001 --date 2026-11-20 --amount 90.00 --service Physiotherapy --reference physio
$C prepare <id>                   # fills the form up to Peoplecare's Review page and prints the CLAIM CARD. Lodges nothing.
$C submit <id> --code <code>      # lodges it. Only with the code George sent back.
$C cancel <id>
$C list [--status ready|pending_provider|prepared|submitted|failed]   ;   $C show <id>
$C allow list                     # providers allowed to be claimed
$C allow add "Provider name"      # only when George says so
$C allow remove "Provider name"   # when George asks
```

How it works: `add` downloads the invoice PDF from the email and records the claim in the claims database. `prepare` drives George's signed-in Peoplecare page (via a server bridge) through How to claim, Receipts, Reference and Review, stopping before Submit. `submit` ticks the terms and lodges it. The bridge refuses to submit unless the approval code printed on the card is quoted back.

Claim flow, the rules and the wording of messages to George are in `instructions.md`.
