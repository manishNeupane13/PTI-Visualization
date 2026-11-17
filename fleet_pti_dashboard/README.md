# Fleet PTI Monitoring Dashboard

A local Streamlit application for reviewing recorded fleet pre-trip inspection (PTI) activity. Fleet overview and Driver PTI consistency count pre-trip DVIRs. Driver profiles, Co-driver analysis, and Defects and safety also retain other inspection types in the selected window.

## Run locally

From the `fleet_pti_dashboard` directory with Python 3.11 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows, activate with `.venv\Scripts\activate`. Open the local address printed by Streamlit. The app uses demo mode by default. The sample fixture contains synthetic drivers and equipment, and its dates shift to the current reporting window.

Run the automated tests with `python -m pytest`.

## Connect n8n

Copy `.env.example` to `.env`, set `PTI_MODE=live`, and enter the production webhook in `N8N_WEBHOOK_URL`. Set `N8N_WEBHOOK_TOKEN` if the workflow uses bearer authentication. Restart Streamlit after changing configuration. Switch back with `PTI_MODE=demo`.

You can also set these keys as environment variables or in `.streamlit/secrets.toml`. Environment values take precedence, followed by `.env` and then Streamlit secrets. Keep credentials in a private configuration file and use an HTTPS endpoint for remote live data.

The app sends GET requests with `days=7` or `days=15`. The live cache defaults to 300 seconds (`PTI_CACHE_TTL`). Refresh clears the current report's cache entry. The sidebar displays the last successful synchronization time. Transient network and HTTP failures are retried up to twice. `PTI_HTTP_TIMEOUT` sets the per-attempt read timeout in seconds.

To persist snapshots, set `PTI_SQLITE_PATH` to a private writable file path. Successful live reports are stored by webhook configuration, reporting period, and synchronization timestamp. Configure file access and retention for the driver and inspection data stored there. When a sync fails, the app can display the latest successful report from the session or SQLite, with a visible snapshot label and the original sync time.

## Response contract

n8n should return HTTP 200 and JSON in one of these forms:

- An array of DVIR objects.
- A Samsara-style object with a `data` array and optional `pagination`. Aggregate all upstream pages in n8n and set `hasNextPage` to false.
- An enriched object with an `inspections` array and optional `drivers`, `driverAssignments` and `teamAssignments` arrays. Configure the array keys using the four `PTI_*_KEY` settings.

Example enriched response:

```json
{
  "rosterComplete": true,
  "drivers": [
    {"id":"D1","name":"Susan Bob"},
    {"id":"D2","name":"Mateo Rivera"}
  ],
  "driverAssignments": [
    {"driver_id":"D1","safety_officer_id":"SO1","safety_officer_name":"Alice","current":true}
  ],
  "teamAssignments": [
    {"dvir_id":"X1","driver_id":"D1","co_driver_id":"D2"}
  ],
  "inspections": [
    {
      "id":"X1",
      "type":"preTrip",
      "startTime":"2026-11-15T06:00:00Z",
      "endTime":"2026-11-15T06:10:00Z",
      "authorSignature":{"signatoryUser":{"id":"D1","name":"Susan Bob"}},
      "vehicle":{"id":"V1","name":"Tractor 24"},
      "safetyStatus":"safe",
      "vehicleDefects":[],
      "trailerDefects":[]
    }
  ]
}
```

Set `rosterComplete` to true only when the driver array represents the complete reporting roster. Otherwise the driver totals cover authors observed in dated DVIRs. Emit a valid empty array when there are no inspections. Driver IDs, vehicle IDs, and DVIR IDs accept strings or integers. Duplicate DVIR IDs keep the first occurrence. Records without a DVIR ID are reported as data quality exclusions.

Assign officers using current driver tags keyed by driver ID. Include the current assignment directly in the driver entry or in `driverAssignments`, using the officer fields in the example. An assignment marked `current: false` or carrying an `endTime` is skipped. Inline DVIR officer enrichment is used when current driver tags are unavailable. The dashboard labels officer views as assignments because historical responsibility would require an effective-dated mapping.

The author comes from `authorSignature.signatoryUser`. Use inline `co_driver_id` and `co_driver_name` when available, or supply a team assignment keyed by both DVIR ID and author ID. Additional signatories remain signatures. A team association retains the original DVIR ID and gives author credit once. Shared vehicles are identified by multiple author IDs inspecting the same vehicle ID. Name-only co-driver enrichment can be displayed without a driver identity join.

Defects may include `defectType`, `description`, `reportedAtTime`, `status`, `isResolved`, `resolvedAtTime` and `mechanicNotes`. Resolution time, status and mechanic notes also support a nested `resolution` object. Empty defect arrays represent zero reported defects. An item without affirmative resolution evidence is counted as unresolved. Full original DVIR details remain available in the profile drill-down.

## Reporting and interpretation

The 7-day and 15-day periods include today and the preceding 6 or 14 calendar days in `PTI_TIMEZONE`, which defaults to `America/Chicago`. n8n should return enough history to cover the same calendar boundaries. The dashboard stores timestamps in UTC and dates a DVIR by local start time, falling back to a valid end time. DVIRs with neither time appear in a review table and are excluded from dated counts.

The driver consistency table counts submissions and distinct submission dates. “Days without recorded PTIs” measures calendar dates with no matching record. Frequent submitters have records on at least half of the selected calendar days. Users can sort the full driver result, page through the heatmap, and export the full filtered table. Equipment and co-driver filters narrow the driver population to authors with matching dated records.

Expected PTI data is unavailable. A compliance calculation requires driving start events, driver and vehicle assignments, and a company policy that defines when an inspection is expected. The `calculate_expected_ptis` entry point currently returns `None`. Unsafe DVIRs and defect rows describe recorded events in the selected window. Assess current equipment condition with later inspection and repair information.

## Troubleshoot live sync

- **Could not reach n8n** — check the webhook host, network, and TLS connectivity from the machine running Streamlit.
- **HTTP 401 or 403** — check workflow authentication and the configured token.
- **HTTP 404** — use the production webhook path and activate the workflow.
- **Invalid or empty JSON** — confirm the workflow returns a JSON body even when the result is empty.
- **Incomplete pagination** — retrieve every upstream page inside n8n before returning a response.
- **Unexpected totals** — check the local calendar boundaries, upstream roster completeness, active dashboard filters, and timestamp review table.

## Training and assignment follow-up

Merge your roster, training and vehicle assignment sources in n8n before returning the dashboard report. On each driver, send `training_status` as `completed`, `incomplete`, `not_trained`, or `unknown`. Use `unknown` when the training record cannot be reliably matched to a Samsara driver ID. For verified completion send `training_completed_at` as an ISO timestamp with an offset or a local date such as `2026-11-10`. Date-only comparisons begin on the following local day.

For assigned vehicles, add a top-level `vehicleAssignments` array with `vehicle_id`, `vehicle_name`, `safety_officer_id`, and `safety_officer_name`. Use the IDs that appear in the DVIRs. For driver assignments, supply the roster's officer fields or the existing `driverAssignments` array.

Driver PTI consistency provides a daily driver list, a 7- or 15-day heatmap, training and frequency filters, and a filtered summary CSV. Assignment counts compare current driver and vehicle IDs against all pre-trip DVIRs in the period. The officer filter applies to both assignment lists. Driver search narrows assigned drivers, and vehicle search narrows assigned vehicles. These lists identify records to cross-check in another PTI platform.
