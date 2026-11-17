---
name: fleet-pti-dashboard
description: Maintain the Fleet PTI Streamlit dashboard, including n8n JSON integration, daily driver heatmaps, training follow-up, safety officer assignments, and co-driver reporting.
---

# Fleet PTI dashboard

Use the existing Streamlit application and its Pandas, Plotly, Pydantic, pytest, and optional SQLite architecture. Read [the project README](../../README.md) for configuration and JSON examples. Check the existing adapter, normalization, analytics, filters, and pages before modifying the reporting contract.

## Reporting and visuals

- Support only 7 and 15 days, including today and the preceding local calendar days. Default to America/Chicago. Store timestamps in UTC.
- Keep fleet overview, driver consistency, driver profiles, co-driver analysis, and defects and safety available. Design for approximately 800 drivers across 15 safety officers. Paginate driver heatmaps and large tables.
- Show a cell per driver and date. Green means recorded PTI, gray means no recorded PTI, yellow means review, and red means unsafe. For a day with multiple records, unsafe takes precedence over review, then recorded. Offer a daily list filtered by date and mark. Keep daily color marks on screen and use the CSV for the sortable driver summary.
- Classify frequency by distinct recorded dates. Frequent means at least half of the selected calendar days. Intermittent means at least one day below that threshold. Distinguish zero recorded activity from undated evidence that needs review. A full roster allows drivers without DVIRs to appear. Label an incomplete population as drivers observed in DVIR records.
- Treat absent records as a prompt to check the other PTI platform. True compliance requires reliable driving opportunities and company policy. Historical unsafe inspections require later inspection and repair evidence to assess current equipment condition.
- Count each original pre-trip DVIR ID once. Preserve other inspection types, original inspection detail, signatures, and defect resolution information. Empty defect arrays mean zero defects.

## Webhook and data matching

- Use one n8n webhook for both `GET ?days=7` and `GET ?days=15`. n8n combines all Samsara pages with verified Cogo ELD, training, and roster or assignment data. Accept the existing direct array, `data` wrapper, or enriched wrapper. Keep credentials in environment settings or Streamlit secrets.
- Match by stable IDs. The DVIR author comes from `authorSignature.signatoryUser.id`. Include zero-submission drivers in the roster and set `rosterComplete` only when the reporting roster is complete. Use current safety officer tags for assignment filters. Historical responsibility requires effective dates.
- Match Cogo team assignments using a verified driver ID crosswalk and the inspection time. Use inline co-driver fields or an explicit assignment keyed by DVIR and author ID. Unknown or ambiguous partners stay unknown. Additional signatures remain signatures. Shared equipment can be reported separately from a confirmed team. Credit the inspection once to the author.
- Show confirmed pairs with both drivers and their assigned officers. The co-driver page officer filter matches either participant.
- Link training data using a verified identifier or a verified crosswalk. Names alone can suggest matches for review. Mark ambiguous or missing training records unknown. Put `training_status` and `training_completed_at` on the driver record. Distinguish incomplete, explicitly not trained, and unknown. For date-only completion, compare from the next local day. Include too-early and undated-evidence cases when evaluating post-training activity.
- Compare current assigned driver IDs and vehicle IDs to pre-trip DVIR authors and vehicle IDs in the selected period. Use driver officer tags or `driverAssignments` and the top-level `vehicleAssignments` array. Show counts per officer and export the assigned IDs with zero matching DVIRs for cross-checking.

## Run and verify

From the dashboard directory, run `streamlit run app.py` and `python -m pytest -q` with the project's Python environment. Demo mode uses `sample_data/sample_dvir.json` with 12 fictional drivers per officer across three officers, illustrating frequent, intermittent, and zero recorded submissions. Verify both periods, officer filtering, and empty datasets when changing the board. Distinguish mocked webhook tests from live verification. If a running Streamlit server picks up a changed caller while retaining an older imported function, restart it and verify the relevant page.
