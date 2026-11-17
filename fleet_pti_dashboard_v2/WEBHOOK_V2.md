# Fleet PTI webhook v2

Use one new n8n dashboard endpoint, for example `GET /webhook/pti-dashboard-v2?days=7`. The same endpoint accepts `days=15`. The existing upstream webhooks can keep their current paths. Store their URLs and credentials in n8n.

## Workflow in n8n

1. Accept 7 or 15 and return HTTP 400 for other values. Calculate the reporting start using local midnight in the dashboard timezone and include today.
2. Read the full Samsara roster and fetch all DVIR pages in the window. Separately call the driver-to-officer and vehicle-to-officer feeds. Include current assignments even when the assets have no DVIRs.
3. Optionally read the Monday training board. Map each verified row to a Samsara driver ID, using a board column or a verified Monday item ID crosswalk. Map board statuses to `completed`, `incomplete`, `not_trained`, or `unknown`. Preserve the completion date or timestamp. Drivers without verified training remain unknown. An optional Monday change webhook can refresh a stored snapshot of the board.
4. Optionally read Cogo team assignments and map drivers to Samsara IDs. For each matching DVIR, emit a team row with the original DVIR ID, author ID, and confirmed partner ID. Verify that the pairing covers the inspection time.
5. Assemble one item using the JSON below and return it with HTTP 200 and JSON. Return an error for failed required sources. Use empty arrays when a successful source has zero rows. Omit optional feeds or use empty arrays until those integrations are ready.

## Example response

```json
{
  "schemaVersion": 2,
  "rosterComplete": true,
  "roster": [
    {"id":"D001","name":"Susan Bob"},
    {"id":"D002","name":"Mateo Rivera"}
  ],
  "driverOfficerAssignments": [
    {"driver_id":"D001","safety_officer_id":"SO001","safety_officer_name":"Alice","current":true},
    {"driver_id":"D002","safety_officer_id":"SO002","safety_officer_name":"Carlos","current":true}
  ],
  "vehicleOfficerAssignments": [
    {"vehicle_id":"V001","vehicle_name":"Truck 4","safety_officer_id":"SO001","safety_officer_name":"Alice"},
    {"vehicle_id":"V002","vehicle_name":"Truck 5","safety_officer_id":"SO002","safety_officer_name":"Carlos"}
  ],
  "trainingRecords": [
    {"driver_id":"D001","training_status":"completed","training_completed_at":"2026-11-09"}
  ],
  "teamAssignments": [
    {"dvir_id":"7107471","driver_id":"D001","co_driver_id":"D002"}
  ],
  "dvirs": [
    {
      "id":"7107471",
      "type":"preTrip",
      "startTime":"2026-11-15T12:00:00Z",
      "endTime":"2026-11-15T12:10:00Z",
      "safetyStatus":"safe",
      "authorSignature":{"signatoryUser":{"id":"D001","name":"Susan Bob"}},
      "vehicle":{"id":"V001","name":"Truck 4"},
      "vehicleDefects":[],
      "trailerDefects":[]
    }
  ]
}
```

Set `rosterComplete` to true only when the full reporting roster is present. Version 2 uses fixed array names. Use a common officer ID in both assignment feeds and resolve competing current assignments before sending them. The dashboard joins training by driver ID and treats conflicting training rows as unknown. Preserve optional Samsara inspection fields for drill-down.

Set `PTI_MODE=live` and `N8N_WEBHOOK_URL` in this copy's local `.env` once the new endpoint is ready. Demo mode exercises the version 2 payload. Older response formats are still accepted.
