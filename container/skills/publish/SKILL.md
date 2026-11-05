---
name: publish
description: Publish a web page for George. Private by default (visible only on the home network at https://pages.home/<name>/); going public on Netlify needs George's yes first. Use when George asks you to make, share, host or publish a page, a trip plan, a one-pager or a report as a web page.
---

# Publish web pages

Write the page as plain HTML (one `index.html`, or a folder with CSS/JS/images), then publish it:

```bash
/app/skills/publish/scripts/publish put tasmania-trip /workspace/agent/tasmania/index.html
```

It prints the private link, for example `https://pages.home/tasmania-trip/`. That link only works on George's home network (his phone on mobile data will not open it). Re-run `put` with the same name to update the page. `publish list` shows everything published; `publish remove NAME` takes a private page down.

## Going public (anyone with the link)

Never publish publicly on your own. The steps are:

1. `publish public NAME` prints the files, anything that looks personal (`possibly_sensitive`: emails, phone numbers, long numbers, keys) and a 6-character code.
2. Tell George plainly: "This will be visible to anyone with the link, and can be found by search engines." Show him what is on the page and anything flagged. Ask for a yes.
3. Only after he says yes: `publish public NAME --confirm CODE`. It prints the public link (a `netlify.app` address).
4. `publish unpublish NAME` takes it down again.

The code is valid for 30 minutes and only for the exact content he was shown; if you edit the page afterwards you must ask again.

## Rules

- Do not put personal details of George's family (addresses, phone numbers, school names with children's names, health, money, account numbers) on any page that could go public. Leave them out or ask him.
- Page names are lowercase letters, digits and dashes. You cannot overwrite another agent's page.
- Allowed files: html, css, js, json, txt, md, svg, png, jpg, gif, webp, ico, woff2; 5 MB in total; no links.
- Credentials are handled by the gateway; never ask George for a token in chat.
