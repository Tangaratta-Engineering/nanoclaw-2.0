# Trip planning sheets

When George asks you to plan or update a holiday, weekend away or trip itinerary, build the planner workbook with the `trip-planner` skill (`/app/skills/trip-planner/scripts/trip-sheet`): a calendar-style Itinerary tab plus budget tabs, built on the `xlsx` skill. Put flight search results in its Flights tab. When a trip needs something compared (cars, tours, flight dates), add a tab for it rather than listing it in chat. Run `xlsx recalc` before sending, and send the file with `send_file`.
