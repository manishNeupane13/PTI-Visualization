# Fleet PTI dashboard logic

This guide records the v2 dashboard’s current calculations, data scopes, and visual rules for future UI changes. See [WEBHOOK_V2.md](WEBHOOK_V2.md) for the JSON contract.

## 1. Data preparation and reporting window

- Only 7- and 15-day windows are offered. The inclusive range runs from local today minus `days − 1` through local today. The default timezone is `America/Chicago`.
- Parse timestamp strings to UTC. Derive the inspection date from the start time in the reporting timezone, using a valid end time as fallback. Records with neither usable timestamp go to the undated review list and are excluded from dated totals.
- Preserve the first row for each DVIR ID and exclude rows without a DVIR ID. Keep the original record for drill-down. PTI activity uses only `type == "preTrip"`. Profile history, team analysis, and the defects page can use all inspection types.
- Credit the driver identified by `authorSignature.signatoryUser.id`. Other signatures are displayed separately. Prefer current roster or explicit officer assignments and fall back to officer enrichment on observed DVIRs where needed. Match on IDs. The officer filter uses officer ID when available and falls back to officer name and then Unknown.
- In v2, merge training rows onto the roster by Samsara driver ID. Conflicting matches or absent rows yield Unknown. Treat `rosterComplete` as an explicit signal that all rostered drivers are present.

Implementation lives in [the adapter](src/data_adapter.py), [normalization](src/normalization.py), and [scope and filters](src/filters.py).

## 2. Population and filters

A complete roster contributes all roster drivers, including people with zero submissions. Observed authors outside that roster can still appear with their activity. With an incomplete roster, use authors observed in dated DVIRs, including other inspection types. In the fleet overview, the roster-size card counts only filtered roster members when the roster is complete.

Driver, vehicle, and trailer searches are case-insensitive literal matches on ID or name. The standard officer and driver filters match the author, while the co-driver filter matches the confirmed partner ID. Vehicle, trailer, and co-driver filters narrow the driver population to authors with a matching dated record. On the co-driver page, the team report can match the selected officer on either participant. Shared-vehicle counts use the standard author-filtered data.

## 3. Driver calculations

| Measure | Calculation |
|---|---|
| PTI submissions | Number of unique dated pre-trip DVIRs credited to the driver after filters |
| Days with PTI | Number of distinct local dates with at least one matching PTI |
| Days without PTI | Window length minus days with PTI |
| Last PTI date | Latest matching local PTI date in the window |
| Days since last PTI | Last day of the window minus last PTI date. Blank when no matching PTI exists |
| Vehicles inspected | Distinct nonempty vehicle IDs on matching pre-trip DVIRs |
| Unsafe inspections | Matching pre-trip rows marked unsafe |
| Unresolved defects | Sum of unresolved defect rows on the driver's matching pre-trip DVIRs |
| Co-driver involvement | Driver appears as author or confirmed partner in a matching dated team DVIR of any type |

**Frequency.** Frequent means at least 4 recorded days in 7 or at least 8 in 15. Intermittent means at least one recorded day below that threshold. Zero matching dated pre-trips with undated pre-trip evidence means Insufficient information. Other drivers with zero matching dated pre-trips receive No recorded PTI. Multiple submissions on one date increase submission count while counting as one recorded day.

**Daily heatmap.** Rows are drivers and columns are every date in the window. Take the highest status per driver and date.

| Priority | Color | Rule |
|---|---|---|
| 3 | Red | An unsafe pre-trip DVIR exists |
| 2 | Yellow | A dated pre-trip DVIR needs review because its start timestamp is missing or invalid, its end precedes its start, or its safety status is unknown |
| 1 | Green | A pre-trip DVIR is recorded |
| 0 | Gray | No matching dated pre-trip DVIR exists |

The sortable driver table and heatmap use the same current driver page. The daily list can show all matching drivers for one date and selected mark, with pagination. The driver summary CSV exports all matching driver rows and excludes per-date columns. Frequency and training filters narrow the driver table, heatmap, and daily list.

Implementation lives in [analytics](src/analytics.py), [the heatmap component](src/components/heatmap.py), and [the consistency page](pages/2_Driver_Consistency.py).

## 4. Training follow-up

For verified completion, compare the latest matching authored PTI timestamp against the later of the reporting window’s local midnight and the training cutoff. A timestamp cutoff includes activity at or after that instant. A date-only cutoff starts at midnight on the following local day.

1. Missing or unverified status yields **Training status unknown**. Explicit `incomplete` and `not_trained` yield their corresponding labels.
2. Completed with an absent or invalid date yields **Trained · Completion date unknown**.
3. If the comparison start is at or after the current time, show **Too early to assess**.
4. If a matching PTI reaches the cutoff, show **Trained · PTI recorded since training**.
5. Otherwise, matching undated activity yields **Trained · Undated PTI needs review**. With no such evidence, show **Trained · No PTI recorded since training**.

These comparisons describe activity visible in the current filtered window. See [training calculation](src/followup.py).

## 5. Assignment cross-check

Group current driver and vehicle assignments by safety officer. Count distinct assigned IDs and distinct assigned IDs missing from the corresponding set of pre-trip DVIR IDs in the date window. For drivers, compare against DVIR **author IDs**. For vehicles, compare against DVIR **vehicle IDs**. The same vehicle can have activity credited to multiple authors.

Officer selection limits the assignments under review. Driver search limits the assigned-driver list and vehicle search limits the assigned-vehicle list. Match against all pre-trip DVIRs in the window independently of the activity, training, and daily-mark filters. Export the unmatched rows for review in the other PTI platform.

## 6. Fleet overview, profile, team, and defect visuals

| View | Logic |
|---|---|
| Fleet overview cards | Filtered roster or observed drivers, drivers with PTI, drivers in the No recorded PTI category, PTI DVIR rows, drivers with over one PTI, unsafe PTIs, summed unresolved PTI defects, and team-related PTI rows |
| Fleet overview charts | Daily PTI counts filled with zero for empty dates, PTI counts grouped by officer display label, driver counts by frequency, safe/unsafe/unknown PTI distribution, summed vehicle and trailer defects, and top 10 drivers by authored PTIs |
| Driver profile | Show authored PTI count, distinct dates, last recorded date, calendar and daily timeline. Combine authored and confirmed partner records in history, label the role, and retain original DVIR data, signatures and defects for drill-down |
| Confirmed teams | Use explicit DVIR partner data or a team assignment keyed by DVIR ID and author ID. Pair rows are grouped by ordered author and co-driver IDs, with distinct DVIR count and latest inspection. The reverse author order can appear as a second pair row. Team inspection counts credit each DVIR once |
| Shared vehicles | Group by vehicle ID and list vehicles with more than one distinct DVIR author. This indicates shared equipment use |
| Defects and safety | Join defect rows to filtered dated DVIRs of all types. Report total, resolved, and unresolved defects plus unsafe DVIR count. Chart defect type, top 15 vehicles and trailers, and reporting/resolution events by local date |

Defect normalization counts each object in vehicle and trailer defect arrays. An explicit resolved status marks a defect resolved. Otherwise affirmative resolution evidence can be an explicit resolution flag or a valid resolution timestamp, unless the status says open, pending, or unresolved. The remaining defects count as unresolved. Trend dates come from reported and resolved timestamps on the selected defects. Missing timestamps contribute no event to that timeline.

## 7. Interpretation and verification

A missing recorded PTI is an item to investigate. The app has no expected-driving-opportunity denominator and reports no verified missed-inspection count or compliance percentage. An unsafe record describes an inspection event. Assessing current equipment condition requires subsequent inspection and repair information.

When changing the UI, test both date windows, the safety officer filters, zero-submission roster members, repeated same-day DVIRs, ambiguous and unsafe heatmap cells, date-only training completion, confirmed team credit, and missing driver and vehicle assignment matches. Run `python -m pytest -q` from the v2 project. Demo mode exercises the v2 response adapter.
