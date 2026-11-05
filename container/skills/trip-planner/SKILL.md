---
name: trip-planner
description: Build and update trip planning spreadsheets (Excel) for George and Emily - a calendar-style day-by-day itinerary plus budget tabs (flights, hotels, food, transfers) and any extra comparison tabs. Use whenever George asks to plan, draft or update a holiday, weekend away or trip itinerary, or sends back an edited planner sheet.
allowed-tools: Bash(/app/skills/trip-planner/scripts/trip-sheet:*), Bash(/app/skills/xlsx/scripts/xlsx:*)
---

# Trip planner sheets

The format George and Emily like: one **Itinerary** tab laid out like a calendar (a column per day, rows for Morning / Lunch / Afternoon / Dinner / Sleep / Accommodation / Comments / Actions), easy to read at a glance and to edit in Excel or Google Sheets. Budget tabs sit beside it, so everything is in one file.

```bash
T=/app/skills/trip-planner/scripts/trip-sheet
$T build spec.json /workspace/agent/trips/nz-2027/NZ-2027-planner.xlsx   # new planner
$T show  file.xlsx                                                       # read the itinerary day by day
$T set   file.xlsx --day 4 --row Morning --text "Cathedral Cove tour"    # change one cell (--append adds a line)
$T add-options file.xlsx --name "Rental cars" --price-label "Price (AUD)" --per trip --multiplier 1 \
   --items '[{"name":"Hertz SUV","price":900,"chosen":1},{"name":"Avis","price":800}]'
/app/skills/xlsx/scripts/xlsx recalc file.xlsx                           # always, before sending
```

Send the file with `send_file`, and say in a line or two what is in it and what you need decided.

## Workflow

1. **Get the brief** (ask only for what you cannot work out): dates or number of days, who is going (names), where from and to, must-dos, budget feel, accommodation base(s). For a short trip a few days is enough; for a long one plan the route first (where each night is slept, drive times between stops).
2. **Research it yourself** with WebSearch/WebFetch (opening hours, durations, drive times, prices). Put travel legs in the text the way George writes them: `AUCKLAND TO HAHEI (2:26)`; mark guesses with `(?)` and who does what (`Em: hike / Kids: cruise`).
3. **Write the spec** and run `build`. Then `xlsx recalc` and read the result back with `show`.
4. **Flights**: do the search with the flight-planning skill (SYD and WSI, search only, never book), then put each option in `flights` with its per-person price. Set `chosen` only when George has decided. Same for hotels. The tab totals follow the options marked chosen (1).
5. **Extra tabs on request**: anything that needs comparing (rental cars, flight cost comparison across dates, tours, insurance) is `add-options` (pick-one comparison with a chosen flag, linked into the Overview total). For a plain list of costs, add a tab with `xlsx`/openpyxl and link it to Overview yourself.
6. **Collaboration**: George and Emily edit the file themselves and send it back. Read it with `show`, keep their edits, and make your changes on a copy (`-v2`) with `set`; never overwrite their file. Tell them what you changed.

## Spec

```json
{"trip": "New Zealand 2027", "start_date": "2027-01-04", "travellers": ["George","Emily","Henry","Sophie"],
 "days": [{"Morning": "Transfer Home -> Airport | Flight SYD -> AUK", "Afternoon": "Pick up car | Check in",
           "Sleep": "Auckland", "Accommodation": "Space available", "Comments": "", "Actions": "Book car"},
          {"Morning": "Rainbows End"}],
 "parts": ["Morning","Lunch","Afternoon","Dinner"],
 "currency": {"home": "AUD", "local": "NZD", "rate": 0.92, "rate_note": "xe.com 6 Nov 2026"},
 "flights": [{"name": "Qantas direct", "price_pp": 650, "chosen": 0}],
 "hotels":  [{"name": "Airbnb Rotorua", "price_per_night": 220, "chosen": 1}],
 "food_per_day": 150, "spending_money": {"George": 300, "Emily": 300},
 "transfers": [{"item": "Rental car 14 days", "cost": 1100}],
 "activities": [{"item": "Hobbiton tour x4", "cost": 480}]}
```

- `days` is a count (empty columns) or a list of day objects; keys are the row names. `start_date` is `YYYY-MM-DD`; the dates and weekday names on the Itinerary are formulas from the **Variables** tab, so changing the start date there moves the whole trip.
- Weekend variant: `"title_row": true` (big trip title on top), your own `parts` (e.g. Early Morning, Late Morning, Lunch, Early Afternoon, Late Afternoon, Dinner) and `"tail_rows": []` to drop Sleep/Accommodation/Comments/Actions.
- Leave out `flights`/`hotels`/`food_per_day` etc. if the trip does not need a budget; with no cost keys you get the Itinerary and Variables tabs only.
- Orange cells are inputs (rate, nights, prices, chosen flags). Hotels and food are in the local currency and converted by the exchange rate on Overview; flights, transfers and activities are in your home currency (`currency_of` overrides, e.g. `{"Transfers": "local"}`). The rate is typed in: look it up, and say where and when in `rate_note`. Never leave a made-up rate.
- A made-up price is worse than a blank one. Put the source in the option's `notes` (`airline site, 6 Nov 2026`), or leave it for George and say so.

## Rules

- Family of four: George, Emily, Henry 10, Sophie 7. Search only, never book or pay.
- Keep trip files under `/workspace/agent/trips/<trip>/`. Do not publish them: they hold family plans and costs.
- Private details (addresses, key-safe codes, booking references) stay in the sheet only; do not repeat them in public channels.
